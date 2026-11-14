"""Checks against the REAL MOLA MEGDR tile in data/raw/ (skipped when it is not present).

Expected MD5s come from the volume checksum file mgsl_300x_201204.md5 (PDS Geosciences Node).
"""

from pathlib import Path

import numpy as np
import pytest

from paf_core.metrics import slope_stats
from paf_core.provenance import verify_md5
from paf_core.sources.mola_megdr import open_megdr, read_window, window_from_center_km

RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "mola_megdr"
LBL, IMG = RAW / "megt00n090hb.lbl", RAW / "megt00n090hb.img"
MD5 = {LBL: "3EA548315445CDEE09B54FCBBC722E14", IMG: "1F2C70C407976DD22E79DFBB3469EBF1"}

pytestmark = pytest.mark.skipif(not IMG.exists(), reason="real MEGDR tile not downloaded")


def test_checksums_match_archive():
    for path, expected in MD5.items():
        assert verify_md5(path, expected), f"{path.name} MD5 mismatch - re-download"


def test_real_tile_validates_and_reads_gale_window():
    p = open_megdr(LBL)
    assert (p.lines, p.samples) == (5632, 11520)
    assert p.grid.radius_m == 3396000.0
    r = read_window(p, *window_from_center_km(p, -5.4, 137.8, 100.0))
    assert r.valid_fraction == 1.0  # MEGDR declares no nodata value
    # Label: dataset-wide topography range is -8208 .. 21249 m.
    assert -8208 <= np.nanmin(r.data) and np.nanmax(r.data) <= 21249
    st = slope_stats(r)
    assert 0.0 <= st.median < 90.0
