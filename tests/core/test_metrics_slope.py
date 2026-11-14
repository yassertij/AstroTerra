"""Slope checked against analytic values on SYNTHETIC surfaces."""

import numpy as np
import pytest

from paf_core.errors import MetricError
from paf_core.provenance import DatasetRecord
from paf_core.raster import GeoGrid, Raster
from paf_core.metrics import slope_degrees, slope_stats

R = 3396000.0
RES = 128


def make(z, lat_top=0.0):
    rows, cols = z.shape
    g = GeoGrid(body="MARS", radius_m=R, lat_top=lat_top, lon_west=90.0, deg_per_pixel=1 / RES, rows=rows, cols=cols)
    rec = DatasetRecord(product_id="SYNTHETIC", data_set_id="SYNTHETIC", product_version="0", body="MARS", is_synthetic=True)
    return Raster(data=z.astype(float), grid=g, record=rec)


def north_distance(g):
    return (R * np.radians(g.row_center_lats()))[:, None] * np.ones((1, g.cols))


def test_flat_surface_zero():
    s = slope_degrees(make(np.full((20, 20), -4500.0)))
    assert np.nanmax(s) == 0.0


@pytest.mark.parametrize("gradient", [0.01, 0.1, 1.0])
def test_north_tilted_plane_matches_analytic(gradient):
    r = make(np.zeros((30, 30)), lat_top=-5.0)
    r.data = gradient * north_distance(r.grid)
    s = slope_degrees(r)
    np.testing.assert_allclose(s[1:-1, 1:-1], np.degrees(np.arctan(gradient)), rtol=1e-9)


def test_east_gradient_accounts_for_latitude():
    # z = c * lon (radians) depends on longitude only, so dz/dy = 0 and
    # dz/dx = c / (R cos(lat)) exactly: slope must grow toward the pole.
    c = 50000.0
    r = make(np.zeros((30, 30)), lat_top=-40.0)
    g = r.grid
    lon_rad = np.radians(g.lon_west + (np.arange(g.cols) + 0.5) * g.deg_per_pixel)
    r.data = c * np.ones((g.rows, 1)) * lon_rad[None, :]
    s = slope_degrees(r)
    expected = np.degrees(np.arctan(c / (R * np.cos(np.radians(g.row_center_lats())))))
    np.testing.assert_allclose(s[1:-1, 1:-1], np.repeat(expected[1:-1, None], g.cols - 2, axis=1), rtol=1e-9)


def test_edges_and_gaps_are_nan_not_filled():
    z = np.zeros((10, 10))
    z[5, 5] = np.nan
    s = slope_degrees(make(z))
    assert np.isnan(s[0]).all() and np.isnan(s[:, -1]).all()
    for rr, cc in [(4, 5), (6, 5), (5, 4), (5, 6)]:
        assert np.isnan(s[rr, cc])
    assert s[5, 5] == 0.0 or np.isnan(s[5, 5])  # centre uses neighbours only
    assert s[2, 2] == 0.0


def test_stats_and_insufficient_data():
    r = make(np.zeros((30, 30)))
    r.data = 0.1 * north_distance(r.grid)
    st = slope_stats(r)
    assert st.units == "degree"
    assert st.median == pytest.approx(np.degrees(np.arctan(0.1)))
    assert st.n_valid == 28 * 28
    assert st.pixel_spacing_m["dy_min"] == pytest.approx(R * np.radians(1 / RES))
    with pytest.raises(MetricError):
        slope_stats(make(np.full((5, 5), np.nan)))
    with pytest.raises(MetricError):
        slope_degrees(make(np.zeros((2, 10))))
