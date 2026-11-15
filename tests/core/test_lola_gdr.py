"""LOLA LDEM reader against a SYNTHETIC fixture mirroring the verified LDEM_64 label."""

import numpy as np
import pytest

from paf_core.errors import RasterValidationError, UnapprovedSourceError
from paf_core.sources import lola_gdr
from paf_core.sources.registry import LOLA_GDR, require_approved

from .lola_fixture import RES, write_lola


def test_registry_entry():
    assert require_approved("LRO-L-LOLA-4-GDR-V1.0") is LOLA_GDR
    with pytest.raises(UnapprovedSourceError):
        require_approved("SLDEM2015_512")


def test_opens_with_label_geometry(tmp_path):
    p = lola_gdr.open_lola(write_lola(tmp_path))
    g = p.grid
    assert g.body == "MOON" and g.radius_m == 1737400.0 and g.deg_per_pixel == 1 / RES
    assert (g.lat_top, g.lat_bottom, g.lon_west, g.lon_east) == (1.0, -1.0, 10.0, 12.0)
    assert p.scale == 0.5 and p.reference_radius_m == 1737400.0
    assert p.record.product_version == "V3.1" and p.record.doi == "10.17189/tnyt-7007"
    assert any("interpolated" in f for f in p.record.quality_flags)


def test_height_is_dn_times_scale_without_offset(tmp_path):
    dn = (np.arange(4 * RES * RES).reshape(2 * RES, 2 * RES) % 2000 - 1000).astype(np.int16)
    p = lola_gdr.open_lola(write_lola(tmp_path, dn))
    r = lola_gdr.read_window(p, -0.5, 0.5, 10.5, 11.5)
    # lat 0.5..-0.5 -> lines 32..96; lon 10.5..11.5 -> samples 32..96
    assert r.data.shape == (64, 64)
    np.testing.assert_array_equal(r.data, dn[32:96, 32:96] * 0.5)
    assert np.abs(r.data).max() <= 500  # heights, never ~1.7e6 m radii
    assert any(s.operation == "dn_to_height" for s in r.record.processing_history)
    assert any("near_band_edge" in f for f in r.record.quality_flags)  # window spans latitude 0


def test_little_endian_byte_order(tmp_path):
    dn = np.full((2 * RES, 2 * RES), 0x0102, dtype=np.int16)
    p = lola_gdr.open_lola(write_lola(tmp_path, dn))
    assert lola_gdr.read_window(p, 0.1, 0.5, 10.1, 10.5).data[0, 0] == 0x0102 * 0.5


def test_global_grid_wraps_across_prime_meridian(tmp_path):
    dn = np.tile(np.arange(360 * RES) % 3000, (8, 1)).astype(np.int16)
    p = lola_gdr.open_lola(write_lola(tmp_path, dn, lat_max=0.125, lon_west=0.0, lon_extent=360.0))
    assert p.global_longitude
    r = lola_gdr.read_window(p, 0.0, 0.125, -0.25, 0.25)
    assert r.grid.lon_west == pytest.approx(-0.25) and r.data.shape == (8, 32)
    np.testing.assert_array_equal(r.data[0], np.concatenate([dn[0, -16:], dn[0, :16]]) * 0.5)
    crop = next(s for s in r.record.processing_history if s.operation == "crop")
    assert "wraps across 0/360" in crop.note


@pytest.mark.parametrize("over, msg", [
    ({"PRODUCT_VERSION_ID": '"V2.0"'}, "PRODUCT_VERSION_ID"),
    ({"TARGET_NAME": "MARS"}, "TARGET_NAME"),
    ({"NAME": "SLOPE"}, "not an LDEM height"),
    ({"PRODUCT_ID": '"LDSM_64"'}, "not an LDEM height"),
    ({"OFFSET": "1737000."}, "reference radius ambiguous"),
    ({"SCALING_FACTOR": "0"}, "SCALING_FACTOR"),
    ({"COORDINATE_SYSTEM_NAME": '"PLANETOGRAPHIC"'}, "Mean Earth"),
    ({"POSITIVE_LONGITUDE_DIRECTION": '"WEST"'}, "POSITIVE_LONGITUDE_DIRECTION"),
    ({"LINE_PROJECTION_OFFSET": "64.5 <pix>"}, "Projection offsets"),  # MEGDR-style 1-based offset
    ({"UNIT": "KM"}, "UNIT"),
])
def test_invalid_labels_rejected(tmp_path, over, msg):
    with pytest.raises(RasterValidationError) as e:
        lola_gdr.open_lola(write_lola(tmp_path, overrides=over))
    assert any(msg in p for p in e.value.problems), e.value.problems


def test_truncated_download_rejected(tmp_path):
    with pytest.raises(RasterValidationError, match="truncated"):
        lola_gdr.open_lola(write_lola(tmp_path, truncate_bytes=10))


def test_window_outside_rejected(tmp_path):
    p = lola_gdr.open_lola(write_lola(tmp_path))
    with pytest.raises(RasterValidationError, match="outside"):
        lola_gdr.read_window(p, 0.0, 2.0, 10.5, 11.0)
