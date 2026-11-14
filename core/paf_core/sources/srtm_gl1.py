"""SRTM GL1 v3 adapter (Earth, 1 arc-second tiles) with mandatory NUM source files.

Format facts (SRTM Collection User Guide, revised Oct 2015, sec. 2.1.1 and 2.1.4):
- Tiles are 3601 x 3601, 16-bit signed big-endian, row-major from the north, no header.
- The tile name gives the *centre* of the lower-left pixel; edge pixels are centred on
  whole degrees and duplicate the neighbouring tiles' edge rows/columns.
- Heights in metres referenced to the WGS84/EGM96 geoid. -32768 flagged voids in
  v1/v2; v3 should contain none (any found are treated as nodata).
- NUM files: one byte per pixel on the same grid; codes in Table 2 (see NUM_CODES).

Coverage is 60 N to 56 S only. Tiles outside are reported as unavailable, never filled.
"""

from __future__ import annotations

import math
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..errors import RasterValidationError
from ..provenance import DatasetRecord, md5_file
from ..raster import GeoGrid, Raster
from .registry import SRTM_GL1, SRTM_GL1N

N = 3601
DEG_PER_PX = 1.0 / 3600.0
SRTM_VOID = -32768
COVERAGE_NORTH, COVERAGE_SOUTH = 60.0, -56.0
WGS84_A = 6378137.0

_TILE_RE = re.compile(r"^([NS])(\d{2})([EW])(\d{3})$", re.I)

# SRTM User Guide V3, Table 2 "Fill Values of the .NUM files".
NUM_CODES = {
    1: "Water-masked SRTM void",
    2: "Water-masked SRTM non-void",
    5: "GDEM elevation = 0 in SRTM void",
    11: "NGA-interpolated SRTM",
    21: "GMTED2010 oversampled from 7.5 arc-second postings",
    25: "SRTM within GDEM",
    31: "NGA fill of SRTM via GDEM",
    51: "USGS NED",
    52: "USGS NED via GDEM",
    53: "Alaska USGS NED via GDEM",
    72: "Canadian Digital Elevation Data (CDED) via GDEM",
    # 101-200: ASTER scene count; 201-224: SRTM swath count
}


def classify_num(num: np.ndarray) -> dict[str, np.ndarray]:
    """Boolean masks: srtm (measured by SRTM), water (<6, per guide), fill (non-SRTM), unknown.

    Codes 11 (NGA-interpolated SRTM) and 25 (SRTM 3" oversampled within GDEM) are
    interpolated, not direct 1" SRTM measurements, so they are counted as fill.
    """
    num = num.astype(np.int16)
    srtm = (num >= 201) & (num <= 224)
    water = num < 6
    fill = np.isin(num, [11, 21, 25, 31, 51, 52, 53, 72]) | ((num >= 101) & (num <= 200))
    unknown = ~(srtm | water | fill)
    return {"srtm": srtm, "water": water, "fill": fill, "unknown": unknown}


@dataclass(frozen=True)
class TileId:
    lat: int  # latitude of the lower-left pixel centre
    lon: int  # longitude of the lower-left pixel centre (-180..179)

    @property
    def name(self) -> str:
        return f"{'N' if self.lat >= 0 else 'S'}{abs(self.lat):02d}{'E' if self.lon >= 0 else 'W'}{abs(self.lon):03d}"

    @classmethod
    def parse(cls, name: str) -> "TileId":
        m = _TILE_RE.match(name.strip())
        if not m:
            raise RasterValidationError([f"{name!r} is not an SRTM tile name like N38W111."])
        lat = int(m[2]) * (1 if m[1].upper() == "N" else -1)
        lon = int(m[4]) * (1 if m[3].upper() == "E" else -1)
        return cls(lat, lon)

    @classmethod
    def containing(cls, lat: float, lon: float) -> "TileId":
        return cls(math.floor(lat), math.floor(lon))


def coverage_status(lat: float, lon: float | None = None) -> str:
    """'inside' or 'outside_coverage' for the SRTM 60 N - 56 S band."""
    return "inside" if COVERAGE_SOUTH <= lat <= COVERAGE_NORTH else "outside_coverage"


def tile_in_coverage(tile: TileId) -> bool:
    return COVERAGE_SOUTH <= tile.lat and tile.lat + 1 <= COVERAGE_NORTH


def granule_urls(tile: TileId) -> dict[str, str]:
    """Download URLs (LP DAAC cloud, Earthdata Login required for 'lp-prod-protected')."""
    n = tile.name
    return {
        "hgt": f"{SRTM_GL1.access_url}{n}.SRTMGL1.hgt/{n}.SRTMGL1.hgt.zip",
        "num": f"{SRTM_GL1N.access_url}{n}.SRTMGL1N.num/{n}.SRTMGL1N.num.zip",
    }


