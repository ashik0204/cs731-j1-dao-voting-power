import random

import numpy as np
import pytest

from power.banzhaf import banzhaf, banzhaf_raw
from power.shapley import shapley_shubik
from power.bruteforce import (banzhaf_bruteforce, shapley_bruteforce_subsets,
                              shapley_bruteforce_permutations)
from power.game import quota, integerise

TOL = 1e-9


def test_known_example():
    # Winning coalitions of [51; 50, 30, 20]: {1,2}, {1,3}, {1,2,3}. Player 1 has
    # 3 swings, players 2 and 3 one each, so normalised Banzhaf = (3, 1, 1) / 5.
    # (The brief's (0.50, 0.25, 0.25) is incorrect; see README, Design decisions.)
    w, q = [50, 30, 20], 51
    assert np.allclose(banzhaf(w, q), [0.60, 0.20, 0.20], atol=TOL, rtol=0)
    assert np.allclose(banzhaf_raw(w, q), [0.75, 0.25, 0.25], atol=TOL, rtol=0)
    assert np.allclose(banzhaf_bruteforce(w, q), [0.60, 0.20, 0.20], atol=TOL, rtol=0)
    assert np.allclose(shapley_shubik(w, q), [2 / 3, 1 / 6, 1 / 6], atol=TOL, rtol=0)


@pytest.mark.parametrize("index", [banzhaf, shapley_shubik])
def test_dummy_player_zero_weight(index):
    v = index([50, 30, 20, 0], 51)
    assert v[3] == 0.0


@pytest.mark.parametrize("index", [banzhaf, shapley_shubik])
def test_dummy_player_positive_weight(index):
    # [6; 4, 4, 1]: the weight-1 player never swings.
    assert abs(index([4, 4, 1], 6)[2]) < TOL


@pytest.mark.parametrize("index", [banzhaf, shapley_shubik])
def test_symmetry(index):
    v = index([7, 5, 5, 3, 1], 11)
    assert abs(v[1] - v[2]) < TOL


def test_shapley_efficiency():
    rng = random.Random(1)
    for _ in range(50):
        n = rng.randint(1, 30)
        w = [rng.randint(0, 40) for _ in range(n)]
        if sum(w) == 0:
            continue
        q = rng.randint(1, sum(w))
        assert abs(shapley_shubik(w, q).sum() - 1) < TOL


def test_banzhaf_normalised_sums_to_one():
    v = banzhaf([9, 4, 4, 2, 1], 11)
    assert abs(v.sum() - 1) < TOL


@pytest.mark.parametrize("seed", range(40))
def test_dp_matches_bruteforce(seed):
    rng = random.Random(seed)
    n = rng.randint(1, 12)
    w = [rng.choice([0, 1, 2, 3, 5, 8, 13, 21, 50]) for _ in range(n)]
    q = rng.randint(1, max(1, sum(w)))
    assert np.allclose(banzhaf(w, q), banzhaf_bruteforce(w, q), atol=TOL, rtol=0)
    assert np.allclose(shapley_shubik(w, q), shapley_bruteforce_subsets(w, q), atol=TOL, rtol=0)


@pytest.mark.parametrize("seed", range(10))
def test_shapley_matches_permutation_definition(seed):
    rng = random.Random(100 + seed)
    n = rng.randint(1, 7)
    w = [rng.randint(0, 10) for _ in range(n)]
    q = rng.randint(1, max(1, sum(w)))
    assert np.allclose(shapley_shubik(w, q), shapley_bruteforce_permutations(w, q), atol=TOL, rtol=0)


def test_no_winning_coalition_gives_zero():
    assert banzhaf([1, 2], 10).sum() == 0
    assert shapley_shubik([1, 2], 10).sum() == 0


def test_large_game_runs_and_is_efficient():
    rng = random.Random(7)
    w = [rng.randint(1, 100) for _ in range(150)]
    q = sum(w) // 2 + 1
    phi = shapley_shubik(w, q)
    beta = banzhaf(w, q)
    assert abs(phi.sum() - 1) < 1e-9 and abs(beta.sum() - 1) < 1e-9
    order = np.argsort(w)
    assert np.all(np.diff(phi[order]) >= -1e-12)   # monotone in weight


def test_quota_rule():
    assert quota(100, 0) == 51            # simple majority
    assert quota(101, 0) == 51
    assert quota(100, 70) == 70           # quorum binds
    ints, qu, u = integerise([10.0, 30.0, 60.0], 100, 25.0)
    assert ints == [10, 30, 60] and qu == 25 and u == 1.0
