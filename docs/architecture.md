# Architecture

Three independent layers. Scientific logic exists only in the core.

```
mobile (React + Capacitor)  --HTTP/JSON-->  api (FastAPI)  --calls-->  core (paf_core)
  UI, photo/EXIF, on-device                 validation, jobs,          ingestion, validation,
  coverage check, polling                   SQLite, exports            metrics, similarity, search
                                                                         |
                                                                data/raw (read-only originals)
                                                                data/processed (derived, cache)
```

## Core — `core/paf_core`

| Module | Responsibility |
|---|---|
| `pds3.py` | PDS3 ODL label parser (text only; never evaluates label content) |
| `sources/registry.py` | NASA-only allow-list with verified IDs, DOIs, citations, sources of verification |
| `sources/mola_megdr.py` | MEGDR topography loader and validator; windowed reads via memory map |
| `sources/srtm_gl1.py` | SRTM GL1 v3 HGT + SRTMGL1N NUM loader; zip CRC; coverage; void-fill classification |
| `raster.py` | `GeoGrid` (edge-registered lat/lon grid; spacing from label sphere radius or WGS84) and `Raster` |
| `resample.py` | Block-mean aggregation to the coarser common grid (no upsampling) |
| `metrics.py` | Slope, local relief, roughness; quality flags; explicit errors instead of substitutes |
| `similarity.py` | Features, robust normalisation, distance, exclusions, weight sensitivity |
| `search.py` | Explicit-tile Earth scan, candidate patches, coverage report, fill-excluded rerun, `AnalysisResult` |
| `export.py` | CSV/JSON exports, coordinate scrubbing / rounding |
| `provenance.py` | `DatasetRecord` (file names only), processing steps, MD5 helpers |

Readers: the MVP reads both formats with label/guide-driven NumPy memory maps (a few
lines, fully tested, no hidden GDAL driver assumptions). Rasterio/GDAL is installed for
later formats (e.g. GeoTIFF exports, PDS4).

## API — `api/paf_api`

- `/v1` endpoints: health, sources, datasets, coverage/check, analyses, jobs, cancel, result, export.
- `JobStore` (SQLite) + one `Worker` thread. States: queued → running → succeeded | failed | cancelled.
  Cancellation is cooperative (checked between tiles and patches). Jobs interrupted by a
  restart are marked failed.
- Errors: `{"error": {"code", "message", "details"}}`. Requests with unknown fields are rejected.
- Logs contain job ids and states only. CORS: Vite dev server and Capacitor webviews only.
- Hosting: **to choose**. MVP runs locally, bound to 127.0.0.1, no authentication or TLS.

## Mobile — `mobile/`

- Six tabs: Overview, Analyse, Results, Photo, Sources, Settings.
- `lib/api.ts` (client, timeouts, structured errors), `lib/useJob.ts` (polling, resume, backoff),
  `lib/photo.ts` (EXIF via exifr, Capacitor Geolocation), `lib/coverage.ts` (on-device SRTM check),
  `lib/palette.ts` + `lib/contrast.ts` (palette and WCAG checks).
- The app never downloads DEM tiles; it receives JSON results only.

## Data layout

```
data/raw/mola_megdr/   megt00n090hb.lbl, .img          (read-only)
data/raw/srtm/         N38W111.SRTMGL1.hgt.zip, ...N.num.zip (read-only)
data/processed/srtm/   extracted .hgt/.num working copies (recreatable)
data/processed/        paf_jobs.sqlite3, analysis JSON
```

## Persistence and security

- SQLite for jobs/results; rasters on the backend file system only.
- No credentials in the repository. The Earthdata download script keeps the password in a
  temporary file that is deleted at exit.
- Downloaded data and image metadata are parsed as data, never executed; zip members with
  path components are rejected.
