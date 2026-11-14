import pytest

from paf_core.errors import UnapprovedSourceError
from paf_core.provenance import md5_file, parse_md5_manifest, verify_md5
from paf_core.sources.registry import MOLA_MEGDR, require_approved


def test_megdr_is_approved():
    assert require_approved("MGS-M-MOLA-5-MEGDR-L3-V1.0") is MOLA_MEGDR


@pytest.mark.parametrize("dsid", ["LRO-L-LOLA-SLDEM2015", "COPERNICUS-DEM-GLO-30", "SOME-RANDOM-MIRROR", "", None])
def test_non_nasa_or_unknown_rejected(dsid):
    with pytest.raises(UnapprovedSourceError):
        require_approved(dsid)


def test_md5_roundtrip(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    assert md5_file(p) == "900150983CD24FB0D6963F7D28E17F72"  # RFC 1321 test vector
    assert verify_md5(p, "900150983cd24fb0d6963f7d28e17f72")
    assert not verify_md5(p, "0" * 32)


def test_md5_manifest_windows_paths():
    text = "1F2C70C407976DD22E79DFBB3469EBF1  mgsl_300x\\meg128\\megt00n090hb.img\n"
    assert parse_md5_manifest(text) == {"megt00n090hb.img": "1F2C70C407976DD22E79DFBB3469EBF1"}
