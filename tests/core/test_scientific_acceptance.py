"""Scientific acceptance cases from the project brief, on SYNTHETIC rasters with known answers.

Each test names the property it demonstrates. None of these values are real findings.
"""

import numpy as np
import pytest

from paf_core.metrics import slope_degrees, terrain_metrics, window_metrics
from paf_core.provenance import DatasetRecord
from paf_core.raster import GeoGrid, Raster
from paf_core.resample import aggregate_to_spacing
from paf_core.search import MAX_SPACING_MISMATCH, check_grid_compatibility
from paf_core.similarity import FEATURES, Candidate, features_from_metrics, rank_candidates
from paf_core.errors import RasterValidationError


def body_raster(z, body="MARS", res=128, radius=3396000.0, lat_top=-5.0):
    g = GeoGrid(body=body, radius_m=radius, lat_top=lat_top, lon_west=137.0, deg_per_pixel=1 / res,
                rows=z.shape[0], cols=z.shape[1])
    rec = DatasetRecord(product_id="SYNTHETIC", data_set_id="SYNTHETIC", product_version="0", body=body, is_synthetic=True)
    return Raster(data=z.astype(float), grid=g, record=rec)


def test_flat_terrain_has_zero_slope_relief_and_roughness():
    tm = terrain_metrics(body_raster(np.full((100, 100), 1234.0)))
    assert tm.slope.median == pytest.approx(0.0, abs=1e-12)
    for w in tm.windows:
        assert w.local_relief_m_median == pytest.approx(0.0, abs=1e-9)
        assert w.roughness_m_median == pytest.approx(0.0, abs=1e-9)


def test_plane_gives_predictable_slope_on_the_moon_grid():
    r = body_raster(np.zeros((60, 60)), body="MOON", res=64, radius=1737400.0, lat_top=0.5)
    dy = r.grid.dy_m()[0]  # 473.8 m per pixel
    z = -np.arange(60)[:, None] * dy * np.tan(np.radians(10.0)) * np.ones((1, 60))  # rises northward at 10 deg
    s = slope_degrees(body_raster(z, body="MOON", res=64, radius=1737400.0, lat_top=0.5))
    assert np.nanmax(np.abs(s[1:-1, 1:-1] - 10.0)) < 1e-9


def test_known_step_gives_known_relief():
    z = np.zeros((100, 100))
    z[:, 50:] = 300.0  # 300 m step running north-south
    w = window_metrics(body_raster(z), 10000.0)  # ~21.6 px windows -> 4 x 4 windows
    # windows that straddle the step have relief 300 m, the others 0; record both counts
    ky, kx = w.window_px
    straddle = sum(1 for b in range(100 // kx) if b * kx < 50 < (b + 1) * kx)
    assert w.n_windows_used == (100 // ky) * (100 // kx)
    expected = np.median([300.0 if b * kx < 50 < (b + 1) * kx else 0.0 for b in range(100 // kx)] * (100 // ky))
    assert w.local_relief_m_median == expected
    assert straddle >= 1


def cand(cid, feats, valid=1.0, fill=0.0):
    return Candidate(candidate_id=cid, tile="N38W111", region={}, features=feats, valid_fraction=valid,
                     fill_fraction=fill, native_spacing_m=27.0, analysis_spacing_m=462.0)


def test_identical_patches_processed_identically_give_zero_distance():
    rng = np.random.default_rng(7)
    z = np.cumsum(rng.normal(0, 15, (120, 120)), axis=0)
    f_target = features_from_metrics(terrain_metrics(body_raster(z)))
    f_same = features_from_metrics(terrain_metrics(body_raster(z.copy())))
    others = [features_from_metrics(terrain_metrics(body_raster(z * k))) for k in (0.3, 2.0, 4.0)]
    rk = rank_candidates(f_target, [cand("same", f_same)] + [cand(f"k{i}", f) for i, f in enumerate(others)])
    best = rk.results[0]
    assert best.candidate_id == "same" and best.distance == 0.0


def test_missing_data_never_improves_a_score():
    base = {f: 10.0 for f in FEATURES}
    target = dict(base)
    # 'gappy' would be a perfect match on the features it has, but it lacks one feature
    # and has a low valid fraction: it must be excluded, never ranked with distance 0.
    gappy = {k: v for k, v in base.items() if k != "relief_20km_m"}
    pool = [cand("gappy", gappy, valid=0.5), cand("a", {f: 20.0 for f in FEATURES}),
            cand("b", {f: 30.0 for f in FEATURES}), cand("c", {f: 15.0 + i for i, f in enumerate(FEATURES)})]
    rk = rank_candidates(target, pool)
    g = next(r for r in rk.results if r.candidate_id == "gappy")
    assert g.excluded and g.rank is None and g.distance is None
    assert any("features unavailable" in x for x in g.exclusion_reasons)
    assert any("valid fraction" in x for x in g.exclusion_reasons)
    assert rk.results[0].candidate_id != "gappy"


def test_no_data_blocks_stay_no_data_after_aggregation():
    z = np.ones((60, 60))
    z[3, 3] = np.nan
    g = GeoGrid(body="EARTH", radius_m=6378137.0, lat_top=38.6, lon_west=-110.9, deg_per_pixel=1 / 3600,
                rows=60, cols=60, ellipsoid="WGS84")
    rec = DatasetRecord(product_id="S", data_set_id="S", product_version="0", body="EARTH", is_synthetic=True)
    agg = aggregate_to_spacing(Raster(data=z, grid=g, record=rec), 463.0)
    assert np.isnan(agg.data[0, 0]) and np.isfinite(agg.data[1, 1])  # never filled by neighbours


def test_incompatible_grid_rejected():
    # Finer target than the Earth source -> upsampling would be needed -> refused.
    g = GeoGrid(body="EARTH", radius_m=6378137.0, lat_top=38.6, lon_west=-110.9, deg_per_pixel=1 / 3600,
                rows=60, cols=60, ellipsoid="WGS84")
    rec = DatasetRecord(product_id="S", data_set_id="S", product_version="0", body="EARTH", is_synthetic=True)
    with pytest.raises(RasterValidationError, match="upsampling"):
        aggregate_to_spacing(Raster(data=np.zeros((60, 60)), grid=g, record=rec), 10.0)
    # Achieved spacing too far from the target spacing -> candidate not compared.
    assert check_grid_compatibility(463.0, 462.0) is None
    assert check_grid_compatibility(463.0, 463.0 * (1 + 2 * MAX_SPACING_MISMATCH)) is not None
