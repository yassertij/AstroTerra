"""Aggregation to a common, coarser grid. Never upsamples.

Rule (owner-approved default): compare both sources on the coarser native spacing.
The finer raster is block-averaged by integer factors chosen so each output pixel is
as close as possible to ``target_m`` in each direction. An output pixel is valid only
when every input pixel in its block is valid (no partial blocks, no gap filling).
Resampling adds no information; the processing history says so.
"""

from __future__ import annotations

import numpy as np

from .errors import RasterValidationError
from .raster import GeoGrid, Raster

STRONG_MISMATCH_RATIO = 4.0


def native_spacing_m(r: Raster) -> float:
    """Geometric mean of N-S and E-W spacing at the raster's centre row (metres)."""
    i = r.grid.rows // 2
    return float(np.sqrt(r.grid.dy_m()[i] * r.grid.dx_m()[i]))


def aggregate_to_spacing(r: Raster, target_m: float) -> Raster:
    g = r.grid
    i = g.rows // 2
    fy = max(1, int(round(target_m / g.dy_m()[i])))
    fx = max(1, int(round(target_m / g.dx_m()[i])))
    if fy == 1 and fx == 1:
        raise RasterValidationError([
            f"Target spacing {target_m:.1f} m is not coarser than native spacing; upsampling is not allowed."
        ])
    rows, cols = g.rows // fy, g.cols // fx
    if rows < 3 or cols < 3:
        raise RasterValidationError([f"Window too small to aggregate by {fy}x{fx} (result {rows}x{cols})."])
    trimmed = r.data[: rows * fy, : cols * fx].reshape(rows, fy, cols, fx)
    data = trimmed.mean(axis=(1, 3))  # NaN in any input -> NaN output
    fill = None
    if r.fill_fraction is not None:
        fill = r.fill_fraction[: rows * fy, : cols * fx].reshape(rows, fy, cols, fx).mean(axis=(1, 3))
    grid = GeoGrid(
        body=g.body, radius_m=g.radius_m, lat_top=g.lat_top, lon_west=g.lon_west,
        deg_per_pixel=g.deg_per_pixel * fy, rows=rows, cols=cols, ellipsoid=g.ellipsoid,
        lon_deg_per_pixel=g.lon_step * fx,
    )
    out =Raster(data=data, grid=grid, record=r.record.model_copy(deep=True), fill_fraction=fill)
    out.record.add_step(
        "aggregate_block_mean",
        note="Block mean to a coarser common grid. Resampling adds no information. "
        "Blocks containing any no-data pixel are no-data. Trailing partial blocks dropped.",
        target_spacing_m=target_m, factor_rows=fy, factor_cols=fx,
        achieved_spacing_m={"dy": float(grid.dy_m()[rows // 2]), "dx": float(grid.dx_m()[rows // 2])},
    )
    return out


def resolution_comparison(a: Raster, b: Raster) -> dict:
    sa, sb = native_spacing_m(a), native_spacing_m(b)
    ratio = max(sa, sb) / min(sa, sb)
    return {
        "spacing_m": {"a": sa, "b": sb},
        "ratio": ratio,
        "strong_mismatch": ratio >= STRONG_MISMATCH_RATIO,
        "common_spacing_m": max(sa, sb),
    }
