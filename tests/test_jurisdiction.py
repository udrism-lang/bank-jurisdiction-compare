"""Tests: the dataset is well-formed, scoring is deterministic, Monte Carlo shares add up."""
from dataclasses import replace
from pathlib import Path

import pytest

from jurisdiction.robustness import monte_carlo, score_uncertainty, weight_thresholds
from jurisdiction.score import load, rank, totals, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ds():
    return load(ROOT / "data" / "jurisdictions.yaml")


def test_dataset_is_valid(ds):
    assert validate(ds) == []


def test_weights_sum_to_one(ds):
    assert sum(c.weight for c in ds.criteria) == pytest.approx(1.0)


def test_every_score_has_source_or_needs_check(ds):
    for (crit, code), s in ds.scores.items():
        assert s.sources or s.needs_check, f"{crit}/{code}"
        assert s.last_checked, f"{crit}/{code} has no last_checked date"


def test_scores_are_integers_1_to_5(ds):
    for (crit, code), s in ds.scores.items():
        assert isinstance(s.value, int) and 1 <= s.value <= 5, f"{crit}/{code}: {s.value}"


def test_every_country_scored_on_every_criterion(ds):
    assert len(ds.scores) == len(ds.criteria) * len(ds.countries)


def test_ranking_is_deterministic(ds):
    assert rank(ds) == rank(ds)
    assert [c for c, _ in rank(ds)] == [c for c, _ in rank(load(ROOT / "data" / "jurisdictions.yaml"))]


def test_ties_broken_by_country_code(ds):
    flat = {c.key: 1.0 for c in ds.criteria}
    same = replace(ds, scores={k: replace(s, value=3) for k, s in ds.scores.items()})
    assert [c for c, _ in rank(same, flat)] == sorted(n.code for n in ds.countries)


def test_totals_stay_on_score_scale(ds):
    assert all(1 <= v <= 5 for v in totals(ds).values())


def test_monte_carlo_shares_sum_to_100_percent(ds):
    mc = monte_carlo(ds, iterations=500)
    assert sum(mc.values()) == pytest.approx(1.0)
    assert set(mc) == {n.code for n in ds.countries}


def test_monte_carlo_is_reproducible(ds):
    assert monte_carlo(ds, iterations=300, seed=7) == monte_carlo(ds, iterations=300, seed=7)


def test_score_uncertainty_shares_sum_and_reproduce(ds):
    a = score_uncertainty(ds, iterations=300, seed=7)
    assert sum(a.values()) == pytest.approx(1.0)
    assert set(a) == {n.code for n in ds.countries}
    assert a == score_uncertainty(ds, iterations=300, seed=7)


def test_score_uncertainty_clear_leader_always_wins(ds):
    """A leader scoring 5 everywhere against rivals scoring 1 stays first after any one-point noise."""
    top = rank(ds)[0][0]
    strong = replace(ds, scores={k: replace(s, value=5 if k[1] == top else 1) for k, s in ds.scores.items()})
    assert score_uncertainty(strong, iterations=200)[top] == 1.0


def test_validate_catches_bad_data(ds):
    key = next(iter(ds.scores))
    bad = replace(ds, scores={**ds.scores, key: replace(ds.scores[key], value=7, sources=(), needs_check=False)})
    errors = validate(bad)
    assert any("not an integer" in e for e in errors)
    assert any("no source" in e for e in errors)


def test_threshold_actually_flips_leader(ds):
    from jurisdiction.robustness import _reweight

    leader = rank(ds)[0][0]
    for t in weight_thresholds(ds, steps=200):
        if t["threshold"] is not None:
            assert rank(ds, _reweight(ds, t["criterion"], t["threshold"]))[0][0] == t["new_leader"] != leader


def test_tie_does_not_count_as_overtaking(ds):
    """A criterion where every country scores the same can never change the leader."""
    flat = {k: (replace(s, value=4) if k[0] == "market_access" else s) for k, s in ds.scores.items()}
    rows = {t["criterion"]: t for t in weight_thresholds(replace(ds, scores=flat), steps=100)}
    assert rows["market_access"]["threshold"] is None


def test_tied_ranks_are_shown_with_equals_sign():
    from jurisdiction.report import rank_labels

    labels = rank_labels([("LT", 4.15), ("LV", 3.55), ("IE", 3.3), ("EE", 2.85), ("NL", 2.85)])
    assert labels == {"LT": "1", "LV": "2", "IE": "3", "EE": "4=", "NL": "4="}
