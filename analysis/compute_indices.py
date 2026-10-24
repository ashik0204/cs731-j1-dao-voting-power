"""Banzhaf and Shapley-Shubik indices for every proposal's game.

    python -m analysis.compute_indices [--resolution R] [--force]

Reads data/processed/{proposals,weights}; writes results/indices_r<R>.csv.gz
(one row per proposal x player) and results/games_r<R>.csv (one row per game).
Players are delegates with positive one-hop (on-chain) weight at the snapshot.
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import yaml

from power.gap import game_indices

CONFIG = yaml.safe_load(open("config.yaml"))
RES = Path("results")


def load_weights():
    w = pd.read_csv("data/processed/weights.csv.gz")
    return w[w.weight > 0]


def compute(resolution, force=False, proposal_ids=None):
    out = RES / f"indices_r{resolution}.csv.gz"
    games_out = RES / f"games_r{resolution}.csv"
    if out.exists() and games_out.exists() and not force and proposal_ids is None:
        return pd.read_csv(out), pd.read_csv(games_out)
    props = pd.read_csv("data/processed/proposals.csv")
    weights = load_weights()
    quorum = CONFIG["governance"]["quorum_votes"]
    frames, games = [], []
    ids = props.proposal_id if proposal_ids is None else proposal_ids
    for pid in ids:
        wp = weights[weights.proposal_id == pid]
        t0 = time.time()
        df = game_indices(dict(zip(wp.delegate, wp.weight)), quorum, resolution)
        df.insert(0, "proposal_id", pid)
        frames.append(df)
        games.append({"proposal_id": pid, "n_players": len(df), "n_live": df.attrs["n_live"],
                      "total_weight": df.weight.sum(), "unit": df.attrs["unit"],
                      "total_int": df.attrs["total_int"], "quota": df.attrs["quota"],
                      "quorum_binds": df.attrs["quota"] > df.attrs["total_int"] // 2 + 1,
                      "dummy_weight_share": df.loc[df.int_weight == 0, "share"].sum(),
                      "seconds": round(time.time() - t0, 2)})
        print(f"  proposal {pid}: {len(df)} players, {df.attrs['n_live']} non-dummy, "
              f"{time.time() - t0:.1f}s", flush=True)
    ind, g = pd.concat(frames, ignore_index=True), pd.DataFrame(games)
    if proposal_ids is None:
        RES.mkdir(exist_ok=True)
        ind.to_csv(out, index=False)
        g.to_csv(games_out, index=False)
    return ind, g


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolution", type=int, default=CONFIG["power"]["resolution"])
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    compute(a.resolution, a.force)
