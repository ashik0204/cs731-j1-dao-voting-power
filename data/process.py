"""Turn cached raw logs into processed CSV tables (runs offline from data/raw/).

    python -m data.process

Writes data/processed/:
  proposals.csv    id, proposer, start/end block and UTC date, snapshot block, outcome, vote totals
  votes.csv        proposal_id, voter, support (0 against, 1 for, 2 abstain), votes
  delegations.csv  every DelegateChanged event (delegator, from, to)
  balances.csv     per proposal snapshot: every delegating address with its
                   balance and delegatee (zero-balance delegators omitted)
  weights.csv      per proposal snapshot: our delegate voting weights, next to the
                   on-chain checkpoint value (DelegateVotesChanged) for checking
  validation.csv   per proposal: agreement of our weights with the chain
  counts.json      size of the raw download and number of events of each type
Every column is described in data/processed/COLUMNS.md.
"""
import bisect
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yaml

from data.rpc import RAW, cached_logs
from data.abi import topic, selector, word, words, addr_topic, addr_word, dyn_string
from power.delegation import replay_snapshots, voting_weights

CONFIG = yaml.safe_load(open("config.yaml"))
OUT = Path("data/processed")
DEC = 10 ** CONFIG["governance"]["decimals"]
STATES = ["Pending", "Active", "Canceled", "Defeated", "Succeeded", "Queued", "Expired", "Executed"]


def load(name, contract, start):
    """Read cached logs (raises if the cache is incomplete: run data.fetch first)."""
    c = CONFIG["contracts"][contract]

    class Offline:
        def get_logs(self, *a):
            raise RuntimeError(f"{name} not cached; run `python -m data.fetch` first")
    return cached_logs(Offline(), name, c, [topic(name)], start, CONFIG["blocks"]["end"])


def proposals_table(logs):
    calls = json.loads((RAW / "calls_governor.json").read_text())
    gov, end = CONFIG["contracts"]["governor"], CONFIG["blocks"]["end"]
    canceled = {int(l["data"][2:66], 16) for l in logs["ProposalCanceled"]}
    queued = {int(l["data"][2:66], 16) for l in logs["ProposalQueued"]}
    executed = {int(l["data"][2:66], 16) for l in logs["ProposalExecuted"]}
    rows = []
    for l in logs["ProposalCreated"]:
        w = words(l["data"])
        pid = w[0]
        desc = dyn_string(l["data"], 8)
        title = desc.strip().split("\n")[0].lstrip("# ").strip()[:120]
        state_hex = calls.get(f"{gov}:{selector('state(uint256)')}{word(pid)}:{end}")
        prop_hex = calls.get(f"{gov}:{selector('proposals(uint256)')}{word(pid)}:{end}")
        pw = words(prop_hex) if prop_hex else [None] * 10
        rows.append({
            "proposal_id": pid, "proposer": addr_word(w[1]), "created_block": l["block"],
            "start_block": w[6], "end_block": w[7], "snapshot_block": w[6],
            "canceled_event": pid in canceled, "queued_event": pid in queued,
            "executed_event": pid in executed,
            "state_onchain": STATES[int(state_hex, 16)] if state_hex else None,
            "for_onchain": pw[5] / DEC if pw[5] is not None else None,
            "against_onchain": pw[6] / DEC if pw[6] is not None else None,
            "abstain_onchain": pw[7] / DEC if pw[7] is not None else None,
            "title": title,
        })
    return pd.DataFrame(rows).sort_values("proposal_id")


def outcome(row, quorum):
    """Outcome from events and tallies: executed, queued (not executed), canceled,
    defeated (for <= against or for < quorum), succeeded (passed, never queued)."""
    if row.canceled_event:
        return "canceled"
    if row.executed_event:
        return "executed"
    if row["for"] > row.against and row["for"] >= quorum:
        return "queued" if row.queued_event else "succeeded"
    return "defeated"


