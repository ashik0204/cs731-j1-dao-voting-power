"""Download and cache all raw data for the configured DAO.

    python -m data.fetch

Writes gzip JSON log chunks under data/raw/<event>/ and cached eth_call results
under data/raw/calls_*.json. Rerunning reuses the cache (offline if complete).
"""
import yaml

from data.rpc import RPC, endpoints, cached_logs, cached_call, cached_block_times
from data.abi import topic, selector, word

CONFIG = yaml.safe_load(open("config.yaml"))


def fetch_logs(rpc):
    """All governor and token events in the configured block window."""
    c, b = CONFIG["contracts"], CONFIG["blocks"]
    out = {}
    for name in ("ProposalCreated", "VoteCast", "ProposalCanceled", "ProposalQueued", "ProposalExecuted"):
        print(f"fetching {name}", flush=True)
        out[name] = cached_logs(rpc, name, c["governor"], [topic(name)], b["governor_deploy"], b["end"])
    for name in ("DelegateChanged", "DelegateVotesChanged", "Transfer"):
        print(f"fetching {name}", flush=True)
        out[name] = cached_logs(rpc, name, c["token"], [topic(name)], b["token_deploy"], b["end"])
    return out


def fetch_calls(rpc, proposal_ids):
    """On-chain values used to cross-check our reconstruction (at the end block)."""
    gov, end = CONFIG["contracts"]["governor"], CONFIG["blocks"]["end"]
    quorum = int(cached_call(rpc, "calls_governor", gov, selector("quorumVotes()"), end), 16)
    print(f"quorumVotes at block {end}: {quorum / 1e18:,.0f} COMP")
    for i, pid in enumerate(proposal_ids):
        cached_call(rpc, "calls_governor", gov, selector("state(uint256)") + word(pid), end)
        cached_call(rpc, "calls_governor", gov, selector("proposals(uint256)") + word(pid), end)
        if i % 50 == 0:
            print(f"  calls: proposal {pid}", flush=True)


def main():
    rpc = RPC(endpoints(CONFIG["rpc_env_var"]))
    logs = fetch_logs(rpc)
    ids = sorted(int(l["data"][2:66], 16) for l in logs["ProposalCreated"])
    fetch_calls(rpc, ids)
    # Dates for reporting: every proposal's start and end block, plus reference blocks.
    blocks = [int(l["data"][2 + 64 * k:2 + 64 * (k + 1)], 16) for l in logs["ProposalCreated"] for k in (6, 7)]
    blocks += list(CONFIG["reference_blocks"].values()) + [CONFIG["blocks"]["end"]]
    cached_block_times(rpc, blocks)
    for k, v in logs.items():
        print(f"{k}: {len(v)} logs")


if __name__ == "__main__":
    main()
