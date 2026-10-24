"""Delegation resolution and snapshot replay.

Conventions
-----------
* Addresses are lower-case hex strings; ZERO is the null address.
* A delegation event is (block, log_index, delegator, to_delegate).
  Delegating to ZERO is an undelegation.
* A transfer event is (block, log_index, sender, receiver, amount); ZERO as
  sender is a mint, ZERO as receiver a burn.
* The snapshot at block b includes every event with block <= b and nothing
  after it (Compound's getPriorVotes(account, startBlock) uses the same rule).

Resolution rules (documented in README section "Design decisions")
-------------------------------------------------------------------
* "one_hop" (Compound semantics, used for the main analysis): an address's
  tokens count for its current delegatee only. If A -> B and B -> C, A's tokens
  count for B and B's own tokens for C. Delegation is not transitive, so
  cycles need no special rule. Undelegated tokens count for nobody.
* "transitive" (sensitivity analysis): follow A -> B -> C ... until an address
  that is self-delegated or not delegating; that terminal address receives the
  tokens. Cycle rule: every address on a cycle is treated as self-delegated,
  and a chain that runs into a cycle stops at the first cycle address it meets.
"""
from collections import defaultdict

ZERO = "0x" + "0" * 40


def delegates_at(delegations, block):
    """Map delegator -> current delegatee using only events with block <= `block`."""
    current = {}
    for b, li, delegator, to in sorted(delegations, key=lambda e: (e[0], e[1])):
        if b > block:
            break
        if to == ZERO:
            current.pop(delegator, None)
        else:
            current[delegator] = to
    return current


def balances_at(transfers, block):
    """Map address -> token balance using only transfers with block <= `block`."""
    bal = defaultdict(int)
    for b, li, src, dst, amount in sorted(transfers, key=lambda e: (e[0], e[1])):
        if b > block:
            break
        if src != ZERO:
            bal[src] -= amount
        if dst != ZERO:
            bal[dst] += amount
    return {a: v for a, v in bal.items() if v != 0}


def resolve(delegate_of, mode="one_hop"):
    """Final delegatee for each delegating address, under the rule `mode`."""
    if mode == "one_hop":
        return dict(delegate_of)
    if mode != "transitive":
        raise ValueError(mode)
    final = {}
    for start in delegate_of:
        path, seen, a = [], set(), start
        while True:
            nxt = delegate_of.get(a)
            if nxt is None or nxt == a:       # terminal: not delegating, or self-delegated
                end = a
                break
            if a in seen:                     # cycle: stop at the first cycle address met
                end = a
                break
            seen.add(a)
            path.append(a)
            a = nxt
        if end in seen:                       # `start` is on, or leads into, a cycle
            cycle = path[path.index(end):]
            if start in cycle:
                end = start                   # cycle members keep their own tokens
        final[start] = end
    return final


def voting_weights(balances, delegate_of, mode="one_hop"):
    """Voting weight w(d) = sum of balances of addresses whose resolved delegatee is d.

    Only addresses with positive weight are returned: these are the players.
    """
    w = defaultdict(int)
    for a, d in resolve(delegate_of, mode).items():
        w[d] += balances.get(a, 0)
    return {d: v for d, v in w.items() if v > 0}


def replay_snapshots(transfers, delegations, blocks):
    """Yield (block, balances, delegate_of) for each snapshot block, in one pass.

    Equivalent to calling balances_at/delegates_at for each block, but linear in
    the number of events. Returned dicts are live views: copy them if kept.
    """
    events = [(e[0], e[1], 0, e) for e in transfers] + [(e[0], e[1], 1, e) for e in delegations]
    events.sort(key=lambda x: (x[0], x[1]))
    bal, cur = defaultdict(int), {}
    i = 0
    for snap in sorted(blocks):
        while i < len(events) and events[i][0] <= snap:
            _, _, kind, e = events[i]
            if kind == 0:
                _, _, src, dst, amount = e
                if src != ZERO:
                    bal[src] -= amount
                if dst != ZERO:
                    bal[dst] += amount
            else:
                _, _, delegator, to = e
                if to == ZERO:
                    cur.pop(delegator, None)
                else:
                    cur[delegator] = to
            i += 1
        yield snap, bal, cur
