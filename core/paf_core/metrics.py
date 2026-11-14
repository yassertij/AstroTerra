"""Terrain metrics with explicit units. Shape metrics only are comparable across bodies.

Slope (degrees, [0, 90))
    dz/dx = (z[i, j+1] - z[i, j-1]) / (2 dx_i),  dz/dy = (z[i-1, j] - z[i+1, j]) / (2 dy_i)
    slope = degrees(arctan(sqrt(dz/dx^2 + dz/dy^2)))
    dx_i, dy_i in metres from the body geometry (label sphere radius, or WGS84 for Earth).
    Edge pixels and pixels with any invalid 4-neighbour are NaN (no one-sided
    differences, no gap filling). Slope depends on grid spacing.

Window metrics (windows defined in metres, converted to whole pixels per raster)
    The raster is cut into non-overlapping k_y x k_x pixel windows,
    k = round(window_m / spacing). A window is used only if its valid fraction is
    >= MIN_WINDOW_VALID_FRACTION.
    - local relief (m)  = max(z) - min(z) within the window.
    - roughness (m)     = standard deviation of residuals from a least-squares plane
                          z = a + b x + c y fitted to the window (x, y in metres),
                          i.e. detrended RMS height.
    Each metric is summarised by the median over used windows.

Elevation mean/std (m) are reported per source but are NOT comparable across bodies:
Mars topography is relative to the areoid, Earth heights to the EGM96 geoid.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from .errors import MetricError
from .raster import Raster

MIN_VALID_SLOPE_PIXELS = 25
MIN_WINDOW_VALID_FRACTION = 0.8
MIN_WINDOW_PIXELS = 3


class SlopeStats(BaseModel):
    units: str = "degree"
    pixel_spacing_m: dict[str, float]
    valid_fraction: float  # fraction of pixels where slope could be computed
    n_valid: int
    median: float
    mean: float
    p90: float
    method: str = "central differences, metric spacing from body geometry, no edge/gap filling"


class WindowMetric(BaseModel):
    window_m: float
    window_px: tuple[int, int]  # (rows, cols)
    n_windows_used: int
    n_windows_rejected: int
    local_relief_m_median: float
    roughness_m_median: float


class TerrainMetrics(BaseModel):
    body: str
    valid_fraction: float
    fill_fraction: float | None  # mean non-native-source fraction; None = unknown
    elevation_mean_m: float
    elevation_std_m: float
    elevation_note: str = "Elevation is relative to the source's own vertical datum; not comparable across bodies."
    slope: SlopeStats
    windows: list[WindowMetric]
    flags: list[str] = []


def slope_degrees(raster: Raster) -> np.ndarray:
    z = raster.data
    if z.ndim != 2 or min(z.shape) < 3:
        raise MetricError(f"Slope needs at least a 3x3 grid; got shape {z.shape}.")
    dx = raster.grid.dx_m()[1:-1, None]
    dy = raster.grid.dy_m()[1:-1, None]
    out = np.full(z.shape, np.nan)
    dzdx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2.0 * dx)
    dzdy = (z[:-2, 1:-1] - z[2:, 1:-1]) / (2.0 * dy)
    out[1:-1, 1:-1] = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))  # NaN propagates
    return out


def slope_stats(raster: Raster) -> SlopeStats:
    s = slope_degrees(raster)
    v = s[np.isfinite(s)]
    if v.size < MIN_VALID_SLOPE_PIXELS:
        raise MetricError(
            f"Only {v.size} valid slope pixels (minimum {MIN_VALID_SLOPE_PIXELS}); "
            "enlarge the window or choose an area with more valid data."
        )
    dx, dy = raster.grid.dx_m(), raster.grid.dy_m()
    return SlopeStats(
        pixel_spacing_m={"dy_min": float(dy.min()), "dy_max": float(dy.max()),
                         "dx_min": float(dx.min()), "dx_max": float(dx.max())},
        valid_fraction=float(v.size / s.size),
        n_valid=int(v.size),
        median=float(np.median(v)),
        mean=float(v.mean()),
        p90=float(np.percentile(v, 90)),
    )


def _plane_residual_std(z: np.ndarray, x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(z)
    A = np.column_stack([np.ones(ok.sum()), x[ok], y[ok]])
    coef, *_ = np.linalg.lstsq(A, z[ok], rcond=None)
    return float(np.std(z[ok] - A @ coef))


def window_metrics(raster: Raster, window_m: float) -> WindowMetric:
    g = raster.grid
    dy, dx = g.dy_m(), g.dx_m()
    i = g.rows // 2
    ky, kx = int(round(window_m / dy[i])), int(round(window_m / dx[i]))
    if ky < MIN_WINDOW_PIXELS or kx < MIN_WINDOW_PIXELS:
        raise MetricError(
            f"A {window_m / 1000:g} km window is only {ky}x{kx} pixels at this resolution "
            f"(minimum {MIN_WINDOW_PIXELS}); use a larger window."
        )
    ny, nx = g.rows // ky, g.cols // kx
    if ny == 0 or nx == 0:
        raise MetricError(f"Raster ({g.rows}x{g.cols} px) is smaller than one {window_m / 1000:g} km window.")
    # Local metric coordinates (metres) for every pixel, from cumulative spacing.
    ycoord = -np.concatenate([[0.0], np.cumsum(dy[:-1])])[:, None] * np.ones((1, g.cols))
    xcoord = np.arange(g.cols)[None, :] * dx[:, None]
    relief, rough, rejected = [], [], 0
    for a in range(ny):
        for b in range(nx):
            sl = (slice(a * ky, (a + 1) * ky), slice(b * kx, (b + 1) * kx))
            z = raster.data[sl]
            if np.isfinite(z).mean() < MIN_WINDOW_VALID_FRACTION:
                rejected += 1
                continue
            relief.append(float(np.nanmax(z) - np.nanmin(z)))
            rough.append(_plane_residual_std(z, xcoord[sl], ycoord[sl]))
    if not relief:
        raise MetricError(
            f"No {window_m / 1000:g} km window has valid fraction >= {MIN_WINDOW_VALID_FRACTION}."
        )
    return WindowMetric(
        window_m=window_m, window_px=(ky, kx), n_windows_used=len(relief), n_windows_rejected=rejected,
        local_relief_m_median=float(np.median(relief)), roughness_m_median=float(np.median(rough)),
    )


def terrain_metrics(raster: Raster, windows_m: tuple[float, ...] = (5000.0, 10000.0, 20000.0)) -> TerrainMetrics:
    v = raster.data[np.isfinite(raster.data)]
    if v.size == 0:
        raise MetricError("Raster has no valid pixels.")
    flags = list(raster.record.quality_flags)
    wins = []
    for w in windows_m:
        try:
            wins.append(window_metrics(raster, w))
        except MetricError as exc:
            flags.append(f"window_{w / 1000:g}km_unavailable: {exc}")
    return TerrainMetrics(
        body=raster.grid.body,
        valid_fraction=raster.valid_fraction,
        fill_fraction=None if raster.fill_fraction is None else float(np.mean(raster.fill_fraction)),
        elevation_mean_m=float(v.mean()),
        elevation_std_m=float(v.std()),
        slope=slope_stats(raster),
        windows=wins,
        flags=flags,
    )
