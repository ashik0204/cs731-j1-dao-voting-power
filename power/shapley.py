"""Shapley-Shubik index by dynamic programming over (coalition size, weight).

Player i is pivotal in an ordering if the players before it, S, satisfy
w(S) < q <= w(S) + w_i. Counting orderings:
    phi_i = sum_{S subset of N \\ {i}, q - w_i <= w(S) < q}  |S|! (n-1-|S|)! / n!
          = (1/n) * sum_{k=0}^{n-1} P_k(q - w_i <= w(S) < q),
where P_k is the distribution of w(S) for S a uniformly random k-subset of
the n-1 other players (because |S|!(n-1-|S|)!/n! * C(n-1, k) = 1/n).

DP state after m players: P[k, x] = P(w(S) = x) for a random k-subset S of
those m players, x = 0..q-1. Adding a player of weight v:
    P'[k, x] = ((m+1-k) P[k, x] + k P[k-1, x-v]) / (m+1)
(a random k-subset of m+1 players excludes the new player with probability
(m+1-k)/(m+1)). Every update is a convex combination, so values stay in [0, 1]
and nothing overflows even for n in the thousands. Cost O(n q) per player.
"""
import numpy as np

from power.game import leave_one_out


def shapley_shubik(weights, q):
    """Shapley-Shubik index phi_i in input order (sums to 1 if any coalition wins)."""
    weights = [int(w) for w in weights]
    n = len(weights)
    if n == 0 or q <= 0:
        return np.zeros(n)
    K = n                                    # sizes k = 0..n-1 are needed
    k = np.arange(K, dtype=float)[:, None]
    empty = (np.zeros((K, q)), 0)
    empty[0][0, 0] = 1.0

    def add(state, v):
        P, m = state
        out = (m + 1 - k) * P
        if v < q:
            out[1:, v:] += k[1:] * P[:-1, :q - v]
        return out / (m + 1), m + 1

    def evaluate(state, w):
        P, m = state
        if w <= 0:
            return 0.0
        return float(P[:, max(0, q - w):].sum()) / n

    by_w = leave_one_out(weights, empty, add, evaluate)
    return np.array([by_w[w] for w in weights])
