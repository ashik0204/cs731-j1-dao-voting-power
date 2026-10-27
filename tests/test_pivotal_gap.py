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


def test_nakamoto_and_voters_to_half():
    import pandas as pd
    from analysis.beyond import nakamoto, voters_to_half
    assert nakamoto([50, 30, 20]) == 2          # 50 is not > 50% of 100
    assert nakamoto([51, 30, 19]) == 1
    v = pd.DataFrame({"proposal_id": [1, 1, 1, 2, 2], "votes": [50.0, 30, 20, 10, 10]})
    assert voters_to_half(v).to_dict() == {1: 1, 2: 1}   # >= 50% of votes cast


def test_participation_game_quorum_unreachable():
    import pandas as pd
    from analysis.beyond import participation_games
    props = pd.DataFrame({"proposal_id": [7], "outcome": ["defeated"]})
    votes = pd.DataFrame({"proposal_id": [7, 7], "voter": ["a", "b"], "support": [1, 0], "votes": [100.0, 50.0]})
    g, ind = participation_games(props, votes, quorum=400.0, resolution=1000)
    assert bool(g.no_winning_coalition.iloc[0]) and ind.banzhaf.sum() == 0


def test_gini():
    from analysis.beyond import gini
    assert gini([1, 1, 1, 1]) == pytest.approx(0)
    assert gini([0, 0, 0, 1]) == pytest.approx(0.75)      # (n-1)/n for one holder


def test_fritsch_potential_and_exercised():
    import pandas as pd
    from analysis.beyond import fritsch_power
    props = pd.DataFrame({"proposal_id": [1], "outcome": ["executed"]})
    # for 60 (a) + 10 (b), against 40 (c), quorum 50: passed.
    votes = pd.DataFrame({"proposal_id": [1, 1, 1], "voter": ["a", "b", "c"],
                          "support": [1, 1, 0], "votes": [60.0, 10.0, 40.0]})
    fp = fritsch_power(props, votes, quorum=50.0).set_index("voter")
    assert fp.loc["a", "potential"] and fp.loc["a", "exercised"]       # without a: 10 for < quorum
    assert not fp.loc["b", "potential"]      # switching b: 60 for vs 50 against, still passes
    assert not fp.loc["b", "exercised"]      # removing b: 60 vs 40, still passes
    assert not fp.loc["c", "potential"]      # switching c to for: still passes

