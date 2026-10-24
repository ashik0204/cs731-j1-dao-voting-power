"""Weighted voting games [q; w_1, ..., w_n] and helpers shared by the indices.

A coalition S wins iff w(S) = sum_{i in S} w_i >= q. Weights and quota are
non-negative integers so the indices can be computed by dynamic programming
over the weight axis 0..q-1.
"""
import math
from collections import Counter


def quota(total_weight, quorum_units):
    """Compound winning rule as a quota: q = max(floor(W/2) + 1, Q).

    With every player voting for or against, the for-side S passes iff
    w(S) > w(N \\ S)  (i.e. w(S) >= floor(W/2) + 1)  and  w(S) >= Q (quorum).
    """
    return max(total_weight // 2 + 1, quorum_units)


def integerise(weights, resolution, quorum):
    """Round real weights to integers in units of u = sum(weights) / resolution.

    Returns (int_weights, quorum_units, u). The quorum is rounded up,
    Q_units = ceil(Q / u), so the rounded game never makes passing easier.
    Players with w_i < u/2 get weight 0 and become dummies.
    """
    total = sum(weights)
    u = total / resolution
    ints = [int(round(w / u)) for w in weights]
    return ints, math.ceil(quorum / u), u


def leave_one_out(weights, empty, add, evaluate):
    """Evaluate `evaluate(state, w_i)` once per distinct weight, where `state`
    describes all players except one copy of a player with weight w_i.

    `empty` is the state with no players, and `add(state, w)` returns a new
    state with one more player of weight w. Players with equal weight have
    equal indices (symmetry), so we work on groups of equal weight. Divide and
    conquer over the groups means only additions are needed (no numerically
    unstable "removal" of a player): O((d log d + n)) calls to `add` for d
    distinct weights and n players.
    Returns {weight: value}.
    """
    groups = sorted(Counter(weights).items())
    out = {}

    def rec(state, lo, hi):
        if hi - lo == 1:
            w, m = groups[lo]
            for _ in range(m - 1):
                state = add(state, w)
            out[w] = evaluate(state, w)
            return
        mid = (lo + hi) // 2
        left = state
        for w, m in groups[mid:hi]:
            for _ in range(m):
                left = add(left, w)
        rec(left, lo, mid)
        right = state
        for w, m in groups[lo:mid]:
            for _ in range(m):
                right = add(right, w)
        rec(right, mid, hi)

    if groups:
        rec(empty, 0, len(groups))
    return out
