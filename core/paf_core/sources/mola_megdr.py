"""MOLA MEGDR adapter (Mars topography, PDS3 detached-label tiles).

Only *topography* products (MEGT*, image NAME containing TOPOGRAPHY) are accepted as
elevation. Radius (MEGR), areoid (MEGA) and count (MEGC) products are rejected here.

Everything the loader needs is read from the label; nothing is hard-coded except the
checks against the verified allow-list entry.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..errors import RasterValidationError
from ..pds3 import Label, Quantity, parse_label_file
from ..provenance import DatasetRecord
from ..raster import GeoGrid, Raster
from .registry import MOLA_MEGDR, require_approved

_SAMPLE_TYPES = {
    "MSB_INTEGER": ">i",
    "SUN_INTEGER": ">i",
    "LSB_INTEGER": "<i",
    "PC_INTEGER": "<i",
    "MSB_UNSIGNED_INTEGER": ">u",
    "LSB_UNSIGNED_INTEGER": "<u",
    "PC_UNSIGNED_INTEGER": "<u",
}
_EPS = 1e-6


@dataclass
class MegdrProduct:
    label_path: Path
    image_path: Path
    dtype: np.dtype
    byte_offset: int
    lines: int
    samples: int
    grid: GeoGrid
    scale: float
    offset: float
    missing: float | None
    record: DatasetRecord


def _deg(v) -> float | None:
    if isinstance(v, Quantity):
        return v.value if v.unit.startswith("DEG") else None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _radius_m(v) -> float | None:
    if isinstance(v, Quantity):
        factor = {"KM": 1000.0, "M": 1.0, "METER": 1.0, "METERS": 1.0}.get(v.unit)
        return v.value * factor if factor else None
    return None


def _find_image_file(label_path: Path, pointer) -> tuple[Path | None, int | None, str | None]:
    """Return (path, start_record, problem) for a detached ^IMAGE pointer."""
    if isinstance(pointer, str):
        m = re.match(r'^\(\s*"?([^",]+)"?\s*,\s*(\d+)\s*\)$', pointer)
        name, start = (m.group(1), int(m.group(2))) if m else (pointer, 1)
    else:
        return None, None, "^IMAGE pointer is not a detached file reference; attached labels are not supported."
    folder = label_path.parent
    for candidate in folder.iterdir():  # archive serves lowercase names, label says uppercase
        if candidate.name.lower() == name.lower():
            return candidate, start, None
    return None, None, f"Image file {name!r} named by the label was not found next to {label_path.name}. Download it into the same folder."


def open_megdr(label_path: str | Path) -> MegdrProduct:
    """Parse and validate a MEGDR topography label and its image file. Raises RasterValidationError."""
    label_path = Path(label_path)
    lbl: Label = parse_label_file(label_path)
    problems: list[str] = []

    source = require_approved(lbl.find("DATA_SET_ID"))  # raises UnapprovedSourceError
    if source is not MOLA_MEGDR:
        problems.append(f"{label_path.name}: DATA_SET_ID is not MOLA MEGDR.")

    version = str(lbl.find("PRODUCT_VERSION_ID") or "")
    if version != source.final_product_version:
        problems.append(
            f"PRODUCT_VERSION_ID is {version or 'missing'!r}; the final release is "
            f"{source.final_product_version!r}. Download the current file from {source.access_url}"
        )

    target = lbl.find("TARGET_NAME")
    if target is not None and str(target).upper() != source.body:
        problems.append(f"TARGET_NAME is {target!r}, expected {source.body}.")

    product_id = str(lbl.find("PRODUCT_ID") or label_path.stem).upper()
    image = lbl.get("IMAGE")
    if not isinstance(image, Label):
        raise RasterValidationError([f"{label_path.name}: no IMAGE object in label."])
    name = str(image.get("NAME", ""))
    if not product_id.startswith("MEGT") or "TOPOGRAPHY" not in name.upper():
        problems.append(
            f"{product_id} (IMAGE NAME={name!r}) is not a topography product. Use a MEGT* file; "
            "radius (MEGR), areoid (MEGA) and count (MEGC) files are not elevation relative to the areoid."
        )

    lines, samples = image.get("LINES"), image.get("LINE_SAMPLES")
    bits, stype = image.get("SAMPLE_BITS"), str(image.get("SAMPLE_TYPE", ""))
    if not (isinstance(lines, int) and isinstance(samples, int) and lines > 0 and samples > 0):
        problems.append("LINES / LINE_SAMPLES missing or not positive integers.")
    if stype not in _SAMPLE_TYPES or bits not in (8, 16, 32):
        problems.append(f"Unsupported SAMPLE_TYPE/SAMPLE_BITS: {stype!r}/{bits!r}.")
    unit = str(image.get("UNIT", "")).upper()
    if unit not in ("METER", "METERS", "M"):
        problems.append(f"Image UNIT is {unit or 'missing'!r}; expected METER.")

    scale = image.get("SCALING_FACTOR", 1.0)
    offset = image.get("OFFSET", 0.0)
    missing = image.get("MISSING_CONSTANT")

    # Map projection / body geometry, all from the label.
    proj = str(lbl.find("MAP_PROJECTION_TYPE") or "")
    if proj.upper() != "SIMPLE CYLINDRICAL":
        problems.append(f"MAP_PROJECTION_TYPE is {proj!r}; this loader supports SIMPLE CYLINDRICAL only.")
    radii = [_radius_m(lbl.find(k)) for k in ("A_AXIS_RADIUS", "B_AXIS_RADIUS", "C_AXIS_RADIUS")]
    if None in radii:
        problems.append("A/B/C_AXIS_RADIUS missing or without a length unit; the body radius must come from the label.")
    elif max(radii) - min(radii) > 1e-6:
        problems.append(f"Non-spherical reference radii {radii} m; only spherical MEGDR grids are supported.")
    csys = str(lbl.find("COORDINATE_SYSTEM_NAME") or "").upper()
    if csys != "PLANETOCENTRIC":
        problems.append(f"COORDINATE_SYSTEM_NAME is {csys or 'missing'!r}; expected PLANETOCENTRIC.")
    londir = str(lbl.find("POSITIVE_LONGITUDE_DIRECTION") or "").upper()
    if londir != "EAST":
        problems.append(f"POSITIVE_LONGITUDE_DIRECTION is {londir or 'missing'!r}; expected EAST.")

    res = lbl.find("MAP_RESOLUTION")
    res = res.value if isinstance(res, Quantity) else res
    lat_max, lat_min = _deg(lbl.find("MAXIMUM_LATITUDE")), _deg(lbl.find("MINIMUM_LATITUDE"))
    lon_w, lon_e = _deg(lbl.find("WESTERNMOST_LONGITUDE")), _deg(lbl.find("EASTERNMOST_LONGITUDE"))
    if None in (res, lat_max, lat_min, lon_w, lon_e):
        problems.append("Grid keywords missing (MAP_RESOLUTION, MIN/MAX_LATITUDE, WESTERN/EASTERNMOST_LONGITUDE).")
    elif isinstance(lines, int) and isinstance(samples, int):
        if abs((lat_max - lat_min) * res - lines) > _EPS:
            problems.append(f"Latitude extent x resolution = {(lat_max - lat_min) * res} != LINES {lines}.")
        if abs((lon_e - lon_w) * res - samples) > _EPS:
            problems.append(f"Longitude extent x resolution = {(lon_e - lon_w) * res} != LINE_SAMPLES {samples}.")
        lpo, spo = lbl.find("LINE_PROJECTION_OFFSET"), lbl.find("SAMPLE_PROJECTION_OFFSET")
        clat, clon = _deg(lbl.find("CENTER_LATITUDE")), _deg(lbl.find("CENTER_LONGITUDE"))
        if None not in (lpo, spo, clat, clon):
            # Edge of the first line/sample must sit at 0.5 in 1-based pixel-centre coordinates.
            top = lpo - res * (lat_max - clat)
            left = spo + res * (lon_w - clon)
            if abs(top - 0.5) > _EPS or abs(left - 0.5) > _EPS:
                problems.append(
                    f"Projection offsets disagree with grid corners (top edge line {top}, left edge sample {left}; expected 0.5)."
                )
        else:
            problems.append("Projection offsets or centre lat/lon missing; grid registration cannot be confirmed.")

    desc = str(lbl.find("DESCRIPTION") or "")
    if "AREOID" not in desc.upper():
        problems.append("Label DESCRIPTION does not mention the areoid; vertical reference cannot be confirmed.")

    image_path, start_record, ptr_problem = _find_image_file(label_path, lbl.get("^IMAGE"))
    if ptr_problem:
        problems.append(ptr_problem)

    if problems:
        raise RasterValidationError(problems)

    dtype = np.dtype(f"{_SAMPLE_TYPES[stype]}{bits // 8}")
    record_bytes = lbl.get("RECORD_BYTES", 0) or 0
    byte_offset = (start_record - 1) * record_bytes
    expected = byte_offset + lines * samples * dtype.itemsize
    actual = image_path.stat().st_size
    if actual != expected:
        hint = "truncated or interrupted download" if actual < expected else "unexpected trailing data"
        raise RasterValidationError(
            [f"{image_path.name} is {actual} bytes; label implies {expected} ({hint}). Re-download and verify the MD5."]
        )

    radius = radii[0]
    grid = GeoGrid(
        body=source.body, radius_m=radius, lat_top=lat_max, lon_west=lon_w,
        deg_per_pixel=1.0 / res, rows=lines, cols=samples,
    )
    record = DatasetRecord(
        product_id=product_id,
        data_set_id=source.data_set_id,
        product_version=version,
        doi=source.doi,
        mission=source.mission,
        instrument=source.instrument,
        archive=source.archive,
        access_url=source.access_url,
        file_format=f"PDS3 detached label + raw {stype} {bits}-bit image",
        body=source.body,
        horizontal_reference=f"{csys} {lbl.find('COORDINATE_SYSTEM_TYPE') or ''}, sphere radius {radius:.1f} m (label A/B/C_AXIS_RADIUS)".strip(),
        projection=f"SIMPLE CYLINDRICAL, {res:g} pixel/degree, edge-registered, centre lon {_deg(lbl.find('CENTER_LONGITUDE')):g}° E",
        latitude_type="planetocentric",
        longitude_convention=f"0-360, positive {londir}",
        vertical_reference=source.vertical_reference,
        units="metre",
        scale_factor=str(scale) if "SCALING_FACTOR" in image else "not declared in label (stored values used as metres)",
        offset=str(offset) if "OFFSET" in image else "not declared in label",
        fill_value=str(missing) if missing is not None else "none declared in label",
        citation=source.citation,
        source_files=[label_path.name, image_path.name],
        quality_flags=[
            "observation_counts_not_loaded: per the MEGDR label, cells with no MOLA "
            "observation hold an interpolated value (near the equator only ~55% of bins "
            "contain a shot; gaps up to 12 km between profiles). The MEGC count product is "
            "not loaded, so interpolated cells cannot be identified or excluded."
        ],
    )
    record.add_step("open_label", note="Label parsed and validated", label=label_path.name)
    return MegdrProduct(
        label_path=label_path, image_path=image_path, dtype=dtype, byte_offset=byte_offset,
        lines=lines, samples=samples, grid=grid, scale=float(scale), offset=float(offset),
        missing=missing, record=record,
    )


def window_from_center_km(product: MegdrProduct, lat: float, lon: float, size_km: float) -> tuple[float, float, float, float]:
    """Square-ish window of ``size_km`` on a side around (lat, lon east), using the label radius."""
    r_km = product.grid.radius_m / 1000.0
    dlat = math.degrees(size_km / 2 / r_km)
    dlon = math.degrees(size_km / 2 / (r_km * math.cos(math.radians(lat))))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def read_window(product: MegdrProduct, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> Raster:
    """Read a lat/lon window (degrees, planetocentric, 0-360 E) without loading the whole tile."""
    g = product.grid
    if not (lat_min < lat_max and lon_min < lon_max):
        raise RasterValidationError(["Window bounds must satisfy min < max."])
    if lat_min < g.lat_bottom - _EPS or lat_max > g.lat_top + _EPS or lon_min < g.lon_west - _EPS or lon_max > g.lon_east + _EPS:
        raise RasterValidationError([
            f"Window lat [{lat_min:.4f}, {lat_max:.4f}] lon [{lon_min:.4f}, {lon_max:.4f}] is outside tile "
            f"{product.record.product_id} (lat [{g.lat_bottom}, {g.lat_top}], lon [{g.lon_west}, {g.lon_east}] E). "
            "Choose a window inside one tile; multi-tile mosaics are not implemented."
        ])
    res = 1.0 / g.deg_per_pixel
    r0 = int(math.floor((g.lat_top - lat_max) * res + _EPS))
    r1 = int(math.ceil((g.lat_top - lat_min) * res - _EPS))
    c0 = int(math.floor((lon_min - g.lon_west) * res + _EPS))
    c1 = int(math.ceil((lon_max - g.lon_west) * res - _EPS))

    mm = np.memmap(product.image_path, dtype=product.dtype, mode="r", offset=product.byte_offset,
                   shape=(product.lines, product.samples))
    raw = np.array(mm[r0:r1, c0:c1])
    del mm
    data = raw.astype(np.float64)
    if product.missing is not None:
        data[raw == product.missing] = np.nan
    data = data * product.scale + product.offset

    sub = GeoGrid(
        body=g.body, radius_m=g.radius_m, lat_top=g.lat_top - r0 * g.deg_per_pixel,
        lon_west=g.lon_west + c0 * g.deg_per_pixel, deg_per_pixel=g.deg_per_pixel,
        rows=r1 - r0, cols=c1 - c0,
    )
    record = product.record.model_copy(deep=True)
    record.add_step(
        "crop",
        note="Window snapped outward to whole pixels. No resampling.",
        requested={"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
        actual={"lat_min": sub.lat_bottom, "lat_max": sub.lat_top, "lon_min": sub.lon_west, "lon_max": sub.lon_east},
        rows=[r0, r1], cols=[c0, c1],
    )
    return Raster(data=data, grid=sub, record=record)
