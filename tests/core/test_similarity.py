"""Ranking maths on hand-built feature vectors (no rasters)."""

import math

import pytest

from paf_core.errors import MetricError
from paf_core.similarity import FEATURES, MAD_TO_SIGMA, Candidate, rank_candidates


def cand(cid, feats, valid=1.0, fill=0.0):
    return Candidate(candidate_id=cid, tile="N38W111", region={}, features=feats, valid_fraction=valid,
                     fill_fraction=fill, native_spacing_m=27.0, analysis_spacing_m=462.0)


def feats(x):
    return {f: float(x + i) for i, f in enumerate(FEATURES)}


def pool():
    return [cand("a", feats(0)), cand("b", feats(10)), cand("c", feats(20)), cand("d", feats(30))]


def test_identical_region_scores_zero_and_ranks_first():
    r = rank_candidates(feats(10), pool())
    best = r.results[0]
    assert best.candidate_id == "b" and best.rank == 1 and best.distance == 0.0
    assert all(v == 0.0 for v in best.feature_differences.values())


def test_distance_matches_hand_computation():
    # Every feature: values offset by 0,10,20,30 -> median 15, MAD = 10, scale = 1.4826*10.
    r = rank_candidates(feats(5), pool())
    a = next(x for x in r.results if x.candidate_id == "a")
    z = 5 / (MAD_TO_SIGMA * 10)
    assert a.distance == pytest.approx(math.sqrt(z * z))  # equal weights, same z for all features
    assert r.normalization["slope_median_deg"]["scale_1.4826MAD"] == pytest.approx(MAD_TO_SIGMA * 10)
    assert sum(a.contributions.values()) == pytest.approx(1.0)
    assert "not a probability" in r.score_meaning.lower()


def test_weights_change_contributions_and_are_normalised():
    w = {f: (3.0 if f == "slope_median_deg" else 1.0) for f in FEATURES}
    t = feats(10)
    t["slope_median_deg"] += 5
    r = rank_candidates(t, pool(), w)
    assert sum(r.weights.values()) == pytest.approx(1.0)
    b = next(x for x in r.results if x.candidate_id == "b")
    assert b.contributions["slope_median_deg"] == pytest.approx(1.0)
    with pytest.raises(MetricError):
        rank_candidates(t, pool(), {f: -1.0 for f in FEATURES})


@pytest.mark.parametrize("kw, reason", [
    ({"valid": 0.5}, "valid fraction"),
    ({"fill": 0.2}, "fill fraction"),
    ({"fill": None}, "unknown"),
])
def test_exclusions_are_recorded(kw, reason):
    r = rank_candidates(feats(10), pool() + [cand("x", feats(10), **kw)])
    x = next(v for v in r.results if v.candidate_id == "x")
    assert x.excluded and x.rank is None and x.distance is None
    assert any(reason in m for m in x.exclusion_reasons)


def test_missing_feature_excludes_candidate():
    f = feats(10)
    del f["relief_20km_m"]
    r = rank_candidates(feats(10), pool() + [cand("x", f)])
    assert next(v for v in r.results if v.candidate_id == "x").excluded


def test_zero_mad_feature_dropped_not_substituted():
    cs = pool()
    for c in cs:
        c.features["slope_median_deg"] = 2.0
    r = rank_candidates(feats(10), cs)
    assert "slope_median_deg" in r.features_dropped and "slope_median_deg" not in r.features_used


def test_too_few_candidates_is_an_error():
    with pytest.raises(MetricError, match="eligible"):
        rank_candidates(feats(0), pool()[:2])


def test_sensitivity_is_seeded_and_reports_stability():
    r1 = rank_candidates(feats(10), pool())
    r2 = rank_candidates(feats(10), pool())
    assert [x.sensitivity for x in r1.results] == [x.sensitivity for x in r2.results]
    b = r1.results[0]
    assert b.sensitivity["top1_fraction"] == 1.0 and b.sensitivity["rank_p95"] == 1
