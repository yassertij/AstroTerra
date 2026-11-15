# Methodology

Status: **not empirically validated.** No reference set of known terrestrial analogs has
been used to test whether low distances correspond to expert-recognised analogs.

## 1. Inputs and references

| Source | Grid | Vertical reference | Units |
|---|---|---|---|
| MOLA MEGDR (Mars) | 1/128° simple cylindrical, planetocentric, 0–360° E, sphere R = 3,396,000 m (from label) | Areoid GMM3 (mgm1025), degree/order 50 | m |
| LOLA LDEM_64 (Moon) | 1/64° simple cylindrical, planetocentric (Mean Earth/Polar Axis frame), 0–360° E, global, sphere R = 1,737,400 m (from label) | Sphere of radius 1737.4 km. HEIGHT = DN × 0.5 m; the label `OFFSET` (1,737,400 m) is the reference radius and is **not** added | m |
| SRTM GL1 v3 (Earth) | 1″ geographic, WGS84, pixel-centre on whole degrees | EGM96 geoid | m |

Absolute elevations are **never** compared across bodies: only terrain-shape statistics are.

## 2. Pixel spacing

Mars and Moon (sphere of radius *R* from the label), for a row at latitude φ and angular step Δ (rad):

    dy = R · Δφ          dx(φ) = R · cos φ · Δλ

Earth: geodesic lengths on the WGS84 ellipsoid (PyProj `Geod.inv`) between the edges of
each row's pixel, north–south and east–west.

## 3. Common grid (resolution mismatch rule)

The target's native spacing is the common spacing (MOLA ≈ 463 m; LOLA LDEM_64 ≈ 474 m,
chosen because it is the LOLA grid closest to MOLA's, so both bodies are compared at nearly
the same scale). The finer raster
(SRTM ≈ 24–31 m) is block-averaged with integer factors `f_y = round(s/dy)`,
`f_x = round(s/dx)` (e.g. 15 × 19 at 38° N → 462.5 × 460.4 m). A block containing any
no-data pixel is no-data. Upsampling is refused. A native-spacing ratio ≥ 4 is flagged as
a strong mismatch (Gale vs SRTM: 16.9). **Resampling adds no information.**

Grid compatibility check: integer factors cannot hit the target spacing exactly, so each
candidate's achieved analysis spacing is compared with the target's. If they differ by more
than 5 % (`MAX_SPACING_MISMATCH`), the candidate is not compared and is excluded with the
reason `grid_incompatible`. Window sizes are converted to whole pixels using the spacing at
the patch's centre row.

## 4. Terrain metrics

All metrics are computed per candidate patch (default 40 km × 40 km) on the common grid.

**Slope (degrees, 0 ≤ s < 90)** — central differences:

    ∂z/∂x = (z[i, j+1] − z[i, j−1]) / (2 dx_i)
    ∂z/∂y = (z[i−1, j] − z[i+1, j]) / (2 dy_i)
    s = atan( sqrt( (∂z/∂x)² + (∂z/∂y)² ) )  (in degrees)

Edge pixels and pixels with an invalid 4-neighbour are no-data (no one-sided differences,
no gap filling). Summary: median (also mean, 90th percentile). At least 25 valid slope
pixels are required, otherwise an error is returned.

**Windows** — defined in metres (default 5, 10, 20 km), converted per raster to
`k = round(w / spacing)` pixels (≥ 3, else the window size is reported unavailable).
The patch is tiled with non-overlapping windows; a window is used only if ≥ 80 % of its
pixels are valid.

**Local relief (m)** = max(z) − min(z) in a window; summarised by the median over windows.

**Roughness (m)** = standard deviation of residuals from a least-squares plane
`z = a + b·x + c·y` fitted to the window's valid pixels (x, y in metres); median over windows.

**Valid fraction** = valid pixels / all pixels. **Fill fraction** (Earth) = mean share of
each common-grid pixel coming from non-SRTM NUM codes. For Mars and the Moon the interpolated share is
unknown and flagged (MOLA: cells without shots are interpolated; LOLA: GMT `surface` was used
where coverage is incomplete; count products are not loaded).

Limitations: slope, relief and roughness are scale-dependent and describe the ~462 m grid
only; MOLA interpolation smooths terrain between tracks (gaps up to 12 km per the label).

## 5. Similarity

Features *f* (7): median slope; relief at 5/10/20 km; roughness at 5/10/20 km.

Normalisation over the *eligible* Earth candidates *c*:

    s_f = 1.4826 · median_c | x_cf − median_c(x_cf) |

A feature with `s_f = 0` is dropped and reported.

Distance between target *t* and candidate *c* with weights *w_f* (default equal):

    z_f = (t_f − c_f) / s_f
    D   = sqrt( Σ_f w_f z_f² / Σ_f w_f )

**Lower D = more similar; D = 0 for identical features.** D is in robust standard-deviation
units relative to this candidate pool. It is not a probability and is not comparable across
analyses with different candidate pools.

Contribution of feature *f*: `w_f z_f² / Σ_g w_g z_g²` (sums to 1).

## 6. Exclusion rules

A candidate is excluded, with the reason recorded, if: valid fraction < 0.8; non-SRTM
fill fraction > 0.05; fill fraction unknown (no NUM file); any feature unavailable; or its
grid is incompatible with the target's (see §3).
At least 3 eligible candidates are required.

## 7. Sensitivity

- **Weights**: 500 runs, each weight multiplied by U(0.5, 1.5), seed 20261113. Reported per
  candidate: median rank, 5th–95th percentile rank, fraction of runs at the baseline rank,
  fraction ranked first.
- **Void fill**: the whole scan is repeated with every non-SRTM pixel set to no-data before
  aggregation; normalisation is recomputed; each candidate's rank in that run is reported.
- **Non-void-filled SRTM control** (DOI 10.5066/F7K072R7): not used — its identity was not
  verified.

## 8. Lunar specifics

- Product LDEM_64, data set `LRO-L-LOLA-4-GDR-V1.0`, product version V3.1 (label). Global,
  so windows that cross 0°/360° E are read from both ends of the grid and joined.
- Projection offsets follow the volume's `dsmap.cat` (zero-based offsets, `LINE =
  NINT(LINE_PROJECTION_OFFSET − RES·(LAT − CENTER_LATITUDE)) + 1`); the reader checks that
  the label's offsets put the outer grid edge at line/sample 0.5 under this convention.
- Windows within 0.5° of latitudes −45°, 0° or 45° are flagged (`near_band_edge`): the label
  warns of possible artifacts at the 45° latitude bands in which the grid was produced.
- Registration and scaling are cross-checked on the real files: a 4 × 4 block mean of
  LDEM_64 is compared with the independent LDEM_16 grid (`tests/core/test_real_lola.py`).
- Lunar terrain at ~474 m is smoothed by interpolation where LOLA tracks are sparse
  (especially at low latitudes); slope and roughness there describe the gridded surface, not
  necessarily the true surface.

## 9. Reproducibility

Every result records dataset IDs and versions, processing history (crop windows, snapping,
aggregation factors, achieved spacing), settings, weights, normalisation parameters,
exclusion rules, sensitivity seed and software version. Given the same raw files and
settings the pipeline is deterministic.
