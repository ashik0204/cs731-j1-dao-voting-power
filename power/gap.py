"""Nominal token share vs effective power (Banzhaf, Shapley-Shubik).

For proposal p with players i and voting weights w_i:
    nominal share   s_i = w_i / sum_j w_j
    gap             g_i = index_i - s_i   (positive: more power than tokens)
Across proposals, an address absent from a proposal's game counts as 0 for
that proposal, so averages are over all analysed proposals.
"""
import numpy as np
import pandas as pd

from power.banzhaf import banzhaf
from power.shapley import shapley_shubik
from power.game import integerise, quota


def ranks(x):
    """Average ranks (1-based), ties get the mean of their positions."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x))
    r[order] = np.arange(1, len(x) + 1)
    for v in np.unique(x):
        m = x == v
        if m.sum() > 1:
            r[m] = r[m].mean()
    return r


def spearman(x, y):
    """Spearman rank correlation = Pearson correlation of average ranks."""
    if len(x) < 2:
        return float("nan")
    rx, ry = ranks(x), ranks(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def game_indices(weights, quorum, resolution):
    """Power indices for one proposal's game.

    weights: dict address -> weight (COMP). Returns a DataFrame with one row per
    player: weight, share, int_weight, banzhaf, shapley, plus the game's quota
    and unit as attributes.
    """
    addrs = sorted(weights, key=lambda a: -weights[a])
    w = np.array([weights[a] for a in addrs], dtype=float)
    ints, q_quorum, unit = integerise(w, resolution, quorum)
    ints = np.array(ints)
    q = quota(int(ints.sum()), q_quorum)
    live = ints > 0                     # zero-weight players are null players
    beta = np.zeros(len(w))
    phi = np.zeros(len(w))
    beta[live] = banzhaf(ints[live], q)
    phi[live] = shapley_shubik(ints[live], q)
    df = pd.DataFrame({"address": addrs, "weight": w, "share": w / w.sum(),
                       "int_weight": ints, "banzhaf": beta, "shapley": phi})
    df.attrs.update(quota=q, unit=unit, total_int=int(ints.sum()), n_live=int(live.sum()))
    return df
