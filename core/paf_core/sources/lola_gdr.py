"""LOLA GDR adapter (Moon heights, PDS3 detached-label LDEM grids).

Verified against ldem_64.lbl (LRO-L-LOLA-4-GDR-V1.0, PRODUCT_VERSION_ID "V3.1") and the
volume's catalog/dsmap.cat on 2026-11-15. Facts the loader relies on, all read from the
label and checked here:

- IMAGE NAME = HEIGHT, LSB_INTEGER 16-bit, UNIT = METER, SCALING_FACTOR = 0.5,
  OFFSET = 1737400 (the reference-sphere radius). Per the label note,
  HEIGHT = DN * SCALING_FACTOR; PLANETARY_RADIUS = HEIGHT + OFFSET. This loader returns
  HEIGHT and never adds OFFSET (adding it would turn heights into radii).
- SIMPLE CYLINDRICAL, sphere A = B = C = 1737.4 km, east-positive 0-360 longitude,
  frame "MEAN EARTH/POLAR AXIS OF DE421" (planetocentric latitudes).
- Projection offsets follow dsmap.cat: LINE = NINT(LINE_PROJECTION_OFFSET -
  RES*(LAT - CENTER_LATITUDE)) + 1, i.e. offsets are zero-based. The grid is pixel
  (edge) registered: the outer edge of line 1 sits at line coordinate 0.5.
- No MISSING_CONSTANT: every cell holds a value; the grid was completed with GMT
  'surface' where LOLA coverage is incomplete, so interpolated cells cannot be told
  apart without the LDAC count products (not loaded) - flagged on every record.

Only LDEM* (elevation) products are accepted; slope, roughness, albedo and count
grids from the same data set are rejected as elevation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..errors import RasterValidationError
from ..pds3 import Label, Quantity, parse_label_file
from ..provenance import DatasetRecord
from ..raster import GeoGrid, Raster
from .mola_megdr import _SAMPLE_TYPES, _deg, _find_image_file, _radius_m
from .registry import LOLA_GDR, require_approved

_EPS = 1e-6
BAND_EDGES_DEG = (-45.0, 0.0, 45.0)  # label: gridded in 45-degree latitude bands
BAND_EDGE_MARGIN_DEG = 0.5


@dataclass
class LolaProduct:
    label_path: Path
    image_path: Path
    dtype: np.dtype
    byte_offset: int
    lines: int
    samples: int
    grid: GeoGrid
    scale: float
    reference_radius_m: float
    global_longitude: bool
    record: DatasetRecord


def open_lola(label_path: str | Path) -> LolaProduct:
    """Parse and validate an LDEM label and its image file. Raises RasterValidationError."""
    label_path = Path(label_path)
    lbl: Label = parse_label_file(label_path)
    problems: list[str] = []

    source = require_approved(lbl.find("DATA_SET_ID"))  # raises UnapprovedSourceError
    if source is not LOLA_GDR:
        problems.append(f"{label_path.name}: DATA_SET_ID is not LOLA GDR.")
    version = str(lbl.find("PRODUCT_VERSION_ID") or "")
    if version != source.final_product_version:
        problems.append(
            f"PRODUCT_VERSION_ID is {version or 'missing'!r}; only {source.final_product_version!r} "
            f"(LDEM_64) has been verified. Download it from {source.access_url}"
        )
    target = lbl.find("TARGET_NAME")
    if str(target or "").upper() != source.body:
        problems.append(f"TARGET_NAME is {target!r}, expected {source.body}.")

    product_id = str(lbl.find("PRODUCT_ID") or label_path.stem).upper()
    image = lbl.find("IMAGE")
    if not isinstance(image, Label):
        raise RasterValidationError([f"{label_path.name}: no IMAGE object in label."])
    if not product_id.startswith("LDEM_") or str(image.get("NAME", "")).upper() != "HEIGHT":
        problems.append(
            f"{product_id} (IMAGE NAME={image.get('NAME')!r}) is not an LDEM height product; slope, "
            "roughness, albedo and count grids are not elevation."
        )

    lines, samples = image.get("LINES"), image.get("LINE_SAMPLES")
    bits, stype = image.get("SAMPLE_BITS"), str(image.get("SAMPLE_TYPE", ""))
    if not (isinstance(lines, int) and isinstance(samples, int) and lines > 0 and samples > 0):
        problems.append("LINES / LINE_SAMPLES missing or not positive integers.")
    if stype not in _SAMPLE_TYPES or bits not in (8, 16, 32):
        problems.append(f"Unsupported SAMPLE_TYPE/SAMPLE_BITS: {stype!r}/{bits!r}.")
    if str(image.get("UNIT", "")).upper() not in ("METER", "METERS", "M"):
        problems.append(f"Image UNIT is {image.get('UNIT')!r}; expected METER.")
    scale, offset = image.get("SCALING_FACTOR"), image.get("OFFSET")
    if not isinstance(scale, (int, float)) or scale <= 0:
        problems.append("SCALING_FACTOR missing or not positive; heights cannot be converted.")
    if not isinstance(offset, (int, float)):
        problems.append("OFFSET (reference radius) missing; the vertical reference cannot be confirmed.")
    if image.get("MISSING_CONSTANT") is not None:
        problems.append("Label declares a MISSING_CONSTANT; this loader was verified on LDEM_64, which has none.")

    if str(lbl.find("MAP_PROJECTION_TYPE") or "").upper() != "SIMPLE CYLINDRICAL":
        problems.append("MAP_PROJECTION_TYPE is not SIMPLE CYLINDRICAL.")
    radii = [_radius_m(lbl.find(k)) for k in ("A_AXIS_RADIUS", "B_AXIS_RADIUS", "C_AXIS_RADIUS")]
    if None in radii:
        problems.append("A/B/C_AXIS_RADIUS missing or without a length unit.")
    elif max(radii) - min(radii) > 1e-6:
        problems.append(f"Non-spherical reference radii {radii} m; only spherical grids are supported.")
    elif isinstance(offset, (int, float)) and abs(offset - radii[0]) > 0.5:
        problems.append(f"OFFSET {offset} m differs from the sphere radius {radii[0]} m; reference radius ambiguous.")
    csys = str(lbl.find("COORDINATE_SYSTEM_NAME") or "").upper()
    if "MEAN EARTH/POLAR AXIS" not in csys:
        problems.append(f"COORDINATE_SYSTEM_NAME is {csys or 'missing'!r}; expected the Mean Earth/Polar Axis frame.")
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
        lpo, spo = _deg_or_pix(lbl.find("LINE_PROJECTION_OFFSET")), _deg_or_pix(lbl.find("SAMPLE_PROJECTION_OFFSET"))
        clat, clon = _deg(lbl.find("CENTER_LATITUDE")), _deg(lbl.find("CENTER_LONGITUDE"))
        if None in (lpo, spo, clat, clon):
            problems.append("Projection offsets or centre lat/lon missing; grid registration cannot be confirmed.")
        else:
            # dsmap.cat: 1-based line = LPO - RES*(LAT - CLAT) + 1; outer edge of line 1 = 0.5.
            top = lpo - res * (lat_max - clat) + 1
            left = spo + res * (lon_w - clon) + 1
            if abs(top - 0.5) > _EPS or abs(left - 0.5) > _EPS:
                problems.append(
                    f"Projection offsets disagree with grid corners under the dsmap.cat convention "
                    f"(top edge line {top}, left edge sample {left}; expected 0.5)."
                )
    desc = " ".join(str(lbl.find("DESCRIPTION") or "").split())
    if "relative to a radius" not in desc.lower():
        problems.append("Label DESCRIPTION does not state the reference radius; vertical reference cannot be confirmed.")

    image_path, start_record, ptr_problem = _find_image_file(label_path, lbl.find("^IMAGE"))
    if ptr_problem:
        problems.append(ptr_problem)
    if problems:
        raise RasterValidationError(problems)

    dtype = np.dtype(f"{_SAMPLE_TYPES[stype]}{bits // 8}")
    record_bytes = lbl.find("RECORD_BYTES") or 0
    byte_offset = (start_record - 1) * record_bytes
    expected = byte_offset + lines * samples * dtype.itemsize
    actual = image_path.stat().st_size
    if actual != expected:
        hint = "truncated or interrupted download" if actual < expected else "unexpected trailing data"
        raise RasterValidationError([f"{image_path.name} is {actual} bytes; label implies {expected} ({hint}). Re-download it."])

    radius = radii[0]
    grid = GeoGrid(body="MOON", radius_m=radius, lat_top=lat_max, lon_west=lon_w,
                   deg_per_pixel=1.0 / res, rows=lines, cols=samples)
    record = DatasetRecord(
        product_id=product_id, data_set_id=source.data_set_id, product_version=version, doi=source.doi,
        mission=source.mission, instrument=source.instrument, archive=source.archive, access_url=source.access_url,
        file_format=f"PDS3 detached label + raw {stype} {bits}-bit image",
        body=source.body,
        horizontal_reference=f"{csys}, planetocentric latitude, sphere radius {radius:.1f} m (label A/B/C_AXIS_RADIUS)",
        projection=f"SIMPLE CYLINDRICAL, {res:g} pixel/degree, pixel (edge) registered, centre lon {clon:g}° E",
        latitude_type="planetocentric (Mean Earth/Polar Axis frame)",
        longitude_convention=f"0-360, positive {londir}",
        vertical_reference=source.vertical_reference,
        units="metre",
        scale_factor=f"{scale} (HEIGHT = DN x SCALING_FACTOR)",
        offset=f"{offset} m = reference radius; not added to heights",
        fill_value="none declared in label (all cells hold a value)",
        citation=source.citation,
        source_files=[label_path.name, image_path.name],
        checksum_md5="unknown",
        quality_flags=[
            "interpolated_cells_not_identified: per the LDEM label, GMT 'surface' was used to compensate "
            "for incomplete LOLA coverage; the LDAC count product is not loaded, so interpolated cells "
            "cannot be identified or excluded.",
            "no_published_checksum: no MD5 is published for this file; size was checked against the label.",
        ],
    )
    record.add_step("open_label", note="Label parsed and validated (LOLA dsmap.cat conventions)", label=label_path.name)
    return LolaProduct(
        label_path=label_path, image_path=image_path, dtype=dtype, byte_offset=byte_offset, lines=lines,
        samples=samples, grid=grid, scale=float(scale), reference_radius_m=float(offset),
        global_longitude=abs((lon_e - lon_w) - 360.0) < _EPS, record=record,
    )


def _deg_or_pix(v) -> float | None:
    if isinstance(v, Quantity):
        return v.value
    return float(v) if isinstance(v, (int, float)) else None


def window_from_center_km(product: LolaProduct, lat: float, lon: float, size_km: float) -> tuple[float, float, float, float]:
    """Square-ish window of ``size_km`` on a side around (lat, lon east), using the label radius."""
    r_km = product.grid.radius_m / 1000.0
    dlat = math.degrees(size_km / 2 / r_km)
    dlon = math.degrees(size_km / 2 / (r_km * math.cos(math.radians(lat))))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def contains(product: LolaProduct, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> bool:
    g = product.grid
    if lat_min < g.lat_bottom - _EPS or lat_max > g.lat_top + _EPS:
        return False
    if product.global_longitude:
        return lon_max - lon_min < 360.0
    return g.lon_west - _EPS <= lon_min and lon_max <= g.lon_east + _EPS


def _cols(g: GeoGrid, lon_min: float, lon_max: float) -> tuple[int, int]:
    res = 1.0 / g.deg_per_pixel
    return int(math.floor((lon_min - g.lon_west) * res + _EPS)), int(math.ceil((lon_max - g.lon_west) * res - _EPS))


def read_window(product: LolaProduct, lat_min: float, lat_max: float, lon_min: float, lon_max: float) -> Raster:
    """Read a lat/lon window (planetocentric, east longitude). Wraps across 0/360 E on global grids."""
    g = product.grid
    if not (lat_min < lat_max and lon_min < lon_max):
        raise RasterValidationError(["Window bounds must satisfy min < max."])
    if not contains(product, lat_min, lat_max, lon_min, lon_max):
        raise RasterValidationError([
            f"Window lat [{lat_min:.4f}, {lat_max:.4f}] lon [{lon_min:.4f}, {lon_max:.4f}] is outside "
            f"{product.record.product_id} (lat [{g.lat_bottom}, {g.lat_top}], lon [{g.lon_west}, {g.lon_east}] E)."
        ])
    res = 1.0 / g.deg_per_pixel
    r0 = int(math.floor((g.lat_top - lat_max) * res + _EPS))
    r1 = int(math.ceil((g.lat_top - lat_min) * res - _EPS))
    shift = 0.0
    if product.global_longitude and lon_min < g.lon_west:
        shift = -360.0
    elif product.global_longitude and lon_min >= g.lon_east:
        shift = 360.0
    c0, c1 = _cols(g, lon_min - shift, lon_max - shift)  # c0 >= 0 now; c1 may exceed samples (wrap)
    mm = np.memmap(product.image_path, dtype=product.dtype, mode="r", offset=product.byte_offset,
                   shape=(product.lines, product.samples))
    if c1 <= product.samples:
        raw = np.array(mm[r0:r1, c0:c1])
        wrapped = False
    else:
        raw = np.hstack([np.array(mm[r0:r1, c0:]), np.array(mm[r0:r1, : c1 - product.samples])])
        wrapped = True
    del mm
    data = raw.astype(np.float64) * product.scale  # HEIGHT = DN * SCALING_FACTOR (no OFFSET)

    sub = GeoGrid(body=g.body, radius_m=g.radius_m, lat_top=g.lat_top - r0 * g.deg_per_pixel,
                  lon_west=g.lon_west + shift + c0 * g.deg_per_pixel, deg_per_pixel=g.deg_per_pixel,
                  rows=r1 - r0, cols=c1 - c0)
    record = product.record.model_copy(deep=True)
    record.add_step(
        "crop", note="Window snapped outward to whole pixels. No resampling."
        + (" Window wraps across 0/360 E; columns joined from both ends of the grid." if wrapped else ""),
        requested={"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
        actual={"lat_min": sub.lat_bottom, "lat_max": sub.lat_top, "lon_min": sub.lon_west, "lon_max": sub.lon_east},
        rows=[r0, r1], cols=[c0, c1],
    )
    record.add_step("dn_to_height", note="HEIGHT = DN x SCALING_FACTOR; reference radius OFFSET not added.",
                    scaling_factor=product.scale, reference_radius_m=product.reference_radius_m)
    near = [b for b in BAND_EDGES_DEG if sub.lat_bottom - BAND_EDGE_MARGIN_DEG <= b <= sub.lat_top + BAND_EDGE_MARGIN_DEG]
    if near:
        record.quality_flags.append(
            f"near_band_edge: window within {BAND_EDGE_MARGIN_DEG} deg of latitude {near}; the label warns of "
            "possible edge artifacts at 45-degree band boundaries."
        )
    return Raster(data=data, grid=sub, record=record)
