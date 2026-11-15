# Planetary Analog Finder

Compares the **topography** of a Mars or Moon region with candidate regions on Earth, using
only NASA-archived elevation data, and ranks the Earth candidates by how similar their
terrain-shape statistics are.

> **Topographic analog assessment only.** Results are not proof of geological, chemical,
> biological or environmental equivalence. Climate, vegetation and composition are not
> compared. The score is a distance (lower = more similar), **not a probability**, and the
> method **has not been validated empirically**. SRTM covers **60° N to 56° S only**; SRTM
> voids were filled with non-SRTM sources; there is **no global coverage**.

| Layer | Folder | Tech |
|---|---|---|
| Scientific core | [`core/paf_core`](core/paf_core) | Python 3.12, NumPy, SciPy, PyProj, Pydantic, Rasterio/GDAL (installed; the MVP readers use label-driven NumPy memory maps) |
| API | [`api/paf_api`](api/paf_api) | FastAPI, SQLite job store, one background worker |
| Mobile app | [`mobile`](mobile) | React 19, Vite 8, Capacitor 8, exifr |

More: [audit](docs/audit.md) · [release checklist](docs/release-checklist.md) · [API & deployment](docs/api.md) · [architecture](docs/architecture.md) · [methodology](docs/methodology.md) ·
[dataset cards](docs/datasets/) · [citations](docs/citations.md) ·
[validation status](docs/validation.md) · [roadmap](docs/roadmap.md)

## Data sources (NASA only)

| Body | Product | Identifier | Archive |
|---|---|---|---|
| Mars | MOLA MEGDR, 128 px/deg topography, final version `PRODUCT_VERSION_ID = "2.0"` | `MGS-M-MOLA-5-MEGDR-L3-V1.0`, doi:10.17189/1519460 | NASA PDS Geosciences Node |
| Moon | LOLA GDR LDEM_64 (64 px/deg ≈ 474 m), product version V3.1 | `LRO-L-LOLA-4-GDR-V1.0`, doi:10.17189/tnyt-7007 (PDS4 bundle) | NASA PDS Geosciences Node |
| Earth | SRTM GL1 v3 elevation | `SRTMGL1.003`, doi:10.5067/MEASURES/SRTM/SRTMGL1.003 | NASA LP DAAC |
| Earth | SRTM GL1 v3 source numbers (NUM) | `SRTMGL1N.003`, doi:10.5067/MEASURES/SRTM/SRTMGL1N.003 | NASA LP DAAC |

SRTM GL1 v3 is distributed by NASA LP DAAC, but its voids were filled from non-SRTM sources
(ASTER GDEM, GMTED2010, USGS NED and others); the NUM file identifies them per pixel and
candidates with more than 5 % fill are excluded.

Excluded by policy: Copernicus DEM, SLDEM2015, and any product whose provenance cannot be
traced to NASA. The allow-list lives in [`registry.py`](core/paf_core/sources/registry.py);
anything else is rejected.

## Installation

