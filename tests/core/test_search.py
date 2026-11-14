"""End-to-end search on SYNTHETIC MEGDR + SRTM fixtures (plumbing, coverage, sensitivity)."""

import json

import numpy as np
import pytest

from paf_core.search import analyze_mars_target

from .megdr_fixture import RES, write_megdr
from .srtm_fixture import N, write_tile


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    d = tmp_path_factory.mktemp("e2e")
    rng = np.random.default_rng(7)
    mars = np.cumsum(rng.normal(0, 20, (RES, RES)), axis=0).astype(np.int16)
    (d / "mola").mkdir()
    lbl = write_megdr(d / "mola", mars)
    earth = (1500 + np.cumsum(rng.normal(0, 3, (N, N)), axis=1)).astype(np.int16)
    num = np.full((N, N), 203, dtype=np.uint8)
    num[:600, :600] = 120  # ASTER fill in the NW corner: ~17 % of the first 40 km patch
    write_tile(d / "srtm", hgt=earth, num=num)
    return analyze_mars_target(
        lbl, -0.5, 90.5, ["N38W111", "N75W090", "N37W111", "BAD"], d / "srtm", d / "work",
        patch_km=40, stride_km=10,
    )


def test_coverage_report_is_exact(result):
    c = result.coverage
    assert c.tiles_examined == ["N38W111"]
    assert c.tiles_outside_coverage == ["N75W090"]
    assert "N37W111" in c.tiles_unavailable
    assert "BAD" in c.tiles_failed
    assert "not global" in c.note


def test_ranking_complete_and_sorted(result):
    ranked = [r for r in result.ranking.results if not r.excluded]
    assert len(ranked) >= 3
    assert [r.rank for r in ranked] == list(range(1, len(ranked) + 1))
    assert all(a.distance <= b.distance for a, b in zip(ranked, ranked[1:]))
    for r in ranked:
        assert set(r.contributions) == set(result.ranking.features_used)
        assert "fill_excluded_rank" in r.sensitivity
        assert r.native_spacing_m < 40 and 400 < r.analysis_spacing_m < 520
        e = r.elevation_m
        assert e and e["min"] <= e["mean"] <= e["max"] and e["std"] >= 0


def test_fill_heavy_patch_is_excluded(result):
    nw = next(r for r in result.ranking.results if r.candidate_id.endswith("_r0_c0"))
    assert nw.fill_fraction > 0.05 and nw.excluded


def test_result_serialises_with_limitations(result):
    js = json.loads(result.model_dump_json())
    assert js["disclaimer"].startswith("Topographic analog assessment only")
    assert any("not a probability" in x for x in js["limitations"])
    assert js["target_record"]["data_set_id"] == "MGS-M-MOLA-5-MEGDR-L3-V1.0"