def _extract_single_member(zip_path: Path, suffix: str, out_dir: Path) -> tuple[Path, str]:
    """Extract the one *.suffix member to out_dir after CRC check. Returns (path, member name)."""
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile as exc:
        raise RasterValidationError([f"{zip_path.name} is not a valid zip (interrupted download?). Re-download it."]) from exc
    with zf:
        members = [m for m in zf.infolist() if m.filename.lower().endswith(suffix)]
        if len(members) != 1:
            raise RasterValidationError([f"{zip_path.name}: expected one *{suffix} member, found {len(members)}."])
        m = members[0]
        if "/" in m.filename or "\\" in m.filename or m.filename.startswith(".."):
            raise RasterValidationError([f"{zip_path.name}: unsafe member path {m.filename!r}."])
        if zf.testzip() is not None:
            raise RasterValidationError([f"{zip_path.name}: CRC check failed. Re-download it."])
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / m.filename
        if not target.exists() or target.stat().st_size != m.file_size:
            with zf.open(m) as src, open(target, "wb") as dst:
                while block := src.read(1 << 20):
                    dst.write(block)
        return target, m.filename


@dataclass
class SrtmTile:
    tile: TileId
    hgt_path: Path
    num_path: Path | None
    grid: GeoGrid
    record: DatasetRecord


def open_srtm_tile(hgt_zip: str | Path, num_zip: str | Path | None, work_dir: str | Path) -> SrtmTile:
    """Validate an SRTMGL1 v3 tile zip (and its NUM zip). Members are extracted to ``work_dir``.

    A missing NUM file is not an error, but the tile is flagged and any analysis must
    treat its void-fill fraction as unknown.
    """
    hgt_zip = Path(hgt_zip)
    problems: list[str] = []
    m = re.match(r"^([NS]\d{2}[EW]\d{3})\.SRTMGL1\.hgt\.zip$", hgt_zip.name, re.I)
    if not m:
        raise RasterValidationError([
            f"{hgt_zip.name}: expected an LP DAAC SRTMGL1 v3 granule named like N38W111.SRTMGL1.hgt.zip."
        ])
    tile = TileId.parse(m[1])
    if not tile_in_coverage(tile):
        raise RasterValidationError([f"{tile.name} is outside SRTM coverage (60 N to 56 S); unavailable."])

    work_dir = Path(work_dir)
    hgt_path, hgt_member = _extract_single_member(hgt_zip, ".hgt", work_dir)
    if hgt_path.stat().st_size != N * N * 2:
        problems.append(f"{hgt_member} is {hgt_path.stat().st_size} bytes; a 1 arc-second tile is {N * N * 2}.")
    if not hgt_member.upper().startswith(tile.name):
        problems.append(f"Zip member {hgt_member!r} does not match tile {tile.name}.")

    num_path = None
    flags: list[str] = []
    if num_zip is None:
        flags.append("num_file_missing: SRTMGL1N source file not supplied; void-fill fraction unknown.")
    else:
        num_zip = Path(num_zip)
        if not num_zip.name.upper().startswith(f"{tile.name}.SRTMGL1N.NUM"):
            problems.append(f"NUM file {num_zip.name} does not belong to tile {tile.name}.")
        else:
            num_path, num_member = _extract_single_member(num_zip, ".num", work_dir)
            if num_path.stat().st_size != N * N:
                problems.append(f"{num_member} is {num_path.stat().st_size} bytes; expected {N * N} (one byte per pixel).")
    if problems:
        raise RasterValidationError(problems)

    grid = GeoGrid(
        body="EARTH", radius_m=WGS84_A, lat_top=tile.lat + 1 + DEG_PER_PX / 2,
        lon_west=tile.lon - DEG_PER_PX / 2, deg_per_pixel=DEG_PER_PX, rows=N, cols=N, ellipsoid="WGS84",
    )
    record = DatasetRecord(
        product_id=f"{tile.name}.SRTMGL1.hgt",
        data_set_id=SRTM_GL1.data_set_id,
        product_version=SRTM_GL1.final_product_version,
        doi=SRTM_GL1.doi,
        mission=SRTM_GL1.mission,
        instrument=SRTM_GL1.instrument,
        archive=SRTM_GL1.archive,
        access_url=granule_urls(tile)["hgt"],
        file_format="HGT: raw 16-bit signed big-endian, 3601x3601, no header (zipped)",
        license_or_terms="Openly shared without restriction per EOSDIS Data Use and Citation Guidance (LP DAAC catalog page)",
        body="EARTH",
        horizontal_reference="WGS84 geographic (lat/lon); pixel-centre registered on whole degrees",
        projection="Geographic (equirectangular lat/lon array), 1 arc-second",
        latitude_type="geodetic (WGS84)",
        longitude_convention="-180..180, positive east",
        vertical_reference=SRTM_GL1.vertical_reference,
        units="metre",
        scale_factor="none (integer metres)",
        offset="none",
        fill_value=f"{SRTM_VOID} (v1/v2 voids; none expected in v3)",
        citation=SRTM_GL1.citation + " ; " + SRTM_GL1N.citation,
        source_files=[hgt_zip.name] + ([Path(num_zip).name] if num_zip else []),
        checksum_md5="unknown (LP DAAC/CMR publish no checksum for this granule); local MD5 of zip: "
        + md5_file(hgt_zip),
        quality_flags=flags,
    )
    record.add_step("unzip", note="Zip CRC verified; member extracted unchanged to a working copy", member=hgt_member)
    return SrtmTile(tile=tile, hgt_path=hgt_path, num_path=num_path, grid=grid, record=record)


