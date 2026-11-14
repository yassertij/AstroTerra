"""Aggregation and window metrics on SYNTHETIC surfaces with known answers."""

import numpy as np
import pytest

from paf_core.errors import MetricError, RasterValidationError
from paf_core.metrics import terrain_metrics, window_metrics
from paf_core.provenance import DatasetRecord
from paf_core.raster import GeoGrid, Raster
from paf_core.resample import aggregate_to_spacing, native_spacing_m, resolution_comparison

S = 1 / 3600


def earth(z, fill=None, lat_top=38.6):
    g = GeoGrid(body="EARTH", radius_m=6378137.0, lat_top=lat_top, lon_west=-110.9, deg_per_pixel=S,
                rows=z.shape[0], cols=z.shape[1], ellipsoid="WGS84")
    rec = DatasetRecord(product_id="SYNTHETIC", data_set_id="SYNTHETIC", product_version="0", body="EARTH", is_synthetic=True)
    return Raster(data=z.astype(float), grid=g, record=rec, fill_fraction=fill)


def mars(z, res=128):
    g = GeoGrid(body="MARS", radius_m=3396000.0, lat_top=-5.0, lon_west=137.0, deg_per_pixel=1 / res, rows=z.shape[0], cols=z.shape[1])
    rec = DatasetRecord(product_id="SYNTHETIC", data_set_id="SYNTHETIC", product_version="0", body="MARS", is_synthetic=True)
    return Raster(data=z.astype(float), grid=g, record=rec)


def test_block_mean_nan_and_fill():
    z = np.arange(60 * 60, dtype=float).reshape(60, 60)
    z[0, 0] = np.nan
    fill = np.zeros((60, 60))
    fill[:15, :19] = 1.0
    r = aggregate_to_spacing(earth(z, fill), 463.0)
    fy, fx = r.record.processing_history[-1].parameters["factor_rows"], r.record.processing_history[-1].parameters["factor_cols"]
    assert (fy, fx) == (15, 19)  # ~30.8 m and ~24.2 m pixels at 38.6 N
    assert np.isnan(r.data[0, 0])
    assert r.data[1, 1] == pytest.approx(z[15:30, 19:38].mean())
    assert r.fill_fraction[0, 0] == 1.0 and r.fill_fraction[1, 1] == 0.0
    assert "adds no information" in r.record.processing_history[-1].note
    sp = r.record.processing_history[-1].parameters["achieved_spacing_m"]
    assert sp["dy"] == pytest.approx(463, rel=0.01) and sp["dx"] == pytest.approx(463, rel=0.03)


def test_no_upsampling():
    with pytest.raises(RasterValidationError, match="upsampling"):
        aggregate_to_spacing(earth(np.zeros((30, 30))), 20.0)


def test_resolution_mismatch_flag():
    cmp = resolution_comparison(earth(np.zeros((10, 10))), mars(np.zeros((10, 10))))
    assert cmp["strong_mismatch"] and cmp["common_spacing_m"] == pytest.approx(native_spacing_m(mars(np.zeros((10, 10)))))


def ramp(r, gx, gy):
    g = r.grid
    y = -np.concatenate([[0.0], np.cumsum(g.dy_m()[:-1])])[:, None]
    x = np.arange(g.cols)[None, :] * g.dx_m()[:, None]
    return 100.0 + gx * x + gy * y


def test_plane_has_zero_roughness_and_known_relief():
    r = mars(np.zeros((44, 44)))
    r.data = ramp(r, 0.0, 0.02)  # 2 % slope north-south only
    w = window_metrics(r, 5000.0)
    ky = w.window_px[0]
    assert w.roughness_m_median == pytest.approx(0.0, abs=1e-6)
    assert w.local_relief_m_median == pytest.approx(0.02 * (ky - 1) * r.grid.dy_m()[0], rel=1e-9)


def test_controlled_roughness():
    rng = np.random.default_rng(0)
    r = mars(np.zeros((220, 220)))
    r.data = ramp(r, 0.01, -0.03) + rng.normal(0, 25.0, (220, 220))
    w = window_metrics(r, 10000.0)
    assert w.roughness_m_median == pytest.approx(25.0, rel=0.1)


def test_sparse_windows_rejected_and_too_small_window():
    z = np.zeros((44, 44))
    z[:, :22] = np.nan
    w = window_metrics(mars(z), 5000.0)
    assert w.n_windows_rejected > 0 and w.n_windows_used > 0
    with pytest.raises(MetricError, match="pixels"):
        window_metrics(mars(np.zeros((44, 44))), 1000.0)  # 1 km ~ 2 MOLA pixels


def test_terrain_metrics_records_unavailable_windows():
    rng = np.random.default_rng(1)
    m = terrain_metrics(mars(rng.normal(0, 10, (60, 60))), windows_m=(1000.0, 5000.0))
    assert [w.window_m for w in m.windows] == [5000.0]
    assert any("window_1km_unavailable" in f for f in m.flags)
    assert m.fill_fraction is None and "not comparable" in m.elevation_note
