"""Realised outcomes: how many addresses were needed to change the result?

For one proposal let F, A be the realised for/against weight and Q the quorum.
It passed iff F > A and F >= Q. Every player (delegate with positive weight at
the snapshot) is in one of three groups: voted for, voted against, or did not
vote for/against (abstained or did not vote).

A *flip set* is a set of players who, by changing their own vote and nobody
else's, reverse the outcome:
  * passed proposal: for-voters switch to against (F -= v, A += v), others join
    against (A += v). Reversed iff F' <= A' or F' < Q.
  * defeated proposal: against-voters switch to for (F += v, A -= v), others
    join for (F += v). Reversed iff F' > A' and F' >= Q.
`min_flip_set` returns a smallest flip set (by number of addresses).
"""


def _greedy(values, need):
    """Fewest items from `values` whose sum is >= need (largest first is optimal)."""
    if need <= 0:
        return []
    out, s = [], 0
    for i, v in sorted(enumerate(values), key=lambda x: -x[1]):
        out.append(i)
        s += v
        if s >= need:
            return out
    return None


def passed(F, A, Q):
    return F > A and F >= Q


def min_flip_set(players, F, A, Q):
    """Smallest flip set. `players` is a list of (address, weight, side) with side
    in {"for", "against", "none"}. Returns a list of addresses, or None if no
    set of players can reverse the outcome."""
    if passed(F, A, Q):
        fors = [p for p in players if p[2] == "for"]
        # (a) margin: a switching for-voter moves the margin F - A by 2v, a
        #     non-for player joining against by v; need total >= F - A.
        movers = fors + [p for p in players if p[2] == "none"]
        gain = [2 * p[1] if p[2] == "for" else p[1] for p in movers]
        a = _greedy(gain, F - A)
        best = None if a is None else [movers[i][0] for i in a]
        # (b) quorum: for-voters leaving must lower F below Q: total > F - Q.
        b = _greedy([p[1] for p in fors], F - Q + 1e-12)
        if b is not None and (best is None or len(b) < len(best)):
            best = [fors[i][0] for i in b]
        return best
    # Defeated: need margin gain >= A - F + eps and quorum gain >= Q - F.
    # Within each group a larger weight is better on both criteria, so an
    # optimal k-set takes the top j against-voters and the top k-j others.
    ag = sorted([p for p in players if p[2] == "against"], key=lambda p: -p[1])
    ot = sorted([p for p in players if p[2] == "none"], key=lambda p: -p[1])
    pa, po = _prefix(ag), _prefix(ot)
    for k in range(1, len(ag) + len(ot) + 1):
        for j in range(max(0, k - len(ot)), min(k, len(ag)) + 1):
            f = F + pa[j] + po[k - j]
            a = A - pa[j]
            if passed(f, a, Q):
                return [p[0] for p in ag[:j]] + [p[0] for p in ot[:k - j]]
    return None


def _prefix(ps):
    out = [0.0]
    for p in ps:
        out.append(out[-1] + p[1])
    return out


def set_flips(players, F, A, Q, subset):
    """Does `subset` (a set of addresses) reverse the outcome on its own?"""
    was = passed(F, A, Q)
    for addr, v, side in players:
        if addr not in subset:
            continue
        if was:
            if side == "for":
                F, A = F - v, A + v
            elif side == "none":
                A += v
        else:
            if side == "against":
                F, A = F + v, A - v
            elif side == "none":
                F += v
    return passed(F, A, Q) != was
