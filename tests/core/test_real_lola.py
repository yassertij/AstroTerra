"""Tests on the REAL LOLA files (skipped when not downloaded; see README "Moon: LOLA LDEM_64").

data/raw/lola_gdr/ldem_64.{lbl,img}            - product used for analysis
data/raw/lola_crosscheck/ldem_16.{lbl,img}      - independent coarser grid of the same data set,
                                                   used only to cross-check registration and scaling
"""

from pathlib import Path

import numpy as np
import pytest

from paf_core.metrics import terrain_metrics
from paf_core.sources import lola_gdr

ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"
L64 = ROOT / "lola_gdr" / "ldem_64.lbl"
L16 = ROOT / "lola_crosscheck" / "ldem_16.lbl"

need64 = pytest.mark.skipif(not (L64.exists() and (L64.parent / "ldem_64.img").exists()), reason="LDEM_64 not downloaded")
need16 = pytest.mark.skipif(not (L16.exists() and (L16.parent / "ldem_16.img").exists()), reason="LDEM_16 not downloaded")

# Label MINIMUM/MAXIMUM DN x SCALING_FACTOR (ldem_64.lbl: MINIMUM = -18251, MAXIMUM = 21546).
H_MIN, H_MAX = -18251 * 0.5, 21546 * 0.5


@need64
def test_real_ldem64_label_and_size():
    p = lola_gdr.open_lola(L64)
    assert p.record.product_id == "LDEM_64" and p.record.product_version == "V3.1"
    assert (p.lines, p.samples) == (11520, 23040) and p.image_path.stat().st_size == 530_841_600
    assert p.global_longitude and p.grid.radius_m == 1737400.0
    assert p.grid.dy_m()[0] == pytest.approx(473.802, abs=0.01)  # label MAP_SCALE


@need64
@pytest.mark.parametrize("lat, lon", [(20.19, 30.77), (-43.3, 348.6), (0.0, 0.0), (60.0, 200.0)])
def test_real_heights_within_label_range_and_metrics_compute(lat, lon):
    p = lola_gdr.open_lola(L64)
    r = lola_gdr.read_window(p, *lola_gdr.window_from_center_km(p, lat, lon, 40.0))
    assert np.isfinite(r.data).all()  # no missing constant: every cell has a value
    assert H_MIN <= r.data.min() and r.data.max() <= H_MAX
    tm = terrain_metrics(r)
    assert 0.0 <= tm.slope.median < 45.0 and len(tm.windows) == 3


@need64
@need16
def test_ldem64_block_mean_reproduces_ldem16():
    """Independent check of georegistration and DN scaling: a 4 x 4 block mean of LDEM_64
    should match LDEM_16 (same data set and version, coarser grid). A one-pixel shift or a
    wrong scale/offset gives errors of hundreds of metres to megametres."""
    p64, p16 = lola_gdr.open_lola(L64), lola_gdr.open_lola(L16)
    rng = np.random.default_rng(1)
    for _ in range(6):
        # corners on LDEM_16 pixel edges (multiples of 1/16 deg) so both reads cover the same area
        lat0 = float(np.round(rng.uniform(-60, 55) * 16) / 16)
        lon0 = float(np.round(rng.uniform(0, 355) * 16) / 16)
        a = lola_gdr.read_window(p64, lat0, lat0 + 4, lon0, lon0 + 4).data  # 256 x 256
        b = lola_gdr.read_window(p16, lat0, lat0 + 4, lon0, lon0 + 4).data  # 64 x 64
        n = b.shape[0]
        agg = a[: 4 * n, : 4 * n].reshape(n, 4, n, 4).mean(axis=(1, 3))
        diff = agg - b
        assert np.median(np.abs(diff)) < 30.0, (lat0, lon0, np.median(np.abs(diff)))
        # Shifting by one LDEM_16 pixel must be clearly worse than no shift.
        shifted = np.median(np.abs(agg[1:, :] - b[:-1, :]))
        assert shifted > 1.5 * np.median(np.abs(diff)), (lat0, lon0)
