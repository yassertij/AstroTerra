"""SYNTHETIC test fixture - not real MOLA data.

Builds a small PDS3 label + big-endian int16 image whose keywords mirror the verified
label of megt00n090hb.lbl (values listed in paf_core.sources.registry), but with a
1 x 1 degree extent and synthetic elevations. Never present outputs from this
fixture as real findings.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

RES = 128


def write_megdr(
    folder: Path,
    elevations: np.ndarray | None = None,
    *,
    lat_max: float = 0.0,
    lon_west: float = 90.0,
    overrides: dict[str, str] | None = None,
    image_name: str = "MEGT00N090HB.IMG",
    disk_name: str | None = None,
    truncate_bytes: int = 0,
) -> Path:
    if elevations is None:
        elevations = np.zeros((RES, RES), dtype=np.int16)
    lines, samples = elevations.shape
    kw = {
        "DATA_SET_ID": '"MGS-M-MOLA-5-MEGDR-L3-V1.0"',
        "PRODUCT_ID": f'"{image_name}"',
        "PRODUCT_VERSION_ID": '"2.0"',
        "NAME": "MEDIAN_TOPOGRAPHY",
        "SAMPLE_TYPE": "MSB_INTEGER",
        "SAMPLE_BITS": "16",
        "UNIT": "METER",
        "MAP_PROJECTION_TYPE": '"SIMPLE CYLINDRICAL"',
        "A_AXIS_RADIUS": "3396.0 <KM>",
        "B_AXIS_RADIUS": "3396.0 <KM>",
        "C_AXIS_RADIUS": "3396.0 <KM>",
        "COORDINATE_SYSTEM_NAME": '"PLANETOCENTRIC"',
        "POSITIVE_LONGITUDE_DIRECTION": '"EAST"',
        "LINE_PROJECTION_OFFSET": str(0.5 + RES * lat_max),
        "SAMPLE_PROJECTION_OFFSET": str(0.5 - RES * (lon_west - 180.0)),
        "MAXIMUM_LATITUDE": f"{lat_max} <DEGREE>",
        "MINIMUM_LATITUDE": f"{lat_max - lines / RES} <DEGREE>",
        "WESTERNMOST_LONGITUDE": f"{lon_west} <DEGREE>",
        "EASTERNMOST_LONGITUDE": f"{lon_west + samples / RES} <DEGREE>",
    }
    kw.update(overrides or {})
    label = f"""PDS_VERSION_ID = PDS3
/* SYNTHETIC FIXTURE - mirrors verified MEGDR label keywords */
RECORD_TYPE = FIXED_LENGTH
RECORD_BYTES = {samples * 2}
FILE_RECORDS = {lines}
^IMAGE = "{image_name}"
DATA_SET_ID = {kw['DATA_SET_ID']}
PRODUCT_ID = {kw['PRODUCT_ID']}
PRODUCT_VERSION_ID = {kw['PRODUCT_VERSION_ID']}
DESCRIPTION = "Synthetic. Topography is the planetary radius minus the
  areoid radius at a given longitude and latitude."
OBJECT = IMAGE
  NAME = {kw['NAME']}
  LINES = {lines}
  LINE_SAMPLES = {samples}
  SAMPLE_TYPE = {kw['SAMPLE_TYPE']}
  SAMPLE_BITS = {kw['SAMPLE_BITS']}
  UNIT = {kw['UNIT']}
END_OBJECT = IMAGE
OBJECT = IMAGE_MAP_PROJECTION
  MAP_PROJECTION_TYPE = {kw['MAP_PROJECTION_TYPE']}
  A_AXIS_RADIUS = {kw['A_AXIS_RADIUS']}
  B_AXIS_RADIUS = {kw['B_AXIS_RADIUS']}
  C_AXIS_RADIUS = {kw['C_AXIS_RADIUS']}
  COORDINATE_SYSTEM_TYPE = "BODY-FIXED ROTATING"
  COORDINATE_SYSTEM_NAME = {kw['COORDINATE_SYSTEM_NAME']}
  POSITIVE_LONGITUDE_DIRECTION = {kw['POSITIVE_LONGITUDE_DIRECTION']}
  MAP_RESOLUTION = {RES}.0 <PIXEL/DEGREE>
  MAXIMUM_LATITUDE = {kw['MAXIMUM_LATITUDE']}
  MINIMUM_LATITUDE = {kw['MINIMUM_LATITUDE']}
  WESTERNMOST_LONGITUDE = {kw['WESTERNMOST_LONGITUDE']}
  EASTERNMOST_LONGITUDE = {kw['EASTERNMOST_LONGITUDE']}
  LINE_PROJECTION_OFFSET = {kw['LINE_PROJECTION_OFFSET']}
  SAMPLE_PROJECTION_OFFSET = {kw['SAMPLE_PROJECTION_OFFSET']}
  CENTER_LATITUDE = 0.0 <DEGREE>
  CENTER_LONGITUDE = 180.0 <DEGREE>
END_OBJECT = IMAGE_MAP_PROJECTION
END
"""
    stem = Path(image_name).stem
    lbl_path = folder / f"{stem.lower()}.lbl"
    lbl_path.write_text(label, encoding="ascii")
    data = elevations.astype(">i2").tobytes()
    if truncate_bytes:
        data = data[:-truncate_bytes]
    (folder / (disk_name or image_name.lower())).write_bytes(data)
    return lbl_path
