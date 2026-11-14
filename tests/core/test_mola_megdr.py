import numpy as np
import pytest

from paf_core.errors import RasterValidationError, UnapprovedSourceError
from paf_core.sources.mola_megdr import open_megdr, read_window, window_from_center_km

from .megdr_fixture import RES, write_megdr


def test_valid_fixture_opens_with_label_geometry(tmp_path):
    p = open_megdr(write_megdr(tmp_path))
    assert p.grid.radius_m == 3396000.0
    assert p.grid.deg_per_pixel == 1 / RES
    assert (p.grid.lat_top, p.grid.lon_west, p.grid.rows, p.grid.cols) == (0.0, 90.0, RES, RES)
    rec = p.record
    assert rec.data_set_id == "MGS-M-MOLA-5-MEGDR-L3-V1.0" and rec.product_version == "2.0"
    assert "areoid" in rec.vertical_reference.lower()
    assert rec.fill_value == "none declared in label"
    assert rec.scale_factor.startswith("not declared")
    # Exported provenance must not leak absolute local paths.
    dumped = rec.model_dump_json()
    assert str(tmp_path) not in dumped and str(tmp_path).replace("\\", "\\\\") not in dumped


def test_big_endian_values_and_window(tmp_path):
    z = (np.arange(RES * RES, dtype=np.int32).reshape(RES, RES) % 3000 - 1500).astype(np.int16)
    p = open_megdr(write_megdr(tmp_path, z))
    # Rows 10..19 (lat -10/128 .. -20/128), cols 5..14.
    r = read_window(p, -20 / RES, -10 / RES, 90 + 5 / RES, 90 + 15 / RES)
    np.testing.assert_array_equal(r.data, z[10:20, 5:15].astype(float))
    assert r.grid.lat_top == pytest.approx(-10 / RES)
    assert r.grid.lon_west == pytest.approx(90 + 5 / RES)
    assert r.record.processing_history[-1].operation == "crop"
    assert "No resampling" in r.record.processing_history[-1].note


def test_window_snaps_outward(tmp_path):
    p = open_megdr(write_megdr(tmp_path))
    # Sub-pixel request inside one pixel -> exactly that pixel.
    r = read_window(p, -0.5 - 0.3 / RES, -0.5, 90 + 25.2 / RES, 90 + 25.7 / RES)
    assert r.data.shape == (1, 1)
    # Request straddling a pixel edge -> both pixels (outward snapping, never dropped).
    r = read_window(p, -0.5 - 0.3 / RES, -0.5, 90 + 25.6 / RES, 90 + 26.1 / RES)
    assert r.data.shape == (1, 2)


def test_window_outside_tile_rejected(tmp_path):
    p = open_megdr(write_megdr(tmp_path))
    with pytest.raises(RasterValidationError, match="outside tile"):
        read_window(p, -0.5, 0.5, 90.1, 90.2)


def test_window_from_center_uses_label_radius(tmp_path):
    p = open_megdr(write_megdr(tmp_path))
    lat0, lat1, lon0, lon1 = window_from_center_km(p, -0.5, 90.5, 10.0)
    km_per_deg = 2 * np.pi * 3396.0 / 360
    assert (lat1 - lat0) * km_per_deg == pytest.approx(10.0)


def test_lowercase_file_found_from_uppercase_label(tmp_path):
    lbl = write_megdr(tmp_path)  # label says MEGT00N090HB.IMG, disk has megt00n090hb.img
    assert open_megdr(lbl).image_path.name == "megt00n090hb.img"


def test_truncated_download_rejected(tmp_path):
    with pytest.raises(RasterValidationError, match="truncated"):
        open_megdr(write_megdr(tmp_path, truncate_bytes=100))


def test_missing_image_rejected(tmp_path):
    lbl = write_megdr(tmp_path)
    (tmp_path / "megt00n090hb.img").unlink()
    with pytest.raises(RasterValidationError, match="not found"):
        open_megdr(lbl)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"PRODUCT_VERSION_ID": '"1.0"'}, "final release"),
        ({"UNIT": "KILOMETER"}, "UNIT"),
        ({"NAME": "PLANETARY_RADIUS"}, "not a topography product"),
        ({"A_AXIS_RADIUS": "3396.0"}, "radius must come from the label"),
        ({"C_AXIS_RADIUS": "3376.2 <KM>"}, "Non-spherical"),
        ({"COORDINATE_SYSTEM_NAME": '"PLANETOGRAPHIC"'}, "PLANETOCENTRIC"),
        ({"POSITIVE_LONGITUDE_DIRECTION": '"WEST"'}, "EAST"),
        ({"MAP_PROJECTION_TYPE": '"POLAR STEREOGRAPHIC"'}, "SIMPLE CYLINDRICAL"),
        ({"SAMPLE_PROJECTION_OFFSET": "11521.5"}, "Projection offsets"),
        ({"MINIMUM_LATITUDE": "-2.0 <DEGREE>"}, "LINES"),
    ],
)
def test_invalid_labels_rejected(tmp_path, overrides, message):
    with pytest.raises(RasterValidationError, match=message):
        open_megdr(write_megdr(tmp_path, overrides=overrides))


def test_radius_product_rejected_as_elevation(tmp_path):
    lbl = write_megdr(tmp_path, image_name="MEGR00N090HB.IMG", overrides={"NAME": "PLANETARY_RADIUS"})
    with pytest.raises(RasterValidationError, match="MEGR"):
        open_megdr(lbl)


def test_unapproved_dataset_rejected(tmp_path):
    with pytest.raises(UnapprovedSourceError):
        open_megdr(write_megdr(tmp_path, overrides={"DATA_SET_ID": '"SLDEM2015"'}))
