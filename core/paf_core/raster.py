"""Planetary raster container on a geographic (lat/lon) grid.

The grid is edge-registered: (lat_top, lon_west) is the outer corner of the upper-left
pixel. For Mars/Moon, pixel spacing in metres comes from the sphere radius recorded in
the product label. For Earth, spacing comes from the named ellipsoid (WGS84) via
pyproj geodesics. The two are never mixed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyproj import Geod

from .provenance import DatasetRecord


@dataclass(frozen=True)
class GeoGrid:
    body: str
    radius_m: float  # sphere radius from the label (planets); ellipsoid semi-major axis for Earth
    lat_top: float  # degrees (planetocentric for Mars; geodetic WGS84 for Earth)
    lon_west: float  # degrees east (may be negative for Earth, -180..180)
    deg_per_pixel: float
    rows: int
    cols: int
    ellipsoid: str | None = None  # e.g. "WGS84" for Earth; None = sphere of radius_m
    lon_deg_per_pixel: float | None = None  # only when it differs from deg_per_pixel (latitude step)

    @property
    def lon_step(self) -> float:
        return self.lon_deg_per_pixel or self.deg_per_pixel

    @property
    def lat_bottom(self) -> float:
        return self.lat_top - self.rows * self.deg_per_pixel

    @property
    def lon_east(self) -> float:
        return self.lon_west + self.cols * self.lon_step

    def row_center_lats(self) -> np.ndarray:
        return self.lat_top - (np.arange(self.rows) + 0.5) * self.deg_per_pixel

    def dy_m(self) -> np.ndarray:
        """North-south pixel spacing per row (metres)."""
        lats = self.row_center_lats()
        if self.ellipsoid is None:
            return np.full(lats.shape, self.radius_m * np.radians(self.deg_per_pixel))
        h = self.deg_per_pixel / 2
        z = np.zeros_like(lats)
        return Geod(ellps=self.ellipsoid).inv(z, lats + h, z, lats - h)[2]

    def dx_m(self) -> np.ndarray:
        """East-west pixel spacing per row (metres); shrinks toward the poles."""
        lats = self.row_center_lats()
        if self.ellipsoid is None:
            return self.radius_m * np.cos(np.radians(lats)) * np.radians(self.lon_step)
        z = np.zeros_like(lats)
        return Geod(ellps=self.ellipsoid).inv(z, lats, z + self.lon_step, lats)[2]


@dataclass
class Raster:
    data: np.ndarray  # float64, metres; NaN = no valid data
    grid: GeoGrid
    record: DatasetRecord
    # Fraction (0..1) of each pixel's area coming from non-native sources (e.g. SRTM
    # void fill). None = unknown (MOLA without counts file).
    fill_fraction: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.data.shape != (self.grid.rows, self.grid.cols):
            raise ValueError(f"data shape {self.data.shape} != grid {(self.grid.rows, self.grid.cols)}")
        if self.fill_fraction is not None and self.fill_fraction.shape != self.data.shape:
            raise ValueError("fill_fraction shape must match data")

    @property
    def valid_mask(self) -> np.ndarray:
        return np.isfinite(self.data)

    @property
    def valid_fraction(self) -> float:
        return float(self.valid_mask.mean()) if self.data.size else 0.0
