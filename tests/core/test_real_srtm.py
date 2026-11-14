"""Checks against the REAL SRTMGL1 v3 tile N38W111 in data/raw/srtm (skipped if absent).

LP DAAC publishes no checksum for these granules; the MD5s below are of the files as
downloaded on 2026-11-13 and only guard against local corruption or replacement.
"""

from pathlib import Path

import numpy as np
import pytest

from paf_core.metrics import terrain_metrics
from paf_core.provenance import verify_md5
from paf_core.resample import aggregate_to_spacing
from paf_core.sources.srtm_gl1 import classify_num, open_srtm_tile, read_window

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "srtm"
HGT, NUM = RAW / "N38W111.SRTMGL1.hgt.zip", RAW / "N38W111.SRTMGL1N.num.zip"
LOCAL_MD5 = {HGT: "93525F7299231DA1D003AE77DFBC5B33", NUM: "8779DE6CE6555351C7A88EA5F6D975B2"}

pytestmark = pytest.mark.skipif(not (HGT.exists() and NUM.exists()), reason="real SRTM tile not downloaded")


@pytest.fixture(scope="module")
def tile():
    return open_srtm_tile(HGT, NUM, ROOT / "data" / "processed" / "srtm")


def test_files_unchanged_since_download():
    for path, md5 in LOCAL_MD5.items():
        assert verify_md5(path, md5), f"{path.name} changed since download"


def test_every_num_code_is_documented(tile):
    num = np.fromfile(tile.num_path, dtype=np.uint8)
    assert not classify_num(num)["unknown"].any()


def test_window_and_metrics_on_common_grid(tile):
    r = read_window(tile, 38.05, 38.95, -110.95, -110.05)
    assert r.data.shape == (3241, 3241)
    assert 0.99 < r.valid_fraction <= 1.0  # water-masked pixels removed
    assert 0.0 < float(np.mean(r.fill_fraction)) < 0.05
    a = aggregate_to_spacing(r, 462.0)
    sp = a.record.processing_history[-1].parameters["achieved_spacing_m"]
    assert sp["dy"] == pytest.approx(462, rel=0.02) and sp["dx"] == pytest.approx(462, rel=0.02)
    m = terrain_metrics(a)
    assert [w.window_m for w in m.windows] == [5000.0, 10000.0, 20000.0]
    assert m.fill_fraction is not None and m.slope.median > 0