def read_window(t: SrtmTile, lat_min: float, lat_max: float, lon_min: float, lon_max: float,
                *, exclude_water: bool = True) -> Raster:
    """Windowed read (memmap). Water-masked pixels (NUM < 6) are set to NaN when exclude_water."""
    g = t.grid
    eps = 1e-9
    if not (lat_min < lat_max and lon_min < lon_max):
        raise RasterValidationError(["Window bounds must satisfy min < max."])
    if coverage_status(lat_min) != "inside" or coverage_status(lat_max) != "inside":
        raise RasterValidationError(["Window extends outside SRTM coverage (60 N to 56 S); unavailable."])
    if lat_min < g.lat_bottom - eps or lat_max > g.lat_top + eps or lon_min < g.lon_west - eps or lon_max > g.lon_east + eps:
        raise RasterValidationError([
            f"Window is outside tile {t.tile.name} (lat [{g.lat_bottom:.5f}, {g.lat_top:.5f}], "
            f"lon [{g.lon_west:.5f}, {g.lon_east:.5f}]). Multi-tile mosaics are not implemented."
        ])
    res = 1.0 / g.deg_per_pixel
    r0, r1 = int(math.floor((g.lat_top - lat_max) * res + 1e-6)), int(math.ceil((g.lat_top - lat_min) * res - 1e-6))
    c0, c1 = int(math.floor((lon_min - g.lon_west) * res + 1e-6)), int(math.ceil((lon_max - g.lon_west) * res - 1e-6))

    hgt = np.memmap(t.hgt_path, dtype=">i2", mode="r", shape=(N, N))
    raw = np.array(hgt[r0:r1, c0:c1])
    del hgt
    data = raw.astype(np.float64)
    voids = raw == SRTM_VOID
    data[voids] = np.nan

    record = t.record.model_copy(deep=True)
    fill_fraction = None
    stats: dict[str, float] = {"void_fraction": float(voids.mean())}
    if t.num_path is not None:
        nm = np.memmap(t.num_path, dtype=np.uint8, mode="r", shape=(N, N))
        num = np.array(nm[r0:r1, c0:c1])
        del nm
        cls = classify_num(num)
        if cls["unknown"].any():
            codes = sorted(set(np.unique(num[cls["unknown"]]).tolist()))
            raise RasterValidationError([f"NUM codes {codes} are not in the SRTM v3 User Guide table; cannot classify sources."])
        fill_fraction = cls["fill"].astype(np.float64)
        if exclude_water:
            data[cls["water"]] = np.nan
        stats.update({k + "_fraction": float(v.mean()) for k, v in cls.items() if k != "unknown"})
    else:
        record.quality_flags.append("void_fill_fraction_unknown: no NUM file")

    sub = GeoGrid(
        body="EARTH", radius_m=g.radius_m, lat_top=g.lat_top - r0 * g.deg_per_pixel,
        lon_west=g.lon_west + c0 * g.deg_per_pixel, deg_per_pixel=g.deg_per_pixel,
        rows=r1 - r0, cols=c1 - c0, ellipsoid=g.ellipsoid,
    )
    record.add_step(
        "crop", note="Snapped outward to whole pixels. No resampling."
        + (" Water-masked pixels (NUM<6) set to no-data." if exclude_water and t.num_path else ""),
        requested={"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
        actual={"lat_min": sub.lat_bottom, "lat_max": sub.lat_top, "lon_min": sub.lon_west, "lon_max": sub.lon_east},
        rows=[r0, r1], cols=[c0, c1], source_fractions=stats,
    )
    return Raster(data=data, grid=sub, record=record, fill_fraction=fill_fraction)