Requirements: Windows, macOS or Linux; [uv](https://docs.astral.sh/uv/); Node.js 22+ (tested with 24); git.

### Backend (core + API)

```bash
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[api,dev]"
```

### Mobile app

```bash
cd mobile
npm ci
```

## Getting the data

Raw files go in `data/raw/` and are never modified (make them read-only after download).
They are excluded from Git.

### Mars: one MOLA MEGDR tile (no login)

The 128 px/deg topography tile covering Gale crater (0–44° S, 90–180° E):

```bash
mkdir -p data/raw/mola_megdr
curl -f -o data/raw/mola_megdr/megt00n090hb.lbl https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg128/megt00n090hb.lbl
curl -f -o data/raw/mola_megdr/megt00n090hb.img https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg128/megt00n090hb.img
```

Expected (from the volume checksum file `mgsl_300x_201204.md5`): `.img` 129,761,280 bytes,
MD5 `1F2C70C407976DD22E79DFBB3469EBF1`; `.lbl` 4,820 bytes, MD5 `3EA548315445CDEE09B54FCBBC722E14`.
Other tiles follow the naming `megt<lat><N|S><lon>hb` described on
<https://pds-geosciences.wustl.edu/missions/mgs/megdr.html>.

### Moon: LOLA LDEM_64 (no login, 531 MB)

```bash
mkdir -p data/raw/lola_gdr
curl -f -o data/raw/lola_gdr/ldem_64.lbl https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.lbl
curl -f -C - -o data/raw/lola_gdr/ldem_64.img https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img
```

Expected size 530,841,600 bytes (`RECORD_BYTES × FILE_RECORDS`). No checksum is published for
this file. Optional cross-check grid for the tests (33 MB): `ldem_16.lbl` / `ldem_16.img` from
the same folder into `data/raw/lola_crosscheck/`. See the [dataset card](docs/datasets/lola_gdr.md).
Until a validated LOLA product is present the Moon screen says lunar analysis is unavailable.

### Earth: SRTM GL1 v3 tile + NUM file (free NASA Earthdata Login required)

1. Register at <https://urs.earthdata.nasa.gov> and confirm the e-mail.
2. Run (Windows PowerShell); it asks for your username and password, does not echo or
   store the password, and deletes its temporary credentials afterwards:

```bash
powershell -ExecutionPolicy Bypass -File scripts/get_srtm_tile.ps1 -Tile N38W111
```

Tiles are named by the **centre of their lower-left pixel**, e.g. `N38W111` covers
38–39° N, 110–111° W. Only tiles between 60° N and 56° S exist. LP DAAC publishes no
checksum for these granules; the zip CRC is verified on load.

### Interpreting the labels

- **MEGDR** (PDS3 detached label): `SAMPLE_TYPE = MSB_INTEGER`, `SAMPLE_BITS = 16`,
  `UNIT = METER`; no `SCALING_FACTOR`, `OFFSET` or `MISSING_CONSTANT` (values are metres as
  stored). Grid: `SIMPLE CYLINDRICAL`, planetocentric, east-positive 0–360°, sphere
  radius `A/B/C_AXIS_RADIUS = 3396.0 km`. Topography = planetary radius − areoid radius
  (GMM3 mgm1025, degree/order 50). Cells without observations hold **interpolated** values.
- **SRTM HGT**: 3601 × 3601 big-endian int16, no header, rows from north; edge pixels
  centred on whole degrees (and duplicated in neighbouring tiles); metres above the
  WGS84/EGM96 geoid. **NUM**: one byte per pixel; codes < 6 water, 201–224 SRTM, other
  codes = void fill (ASTER GDEM, GMTED2010, NED, CDED, NGA). See the
  [dataset cards](docs/datasets/).

## Running

Commands below use the Windows venv path `.venv/Scripts/python`; on macOS/Linux use `.venv/bin/python`.

```bash
# API (http://127.0.0.1:8765, interactive docs at /docs)
.venv/Scripts/python -m uvicorn paf_api.main:create_app --factory --host 127.0.0.1 --port 8765
```

```bash
# Mobile app in a browser (http://127.0.0.1:5173)
npm --prefix mobile run dev
```

Environment variables (all optional): `PAF_DATA_DIR` (default `./data`), `PAF_DB_PATH`
(default `data/processed/paf_jobs.sqlite3`), `PAF_CORS_ORIGINS` (comma-separated), plus the
limits `PAF_MAX_BODY_BYTES`, `PAF_MAX_ACTIVE_JOBS`, `PAF_SUBMIT_RATE_PER_MINUTE`,
`PAF_JOB_RETENTION_DAYS` — see [docs/api.md](docs/api.md). `GET /v1/ready` reports whether the
server can run analyses.
A data directory containing a file named `SYNTHETIC` marks every result as synthetic demo data.

### Android APK (built, not yet run on a device or emulator)

Requirements: Android Studio's SDK (platform 36) and **JDK 21** (Capacitor 8 / Gradle 8.14
do not run on Android Studio's bundled Java 25).

Debug build (development: plain HTTP allowed, app served as `http://localhost`). The address
baked in by `VITE_PAF_API_BASE` is only the default; it can be changed in Settings:

```bash
cd mobile && VITE_PAF_API_BASE=http://10.0.2.2:8765 npm run build && npx cap sync android
```

```bash
cd mobile/android && set JAVA_HOME=C:\Users\<you>\.jdks\jdk-21.0.13.0.2+1 && gradlew.bat assembleDebug
```

Output: `mobile/android/app/build/outputs/apk/debug/app-debug.apk` (debug-signed; install
on your own phone, not for the Play Store).

Release build (HTTPS only): the web app must point to an `https://` API, Capacitor is synced
in release mode (app served as `https://localhost`, cleartext off), and the release build
type sets `usesCleartextTraffic="false"`:

```bash
cd mobile && VITE_PAF_API_BASE=https://<your-api-host> npm run build && PAF_RELEASE=1 npx cap sync android
```

```bash
cd mobile/android && gradlew.bat assembleRelease
```

This produces `app-release-unsigned.apk`; sign it with your own keystore (not in the repo). Permissions: coarse location, read images,
media location (needed for EXIF GPS on Android 10+); no camera permission (the system
camera app is used).

To use it on a phone, the API must be reachable on your network:

```bash
.venv/Scripts/python -m uvicorn paf_api.main:create_app --factory --host 0.0.0.0 --port 8765
```

then enter `http://<your-PC-LAN-IP>:8765` in the app's Settings (emulator: `http://10.0.2.2:8765`).
Settings accepts plain `http://` only for local/private addresses; anything else must be `https://`.
Allow port 8765 in your firewall yourself. The API has no authentication: anyone on the
same network can use it while it runs. Debug builds are served as `http://localhost` with
cleartext allowed so they can call this plain-HTTP backend; release builds are not.

iOS needs macOS with Xcode (`npx cap add ios`) plus photo-library and location usage
strings in `Info.plist`. **No native app has been run on a device or simulator yet.**

## Workflow example

1. Download the MEGDR tile and SRTM tile `N38W111` as above; start the API and the app.
2. **Analyse** tab: Mars target 5.4° S, 137.8° E (Gale crater), patch 40 km; tick `N38W111`; Run.
3. The status card shows progress; you can leave and come back, or cancel.
4. **Results**: 40 candidate patches, ranked. On real data (2026-11-14) the best distance
   was 8.12 with all candidates between 8.1 and 10.9 — i.e. no close analog in this tile,
   mainly because Gale's 20 km relief (~3,375 m) is several times larger than anything in it.
5. Export JSON or CSV (coordinates excluded by default).

The same through the API:

```bash
curl -X POST http://127.0.0.1:8765/v1/analyses -H "Content-Type: application/json" -d "{\"target\":{\"lat\":-5.4,\"lon_east\":137.8,\"patch_km\":40},\"earth_tiles\":[\"N38W111\"],\"stride_km\":10}"
```

Then poll `GET /v1/jobs/{id}`, fetch `GET /v1/jobs/{id}/result` or
`GET /v1/jobs/{id}/export?format=csv`.

## Photo location and privacy

- A photo can (1) give an Earth location to choose a candidate tile and (2) be attached to
  a candidate as a **photo observation** — a visual reference, never a measurement.
- EXIF GPS is read **on the device**. Device location is requested only when the user taps
  "Use device location", through the system permission prompt; declining is fine.
- Photo position and device position are shown separately, with the accuracy radius when
  available. Positions outside 60° N–56° S are reported as "outside coverage" and no
  analysis is offered.
- The coverage check runs on the device; only a **tile name** is ever used. Photos, EXIF
  data and coordinates are never sent to the server or any third party, are kept in memory
  for the session only, and can be deleted from Settings.
- EXIF GPS is often missing: privacy settings, social networks and screenshots remove it.
  A photo's position is where it was taken, not necessarily where the analysis is run. An
  Earth location only selects an Earth candidate; it never changes the Mars target.

## Exports

CSV and JSON record dataset identifiers, versions, DOIs, citations, vertical references,
label-derived grid details, processing history, settings, weights, normalisation
parameters, exclusion rules, sensitivity method, void-fill fractions, coverage, quality
flags, limitations, metric definitions, software version and timestamp.
**By default all coordinates and pixel offsets are removed** and candidates are relabelled
(`N38W111#1`…). Opt-in (`include_coordinates=true`) adds coordinates rounded to 0.01°
(~1 km). Exports never contain local paths, credentials, photos or device location.

## Tests

```bash
.venv/Scripts/python -m pytest
```

```bash
npm --prefix mobile test
```

```bash
npm --prefix mobile run typecheck
```

Tests that need the real downloaded tiles skip themselves when the files are absent.
See [validation status](docs/validation.md) for what is and is not covered.

## Limitations

- Topographic statistics only, compared at the coarser common grid (~462 m); finer Earth
  detail is averaged away and slope values describe that scale only.
- MOLA cells without observations are interpolated and cannot yet be identified.
- One MEGDR tile and single SRTM tiles per candidate (no mosaicking); the 40 km default
  patch is limited by the ~87 km width of an SRTM tile at 38° N.
- Candidate patches overlap (10 km stride); distances depend on the candidate pool used for
  normalisation, so compare distances only within one analysis.
- Not scientifically validated; no global coverage; native mobile builds not yet tested.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| App says "Cannot reach the analysis server" | Start the API; check the address in Settings (emulator: `10.0.2.2`). |
| `target_not_available` | No local MEGDR tile fully contains the target patch; move the target or download the tile. |
| SRTM download returns HTTP 401 | Earthdata username/password wrong or account not activated; sign in at urs.earthdata.nasa.gov first. |
| Tile listed as *unavailable* | The SRTM zip is not in `data/raw/srtm/`. |
| Candidates excluded with "void-fill fraction unknown" | The `*.SRTMGL1N.num.zip` file is missing. |
| "Only N eligible candidates" | Fewer than 3 candidates passed the exclusion rules; add tiles or use a smaller stride. |
| `pip` and `python` disagree on Windows | Use the uv-managed `.venv` as shown above. |
