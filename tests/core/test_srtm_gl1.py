import numpy as np
import pytest
from pyproj import Geod

from paf_core.errors import RasterValidationError
from paf_core.sources.srtm_gl1 import (
    TileId, classify_num, coverage_status, granule_urls, open_srtm_tile, read_window, tile_in_coverage,
)

from .srtm_fixture import N, write_tile

S = 1 / 3600


@pytest.fixture(scope="module")
def tile(tmp_path_factory):
    d = tmp_path_factory.mktemp("srtm")
    rows = np.arange(N, dtype=np.int32)[:, None]
    cols = np.arange(N, dtype=np.int32)[None, :]
    hgt = ((rows * 7 + cols * 3) % 4000 + 1000).astype(np.int16)
    num = np.full((N, N), 203, dtype=np.uint8)
    num[100:110, 200:220] = 125   # ASTER fill
    num[100:110, 220:230] = 51    # NED fill
    num[0:5, 0:5] = 2             # water-masked
    hz, nz = write_tile(d / "raw", hgt=hgt, num=num)
    return open_srtm_tile(hz, nz, d / "work"), hgt


def test_pixel_centre_registration(tile):
    t, _ = tile
    g = t.grid
    assert g.lat_top == pytest.approx(39 + S / 2) and g.lon_west == pytest.approx(-111 - S / 2)
    assert g.lat_bottom == pytest.approx(38 - S / 2) and g.lon_east == pytest.approx(-110 + S / 2)
    # Pixel (1800, 1800) is centred on 38.5 N, 110.5 W.
    assert g.row_center_lats()[1800] == pytest.approx(38.5)


def test_window_values_and_provenance(tile):
    t, hgt = tile
    # Pixels centred 38.5 N .. 38.5 N + 9 s (rows 1791..1800) and 110.5 W .. +9 s (cols 1800..1809).
    r = read_window(t, 38.5 - S / 2, 38.5 + 9.5 * S, -110.5 - S / 2, -110.5 + 9.5 * S)
    assert r.data.shape == (10, 10)
    np.testing.assert_array_equal(r.data, hgt[1791:1801, 1800:1810].astype(float))
    assert r.grid.lat_top == pytest.approx(38.5 + 9.5 * S)
    assert r.record.data_set_id == "SRTMGL1.003"
    assert "EGM96" in r.record.vertical_reference
    assert r.record.processing_history[-1].operation == "crop"


def test_num_fill_and_water(tile):
    t, _ = tile
    r = read_window(t, t.grid.lat_top - 120 * S, t.grid.lat_top, t.grid.lon_west, t.grid.lon_west + 240 * S)
    assert r.fill_fraction[100:110, 200:230].all()
    assert r.fill_fraction.sum() == 300
    assert np.isnan(r.data[0:5, 0:5]).all()  # water excluded
    fr = r.record.processing_history[-1].parameters["source_fractions"]
    assert fr["fill_fraction"] == pytest.approx(300 / (120 * 240))
    assert fr["water_fraction"] == pytest.approx(25 / (120 * 240))
    keep = read_window(t, t.grid.lat_top - 10 * S, t.grid.lat_top, t.grid.lon_west, t.grid.lon_west + 10 * S, exclude_water=False)
    assert np.isfinite(keep.data).all()


def test_classify_num_table():
    codes = np.array([1, 2, 5, 11, 21, 25, 31, 51, 52, 53, 72, 101, 200, 201, 224, 3, 250], dtype=np.uint8)
    c = classify_num(codes)
    assert c["water"].tolist() == [True] * 3 + [False] * 12 + [True, False]
    assert c["srtm"].tolist() == [False] * 13 + [True, True, False, False]
    assert c["fill"][3:13].all() and not c["fill"][13:].any()
    assert c["unknown"].tolist() == [False] * 16 + [True]


