from power.delegation import (ZERO, delegates_at, balances_at, resolve,
                              voting_weights, replay_snapshots)

A, B, C, D, X = ("0x" + c * 40 for c in "abcde")


def test_self_delegation():
    w = voting_weights({A: 10, B: 5}, {A: A})
    assert w == {A: 10}                    # B never delegated: its tokens count for nobody


def test_one_hop_chain_is_not_transitive():
    # A -> B -> C (Compound semantics)
    dels = {A: B, B: C, C: C}
    assert voting_weights({A: 1, B: 2, C: 4}, dels, "one_hop") == {B: 1, C: 6}


def test_transitive_chain():
    dels = {A: B, B: C, C: C}
    assert resolve(dels, "transitive") == {A: C, B: C, C: C}
    assert voting_weights({A: 1, B: 2, C: 4}, dels, "transitive") == {C: 7}


def test_transitive_chain_to_undelegated_terminal():
    # C does not delegate: it is the terminal and receives A's and B's tokens,
    # but C's own tokens are not delegated and count for nobody.
    dels = {A: B, B: C}
    assert voting_weights({A: 1, B: 2, C: 4}, dels, "transitive") == {C: 3}


def test_cycle_rule():
    # A -> B -> A is a cycle, X -> A leads into it.
    dels = {A: B, B: A, X: A}
    r = resolve(dels, "transitive")
    assert r[A] == A and r[B] == B         # cycle members keep their own tokens
    assert r[X] == A                       # first cycle address met
    assert voting_weights({A: 1, B: 2, X: 4}, dels, "transitive") == {A: 5, B: 2}
    # one-hop: each cycle member simply receives the other's tokens
    assert voting_weights({A: 1, B: 2, X: 4}, dels, "one_hop") == {B: 1, A: 6}


def test_longer_cycle_and_tail():
    dels = {A: B, B: C, C: A, D: X, X: B}
    r = resolve(dels, "transitive")
    assert r[A] == A and r[B] == B and r[C] == C
    assert r[D] == B and r[X] == B


def test_undelegation():
    events = [(1, 0, A, B), (5, 0, A, ZERO)]
    assert delegates_at(events, 4) == {A: B}
    assert delegates_at(events, 5) == {}
    events.append((7, 0, A, C))            # re-delegate after undelegating
    assert delegates_at(events, 9) == {A: C}


def test_redelegation_order_within_block():
    events = [(3, 2, A, C), (3, 1, A, B)]  # same block: log index decides
    assert delegates_at(events, 3) == {A: C}


TRANSFERS = [(1, 0, ZERO, A, 100), (2, 0, A, B, 30), (6, 0, B, C, 10), (9, 0, A, ZERO, 5)]
DELEGATIONS = [(1, 1, A, A), (3, 0, B, A), (6, 1, B, C), (8, 0, A, ZERO)]


def test_snapshot_ignores_later_events():
    bal = balances_at(TRANSFERS, 5)
    dels = delegates_at(DELEGATIONS, 5)
    assert bal == {A: 70, B: 30}
    assert dels == {A: A, B: A}
    assert voting_weights(bal, dels) == {A: 100}
    # Adding arbitrary events after block 5 must not change the block-5 snapshot.
    later_t = TRANSFERS + [(6, 5, A, D, 70), (100, 0, ZERO, D, 10 ** 6)]
    later_d = DELEGATIONS + [(6, 7, A, D), (50, 0, D, D)]
    assert balances_at(later_t, 5) == bal
    assert delegates_at(later_d, 5) == dels


def test_snapshot_includes_events_in_snapshot_block():
    assert balances_at(TRANSFERS, 6) == {A: 70, B: 20, C: 10}
    assert delegates_at(DELEGATIONS, 6) == {A: A, B: C}


def test_replay_matches_direct_computation():
    blocks = [0, 1, 2, 5, 6, 8, 9, 20]
    for b, bal, dels in replay_snapshots(TRANSFERS, DELEGATIONS, blocks):
        assert {a: v for a, v in bal.items() if v} == balances_at(TRANSFERS, b)
        assert dels == delegates_at(DELEGATIONS, b)
