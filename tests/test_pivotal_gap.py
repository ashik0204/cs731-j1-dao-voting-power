import itertools
import random

import numpy as np
import pytest

from power.pivotal import min_flip_set, set_flips, passed
from power.gap import spearman, ranks, game_indices


def brute_min_flip(players, F, A, Q):
    addrs = [p[0] for p in players]
    for k in range(1, len(addrs) + 1):
        for S in itertools.combinations(addrs, k):
            if set_flips(players, F, A, Q, set(S)):
                return k
    return None


@pytest.mark.parametrize("seed", range(200))
def test_min_flip_set_matches_bruteforce(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 8)
    players = [(f"p{i}", float(rng.randint(1, 20)), rng.choice(["for", "against", "none"]))
               for i in range(n)]
    F = sum(p[1] for p in players if p[2] == "for")
    A = sum(p[1] for p in players if p[2] == "against")
    Q = float(rng.randint(0, 60))
    got = min_flip_set(players, F, A, Q)
    want = brute_min_flip(players, F, A, Q)
    if want is None:
        assert got is None
    else:
        assert got is not None and len(got) == want
        assert set_flips(players, F, A, Q, set(got))


def test_flip_example():
    # Passed 60-40 with quorum 50: the single for-voter of weight 60 flips it.
    players = [("a", 60.0, "for"), ("b", 40.0, "against"), ("c", 5.0, "none")]
    assert passed(60, 40, 50)
    assert min_flip_set(players, 60, 40, 50) == ["a"]


def test_spearman():
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1)
    assert spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1)
    assert list(ranks([5, 1, 5, 3])) == [3.5, 1, 3.5, 2]


def test_game_indices_sum_and_dummies():
    w = {"a": 500.0, "b": 300.0, "c": 200.0, "d": 0.001}
    df = game_indices(w, quorum=0.0, resolution=1000).set_index("address")
    assert df.loc["d", "int_weight"] == 0 and df.loc["d", "banzhaf"] == 0
    assert df.banzhaf.sum() == pytest.approx(1) and df.shapley.sum() == pytest.approx(1)
    assert df.loc["a", "shapley"] == pytest.approx(2 / 3)
    assert np.isclose(df.share.sum(), 1)
