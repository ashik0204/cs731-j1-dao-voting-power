"""Banzhaf index by dynamic programming over integer weights.

Raw Banzhaf value of player i:
    psi_i = #{S subset of N \\ {i} : w(S) < q <= w(S) + w_i} / 2^(n-1)
          = P(q - w_i <= w(S) < q),  S a uniformly random subset of the others.
Normalised index: beta_i = psi_i / sum_j psi_j  (sums to 1).

DP state: p[x] = P(w(S) = x) for x = 0..q-1 over the players added so far.
Adding a player of weight v (in S with probability 1/2):
    p'[x] = (p[x] + p[x - v]) / 2.
Mass at x >= q is dropped; it can never be part of a swing.
Cost O(q) per added player; see game.leave_one_out for the total.
"""
import numpy as np

from power.game import leave_one_out


def _add(q):
    def add(p, v):
        out = p * 0.5
        if v < q:
            out[v:] += 0.5 * p[:q - v]
        return out
    return add


def banzhaf_raw(weights, q):
    """Raw (non-normalised) Banzhaf values psi_i, in input order."""
    weights = [int(w) for w in weights]
    if q <= 0:
        return np.zeros(len(weights))
    empty = np.zeros(q)
    empty[0] = 1.0

    def evaluate(p, w):
        return float(p[max(0, q - w):].sum()) if w > 0 else 0.0

    by_w = leave_one_out(weights, empty, _add(q), evaluate)
    return np.array([by_w[w] for w in weights])


def banzhaf(weights, q):
    """Normalised Banzhaf index beta_i (sums to 1; all zeros if no player swings)."""
    raw = banzhaf_raw(weights, q)
    s = raw.sum()
    return raw / s if s > 0 else raw
