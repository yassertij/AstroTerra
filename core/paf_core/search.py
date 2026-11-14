"""Earth candidate search over explicitly listed SRTM tiles, with coverage tracking.

Selection is never global: only the tiles the caller lists are examined, and the
coverage report says exactly which were examined, failed, unavailable, or outside SRTM
coverage. Each examined tile is aggregated to the target's grid spacing (block mean,
no upsampling) and cut into square candidate patches of ``patch_m`` with ``stride_m``.

Sensitivity to void fill: the scan is repeated with every non-SRTM-source pixel set to
no-data before aggregation (so any block touching fill becomes no-data), candidates are
re-ranked, and each baseline result records its rank in that run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from pydantic import BaseModel, Field

from . import DISCLAIMER, __version__
from .errors import JobCancelled, MetricError, PafError, RasterValidationError

ProgressFn = Callable[[float, str], None]
CancelFn = Callable[[], bool]


def _noop_progress(fraction: float, message: str) -> None:
    pass


def _never() -> bool:
    return False


def _check(should_cancel: CancelFn) -> None:
    if should_cancel():
        raise JobCancelled("Cancelled by request.")
from .metrics import TerrainMetrics, terrain_metrics
from .provenance import DatasetRecord
from .raster import Raster
from .resample import aggregate_to_spacing, native_spacing_m
from .similarity import Candidate, Ranking, features_from_metrics, rank_candidates
from .sources import mola_megdr, srtm_gl1

DEFAULT_WINDOWS_M = (5000.0, 10000.0, 20000.0)


class CoverageReport(BaseModel):
    selection_method: str
    tiles_requested: list[str]
    tiles_examined: list[str] = Field(default_factory=list)
    tiles_failed: dict[str, str] = Field(default_factory=dict)
    tiles_unavailable: dict[str, str] = Field(default_factory=dict)
    tiles_outside_coverage: list[str] = Field(default_factory=list)
    note: str = "Only the tiles listed above were examined. This is not global coverage."


@dataclass
class _Scan:
    candidates: list[Candidate] = field(default_factory=list)
    fill_excluded: list[Candidate] = field(default_factory=list)
    records: dict[str, DatasetRecord] = field(default_factory=dict)


def _patches(agg: Raster, patch_m: float, stride_m: float):
    i = agg.grid.rows // 2
    dy, dx = agg.grid.dy_m()[i], agg.grid.dx_m()[i]
    ky, kx = int(round(patch_m / dy)), int(round(patch_m / dx))
    sy, sx = max(1, int(round(stride_m / dy))), max(1, int(round(stride_m / dx)))
    for r0 in range(0, agg.grid.rows - ky + 1, sy):
        for c0 in range(0, agg.grid.cols - kx + 1, sx):
            yield r0, c0, ky, kx


def _candidate(tile: str, sub: Raster, r0: int, c0: int, native_m: float, windows_m, fill_override: float | None = None) -> Candidate:
    g = sub.grid
    region = {
        "tile": tile, "aggregated_rows": [r0, r0 + g.rows], "aggregated_cols": [c0, c0 + g.cols],
        "lat_min": g.lat_bottom, "lat_max": g.lat_top, "lon_min": g.lon_west, "lon_max": g.lon_east,
    }
    fill = fill_override if fill_override is not None else (
        None if sub.fill_fraction is None else float(np.mean(sub.fill_fraction)))
    flags: list[str] = []
    feats: dict[str, float] = {}
    try:
        tm = terrain_metrics(sub, windows_m)
        feats = features_from_metrics(tm)
        flags = [f for f in tm.flags if f not in sub.record.quality_flags]
    except MetricError as exc:
        flags.append(f"metrics_unavailable: {exc}")
    i = g.rows // 2
    v = sub.data[np.isfinite(sub.data)]
    elevation = None if v.size == 0 else {
        "mean": float(v.mean()), "std": float(v.std()), "min": float(v.min()), "max": float(v.max()),
    }
    return Candidate(
        candidate_id=f"{tile}_r{r0}_c{c0}", tile=tile, region=region, features=feats,
        valid_fraction=sub.valid_fraction, fill_fraction=fill, native_spacing_m=native_m,
        analysis_spacing_m=float(np.sqrt(g.dy_m()[i] * g.dx_m()[i])), flags=flags + list(sub.record.quality_flags),
        elevation_m=elevation,
    )


def scan_srtm_tiles(tile_names: list[str], raw_dir: Path, work_dir: Path, spacing_m: float,
                    patch_m: float, stride_m: float, windows_m=DEFAULT_WINDOWS_M,
                    progress: ProgressFn = _noop_progress, should_cancel: CancelFn = _never) -> tuple[_Scan, CoverageReport]:
    cov = CoverageReport(
        selection_method="Tiles listed explicitly by the user; no automatic or global selection.",
        tiles_requested=list(tile_names),
    )
    scan = _Scan()
    for k, name in enumerate(tile_names):
        _check(should_cancel)
        progress(k / max(1, len(tile_names)), f"Tile {k + 1}/{len(tile_names)}: {name}")
        try:
            tid = srtm_gl1.TileId.parse(name)
        except RasterValidationError as exc:
            cov.tiles_failed[name] = str(exc)
            continue
        if not srtm_gl1.tile_in_coverage(tid):
            cov.tiles_outside_coverage.append(tid.name)
            continue
        hgt = Path(raw_dir) / f"{tid.name}.SRTMGL1.hgt.zip"
        num = Path(raw_dir) / f"{tid.name}.SRTMGL1N.num.zip"
        if not hgt.exists():
            cov.tiles_unavailable[tid.name] = "elevation zip not downloaded"
            continue
        try:
            t = srtm_gl1.open_srtm_tile(hgt, num if num.exists() else None, work_dir)
            g = t.grid
            base = srtm_gl1.read_window(t, g.lat_bottom, min(g.lat_top, srtm_gl1.COVERAGE_NORTH), g.lon_west, g.lon_east)
            native = native_spacing_m(base)
            agg = aggregate_to_spacing(base, spacing_m)
            noff = None
            if base.fill_fraction is not None:
                masked = Raster(data=np.where(base.fill_fraction > 0, np.nan, base.data), grid=base.grid,
                                record=base.record.model_copy(deep=True), fill_fraction=np.zeros_like(base.fill_fraction))
                masked.record.add_step("exclude_non_srtm", note="Sensitivity run: non-SRTM (void-fill) pixels set to no-data")
                noff = aggregate_to_spacing(masked, spacing_m)
            del base
        except PafError as exc:
            cov.tiles_failed[tid.name] = str(exc)
            continue
        cov.tiles_examined.append(tid.name)
        scan.records[tid.name] = agg.record
        for r0, c0, ky, kx in _patches(agg, patch_m, stride_m):
            _check(should_cancel)
            scan.candidates.append(_candidate(tid.name, agg.subset(r0, r0 + ky, c0, c0 + kx), r0, c0, native, windows_m))
            if noff is not None:
                scan.fill_excluded.append(_candidate(tid.name, noff.subset(r0, r0 + ky, c0, c0 + kx), r0, c0, native, windows_m, 0.0))
    return scan, cov


class AnalysisResult(BaseModel):
    disclaimer: str = DISCLAIMER
    software_version: str = __version__
    is_synthetic: bool = False
    target: dict
    target_metrics: TerrainMetrics
    target_record: DatasetRecord
    earth_records: dict[str, DatasetRecord]
    settings: dict
    coverage: CoverageReport
    ranking: Ranking
    limitations: list[str]


def analyze_mars_target(megdr_label: Path, lat: float, lon: float, srtm_tiles: list[str], srtm_raw: Path,
                        work_dir: Path, patch_km: float = 40.0, stride_km: float = 10.0,
                        windows_m=DEFAULT_WINDOWS_M, weights: dict[str, float] | None = None,
                        progress: ProgressFn = _noop_progress, should_cancel: CancelFn = _never) -> AnalysisResult:
    progress(0.0, "Reading Mars target")
    product = mola_megdr.open_megdr(megdr_label)
    target = mola_megdr.read_window(product, *mola_megdr.window_from_center_km(product, lat, lon, patch_km))
    tm = terrain_metrics(target, windows_m)
    spacing = native_spacing_m(target)
    scan, cov = scan_srtm_tiles(
        srtm_tiles, srtm_raw, work_dir, spacing, patch_km * 1000, stride_km * 1000, windows_m,
        progress=lambda f, m: progress(0.05 + 0.85 * f, m), should_cancel=should_cancel,
    )
    _check(should_cancel)
    progress(0.9, "Ranking candidates")
    target_features = features_from_metrics(tm)
    ranking = rank_candidates(target_features, scan.candidates, weights)

    fill_note = "fill-excluded run not available (no NUM data)"
    if scan.fill_excluded:
        try:
            alt = rank_candidates(target_features, scan.fill_excluded, weights)
            alt_by_id = {r.candidate_id: r for r in alt.results}
            for r in ranking.results:
                a = alt_by_id.get(r.candidate_id)
                r.sensitivity["fill_excluded_rank"] = a.rank if a else None
                r.sensitivity["fill_excluded_distance"] = a.distance if a else None
                if a and a.excluded:
                    r.sensitivity["fill_excluded_exclusion"] = a.exclusion_reasons
            fill_note = "fill-excluded run: non-SRTM pixels set to no-data, normalisation recomputed"
        except MetricError as exc:
            fill_note = f"fill-excluded run failed: {exc}"
    ranking.flags.append(fill_note)
    progress(1.0, "Done")

    return AnalysisResult(
        target={"body": "MARS", "center_lat": lat, "center_lon_east": lon, "patch_km": patch_km,
                "bounds": {"lat_min": target.grid.lat_bottom, "lat_max": target.grid.lat_top,
                           "lon_min": target.grid.lon_west, "lon_max": target.grid.lon_east}},
        target_metrics=tm, target_record=target.record, earth_records=scan.records,
        settings={"patch_km": patch_km, "stride_km": stride_km, "windows_m": list(windows_m),
                  "analysis_spacing_m": spacing, "weights": "equal" if weights is None else weights},
        coverage=cov, ranking=ranking,
        limitations=[
            "Topographic statistics only; climate, vegetation, composition and geology are not compared.",
            "Compared at the coarser common grid spacing; finer Earth detail is averaged away.",
            "Mars topography is relative to the areoid and Earth to the EGM96 geoid; absolute elevations are not compared.",
            "MOLA MEGDR cells without observations are interpolated and cannot yet be identified.",
            "SRTM covers 60 N to 56 S only; only the listed tiles were examined.",
            "The distance is not a probability and the method is not empirically validated.",
        ],
    )