def votes_table(logs):
    rows = []
    for l in logs["VoteCast"]:
        w = words(l["data"])
        rows.append({"proposal_id": w[0], "voter": addr_topic(l["topics"][1]), "support": w[1],
                     "votes_wei": w[2], "votes": w[2] / DEC, "block": l["block"]})
    return pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = CONFIG["blocks"]
    logs = {n: load(n, "governor", b["governor_deploy"]) for n in
            ("ProposalCreated", "VoteCast", "ProposalCanceled", "ProposalQueued", "ProposalExecuted")}
    for n in ("DelegateChanged", "DelegateVotesChanged", "Transfer"):
        logs[n] = load(n, "token", b["token_deploy"])
    print({k: len(v) for k, v in logs.items()})

    votes = votes_table(logs)
    votes.drop(columns="votes_wei").to_csv(OUT / "votes.csv", index=False)

    props = proposals_table(logs)
    tally = votes.pivot_table(index="proposal_id", columns="support", values="votes",
                              aggfunc="sum", fill_value=0).rename(columns={0: "against", 1: "for", 2: "abstain"})
    props = props.merge(tally, left_on="proposal_id", right_index=True, how="left").fillna(
        {"for": 0, "against": 0, "abstain": 0})
    props["n_voters"] = props.proposal_id.map(votes.groupby("proposal_id").size()).fillna(0).astype(int)
    props["outcome"] = props.apply(outcome, axis=1, quorum=CONFIG["governance"]["quorum_votes"])
    times = {int(k): v for k, v in json.loads((RAW / "block_times.json").read_text()).items()}
    utc_date = lambda blk: pd.Timestamp(times[blk], unit="s").strftime("%Y-%m-%d")
    props.insert(props.columns.get_loc("start_block") + 1, "start_date", props.start_block.map(utc_date))
    props.insert(props.columns.get_loc("end_block") + 1, "end_date", props.end_block.map(utc_date))
    props.to_csv(OUT / "proposals.csv", index=False)
    counts = {"raw_mb": round(sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 2**20, 1),
              "events": {k: len(v) for k, v in logs.items()},
              "reference_dates": {name: utc_date(blk) for name, blk in CONFIG["reference_blocks"].items()},
              "end_block_date": utc_date(CONFIG["blocks"]["end"])}
    (OUT / "counts.json").write_text(json.dumps(counts, indent=2))

    transfers = [(l["block"], l["logIndex"], addr_topic(l["topics"][1]), addr_topic(l["topics"][2]),
                  int(l["data"], 16)) for l in logs["Transfer"]]
    delegations = [(l["block"], l["logIndex"], addr_topic(l["topics"][1]), addr_topic(l["topics"][3]))
                   for l in logs["DelegateChanged"]]
    pd.DataFrame([{"block": l["block"], "log_index": l["logIndex"], "delegator": addr_topic(l["topics"][1]),
                   "from_delegate": addr_topic(l["topics"][2]), "to_delegate": addr_topic(l["topics"][3])}
                  for l in logs["DelegateChanged"]]).to_csv(OUT / "delegations.csv", index=False)

    # On-chain checkpoints: delegate -> sorted [(block, logIndex, newBalance)]
    checkpoints = defaultdict(list)
    for l in logs["DelegateVotesChanged"]:
        checkpoints[addr_topic(l["topics"][1])].append((l["block"], l["logIndex"], words(l["data"])[1]))
    for v in checkpoints.values():
        v.sort()

    def onchain_votes(d, block):
        cp = checkpoints.get(d, [])
        i = bisect.bisect_right(cp, (block, float("inf"), 0))
        return cp[i - 1][2] if i else 0

    snap_to_ids = props.groupby("snapshot_block").proposal_id.apply(list).to_dict()
    bal_rows, w_rows, val_rows = [], [], []
    for snap, bal, dels in replay_snapshots(transfers, delegations, snap_to_ids):
        weights = voting_weights(bal, dels, "one_hop")
        weights_tr = voting_weights(bal, dels, "transitive")
        onchain = {d: onchain_votes(d, snap) for d in checkpoints}
        onchain = {d: v for d, v in onchain.items() if v > 0}
        for pid in snap_to_ids[snap]:
            for a, d in sorted(dels.items()):
                if bal.get(a, 0) > 0:
                    bal_rows.append((pid, snap, a, bal[a] / DEC, d))
            for d in sorted(set(weights) | set(onchain) | set(weights_tr)):
                w_rows.append((pid, snap, d, weights.get(d, 0) / DEC, weights_tr.get(d, 0) / DEC,
                               onchain.get(d, 0) / DEC))
            diffs = [abs(weights.get(d, 0) - onchain.get(d, 0)) for d in set(weights) | set(onchain)]
            val_rows.append({"proposal_id": pid, "snapshot_block": snap, "n_players": len(weights),
                             "n_players_onchain": len(onchain),
                             "total_weight": sum(weights.values()) / DEC,
                             "total_weight_onchain": sum(onchain.values()) / DEC,
                             "n_mismatch": sum(x > 0 for x in diffs), "max_abs_diff": max(diffs, default=0) / DEC})
        print(f"  snapshot {snap}: {len(weights)} players, {sum(weights.values()) / DEC:,.0f} COMP delegated",
              flush=True)

    pd.DataFrame(bal_rows, columns=["proposal_id", "snapshot_block", "address", "balance", "delegatee"]
                 ).to_csv(OUT / "balances.csv.gz", index=False)
    pd.DataFrame(w_rows, columns=["proposal_id", "snapshot_block", "delegate", "weight",
                                  "weight_transitive", "weight_onchain"]).to_csv(OUT / "weights.csv.gz", index=False)
    val = pd.DataFrame(val_rows)
    # Each vote's weight should equal our weight for the voter at the snapshot.
    wt = pd.DataFrame(w_rows, columns=["proposal_id", "snapshot_block", "delegate", "weight",
                                       "weight_transitive", "weight_onchain"])
    m = votes.merge(wt, left_on=["proposal_id", "voter"], right_on=["proposal_id", "delegate"], how="left")
    m["weight"] = m["weight"].fillna(0)
    m["vote_diff"] = (m["votes"] - m["weight"]).abs()
    val = val.merge(m.groupby("proposal_id").agg(n_votes=("voter", "size"),
                                                 n_vote_mismatch=("vote_diff", lambda s: int((s > 1e-6).sum())),
                                                 max_vote_diff=("vote_diff", "max")),
                    left_on="proposal_id", right_index=True, how="left")
    val.to_csv(OUT / "validation.csv", index=False)
    print(val[["n_mismatch", "n_vote_mismatch"]].sum().to_dict())


if __name__ == "__main__":
    main()