def test_unknown_num_code_rejected(tmp_path):
    num = np.full((N, N), 203, dtype=np.uint8)
    num[0, 0] = 250
    t = open_srtm_tile(*write_tile(tmp_path / "raw", num=num), tmp_path / "work")
    with pytest.raises(RasterValidationError, match="250"):
        read_window(t, t.grid.lat_top - 5 * S, t.grid.lat_top, t.grid.lon_west, t.grid.lon_west + 5 * S)


def test_missing_num_flagged_not_silent(tmp_path):
    hz, _ = write_tile(tmp_path / "raw", with_num=False)
    t = open_srtm_tile(hz, None, tmp_path / "work")
    assert any("num_file_missing" in f for f in t.record.quality_flags)
    r = read_window(t, 38.4, 38.5, -110.6, -110.5)
    assert r.fill_fraction is None
    assert any("void_fill_fraction_unknown" in f for f in r.record.quality_flags)


def test_void_value_is_nodata(tmp_path):
    hgt = np.zeros((N, N), dtype=np.int16)
    hgt[1800, 1800] = -32768
    t = open_srtm_tile(*write_tile(tmp_path / "raw", hgt=hgt), tmp_path / "work")
    r = read_window(t, 38.5 - S / 2, 38.5 + S / 2, -110.5 - S / 2, -110.5 + S / 2)
    assert r.data.shape == (1, 1) and np.isnan(r.data[0, 0])


def test_wrong_size_rejected(tmp_path):
    hz, nz = write_tile(tmp_path / "raw", hgt_bytes=b"\x00" * 1000)
    with pytest.raises(RasterValidationError, match="bytes"):
        open_srtm_tile(hz, nz, tmp_path / "work")


def test_corrupt_zip_rejected(tmp_path):
    hz, nz = write_tile(tmp_path / "raw")
    hz.write_bytes(hz.read_bytes()[:500])
    with pytest.raises(RasterValidationError, match="zip"):
        open_srtm_tile(hz, nz, tmp_path / "work")


def test_mismatched_num_rejected(tmp_path):
    hz, _ = write_tile(tmp_path / "a")
    _, nz = write_tile(tmp_path / "b", name="N37W111")
    with pytest.raises(RasterValidationError, match="does not belong"):
        open_srtm_tile(hz, nz, tmp_path / "work")


@pytest.mark.parametrize("name, inside", [("N38W111", True), ("N59W111", True), ("N60W111", False), ("S56W070", True), ("S57W070", False)])
def test_tile_coverage(name, inside):
    assert tile_in_coverage(TileId.parse(name)) is inside


def test_outside_coverage_tile_reported(tmp_path):
    hz, nz = write_tile(tmp_path / "raw", name="N75W090")  # Devon Island area
    with pytest.raises(RasterValidationError, match="outside SRTM coverage"):
        open_srtm_tile(hz, nz, tmp_path / "work")


@pytest.mark.parametrize("lat, status", [(60.0, "inside"), (60.01, "outside_coverage"), (-56.0, "inside"), (-56.01, "outside_coverage"), (0, "inside")])
def test_point_coverage(lat, status):
    assert coverage_status(lat) == status


def test_tile_naming_and_urls():
    t = TileId.containing(38.4, -110.8)
    assert t.name == "N38W111"
    assert TileId.containing(-0.5, 0.5).name == "S01E000"
    u = granule_urls(t)
    assert u["hgt"].endswith("SRTMGL1.003/N38W111.SRTMGL1.hgt/N38W111.SRTMGL1.hgt.zip")
    assert u["num"].endswith("SRTMGL1N.003/N38W111.SRTMGL1N.num/N38W111.SRTMGL1N.num.zip")


def test_wgs84_spacing_matches_independent_geodesic(tile):
    t, _ = tile
    g = t.grid
    dy, dx = g.dy_m()[1800], g.dx_m()[1800]
    geod = Geod(ellps="WGS84")
    assert dy == pytest.approx(geod.line_length([0, 0], [38.5 - S / 2, 38.5 + S / 2]), rel=1e-9)
    assert 30.7 < dy < 31.0 and 24.0 < dx < 24.5
