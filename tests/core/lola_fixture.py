"""SYNTHETIC test fixture - not real LOLA data.

Writes a PDS3 label + little-endian int16 image whose keywords mirror the verified
ldem_64.lbl (LRO-L-LOLA-4-GDR-V1.0, V3.1) - same scale, offset, frame and dsmap.cat
offset convention - but with a small extent and synthetic DNs. Never present outputs
from this fixture as real findings.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

RES = 64


def write_lola(folder: Path, dn: np.ndarray | None = None, *, lat_max: float = 1.0, lon_west: float = 10.0,
               lon_extent: float | None = None, overrides: dict[str, str] | None = None,
               truncate_bytes: int = 0) -> Path:
    if dn is None:
        dn = np.zeros((2 * RES, 2 * RES), dtype=np.int16)
    lines, samples = dn.shape
    lon_extent = samples / RES if lon_extent is None else lon_extent
    kw = {
        "DATA_SET_ID": '"LRO-L-LOLA-4-GDR-V1.0"',
        "PRODUCT_ID": '"LDEM_64"',
        "PRODUCT_VERSION_ID": '"V3.1"',
        "TARGET_NAME": "MOON",
        "NAME": "HEIGHT",
        "SAMPLE_TYPE": "LSB_INTEGER",
        "SAMPLE_BITS": "16",
        "UNIT": "METER",
        "SCALING_FACTOR": "0.5",
        "OFFSET": "1737400.",
        "MAP_PROJECTION_TYPE": '"SIMPLE CYLINDRICAL"',
        "MAP_RESOLUTION": f"{RES} <pix/deg>",
        "A_AXIS_RADIUS": "1737.4 <km>",
        "B_AXIS_RADIUS": "1737.4 <km>",
        "C_AXIS_RADIUS": "1737.4 <km>",
        "POSITIVE_LONGITUDE_DIRECTION": '"EAST"',
        "CENTER_LATITUDE": "0 <deg>",
        "CENTER_LONGITUDE": "180 <deg>",
        "MAXIMUM_LATITUDE": f"{lat_max} <deg>",
        "MINIMUM_LATITUDE": f"{lat_max - lines / RES} <deg>",
        "WESTERNMOST_LONGITUDE": f"{lon_west} <deg>",
        "EASTERNMOST_LONGITUDE": f"{lon_west + lon_extent} <deg>",
        # dsmap.cat: offsets are zero-based; outer edge of line 1 at 0.5 (1-based).
        "LINE_PROJECTION_OFFSET": f"{RES * lat_max - 0.5} <pix>",
        "SAMPLE_PROJECTION_OFFSET": f"{-0.5 - RES * (lon_west - 180.0)} <pix>",
        "COORDINATE_SYSTEM_NAME": '"MEAN EARTH/POLAR AXIS OF DE421"',
    }
    kw.update(overrides or {})
    label = f"""PDS_VERSION_ID            = "PDS3"
/* SYNTHETIC FIXTURE - mirrors verified LDEM_64 label keywords */
PRODUCT_VERSION_ID        = {kw['PRODUCT_VERSION_ID']}
DATA_SET_ID               = {kw['DATA_SET_ID']}
PRODUCT_ID                = {kw['PRODUCT_ID']}
MISSION_PHASE_NAME        = {{"COMMISSIONING","NOMINAL MISSION","SCIENCE
                            MISSION","EXTENDED SCIENCE MISSION"}}
TARGET_NAME               = {kw['TARGET_NAME']}
DESCRIPTION               = "Synthetic. Map values are relative to a radius of
   1737.4 km."
OBJECT                    = UNCOMPRESSED_FILE
FILE_NAME                 = "LDEM_64.IMG"
RECORD_TYPE               = FIXED_LENGTH
FILE_RECORDS              = {lines}
RECORD_BYTES              = {samples * 2}
^IMAGE                    = "LDEM_64.IMG"
  OBJECT                  = IMAGE
    NAME                  = {kw['NAME']}
    LINES                 = {lines}
    LINE_SAMPLES          = {samples}
    SAMPLE_TYPE           = {kw['SAMPLE_TYPE']}
    SAMPLE_BITS           = {kw['SAMPLE_BITS']}
    UNIT                  = {kw['UNIT']}
    SCALING_FACTOR        = {kw['SCALING_FACTOR']}
    OFFSET                = {kw['OFFSET']}
  END_OBJECT              = IMAGE
END_OBJECT                = UNCOMPRESSED_FILE
OBJECT                    = IMAGE_MAP_PROJECTION
 MAP_PROJECTION_TYPE          = {kw['MAP_PROJECTION_TYPE']}
 MAP_RESOLUTION               = {kw['MAP_RESOLUTION']}
 A_AXIS_RADIUS                = {kw['A_AXIS_RADIUS']}
 B_AXIS_RADIUS                = {kw['B_AXIS_RADIUS']}
 C_AXIS_RADIUS                = {kw['C_AXIS_RADIUS']}
 POSITIVE_LONGITUDE_DIRECTION = {kw['POSITIVE_LONGITUDE_DIRECTION']}
 CENTER_LATITUDE              = {kw['CENTER_LATITUDE']}
 CENTER_LONGITUDE             = {kw['CENTER_LONGITUDE']}
 MAXIMUM_LATITUDE             = {kw['MAXIMUM_LATITUDE']}
 MINIMUM_LATITUDE             = {kw['MINIMUM_LATITUDE']}
 WESTERNMOST_LONGITUDE        = {kw['WESTERNMOST_LONGITUDE']}
 EASTERNMOST_LONGITUDE        = {kw['EASTERNMOST_LONGITUDE']}
 LINE_PROJECTION_OFFSET       = {kw['LINE_PROJECTION_OFFSET']}
 SAMPLE_PROJECTION_OFFSET     = {kw['SAMPLE_PROJECTION_OFFSET']}
 COORDINATE_SYSTEM_NAME       = {kw['COORDINATE_SYSTEM_NAME']}
END_OBJECT                    = IMAGE_MAP_PROJECTION
END
"""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ldem_64.lbl").write_text(label, encoding="ascii")
    raw = dn.astype("<i2").tobytes()
    (folder / "ldem_64.img").write_bytes(raw[: len(raw) - truncate_bytes] if truncate_bytes else raw)
    return folder / "ldem_64.lbl"
