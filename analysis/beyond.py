"""Extensions beyond the base analysis.

1. Participation game: power among the addresses that actually voted.
   Players are the for/against voters of a proposal, weights their cast votes,
   and the quota is the same Compound rule q = max(floor(W/2) + 1, ceil(Q/u))
   with W the cast for+against weight. Unlike the all-delegates game, the
   400k COMP quorum can bind here, because turnout is low.
   (Abstain votes count for neither side nor quorum in GovernorBravo.)

2. Prior work, recomputed on our data with the same definitions:
   * Fritsch, Mueller & Wattenhofer (arXiv:2204.01176): Nakamoto coefficient,
     the fewest delegates holding more than 50% of voting power, at block 14,300,000.
   * Messias et al. (arXiv:2305.17655): number of voters needed to reach at
     least 50% of the votes cast on a proposal, averaged over proposals.
"""
import numpy as np
import pandas as pd

from power.gap import game_indices


def participation_games(props, votes, quorum, resolution):
    """Banzhaf / Shapley-Shubik in each decided proposal's participation game."""
    rows, frames = [], []
    for _, p in props[props.outcome != "canceled"].iterrows():
        v = votes[(votes.proposal_id == p.proposal_id) & (votes.support.isin([0, 1])) & (votes.votes > 0)]
        if len(v) == 0:
            continue
        w = dict(zip(v.voter, v.votes))
        df = game_indices(w, quorum, resolution)
        df.insert(0, "proposal_id", p.proposal_id)
        frames.append(df)
        a = df.attrs
        ss = np.sort(df.shapley.values)[::-1]
        rows.append({"proposal_id": p.proposal_id, "n_voters": len(df), "cast_weight": df.weight.sum(),
                     "quorum_binds": a["quota"] > a["total_int"] // 2 + 1,
                     "no_winning_coalition": a["quota"] > a["total_int"],
                     "top1_share": df.share.max(), "top1_banzhaf": df.banzhaf.max(),
                     "top1_shapley": df.shapley.max(),
                     "nakamoto_shapley": int(np.searchsorted(np.cumsum(ss), 0.5, side="right") + 1)
                     if ss.sum() > 0 else None})
    return pd.DataFrame(rows), pd.concat(frames, ignore_index=True)


def nakamoto(weights):
    """Fewest players whose combined weight exceeds half the total."""
    w = np.sort(np.asarray(weights, dtype=float))[::-1]
    return int(np.searchsorted(np.cumsum(w), w.sum() / 2, side="right") + 1)


def voters_to_half(votes):
    """Per proposal: fewest voters (largest first) whose votes reach >= 50% of all votes cast."""
    out = {}
    for pid, v in votes[votes.votes > 0].groupby("proposal_id"):
        w = np.sort(v.votes.values)[::-1]
        out[pid] = int(np.searchsorted(np.cumsum(w), w.sum() / 2, side="left") + 1)
    return pd.Series(out, name="voters_to_half")
