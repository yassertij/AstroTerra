# Dataset card — SRTM GL1 v3 and SRTMGL1N (Earth)

Sources: LP DAAC / Earthdata catalog pages for `SRTMGL1_003` and `SRTMGL1N_003`, NASA CMR
collection and granule records, and the *SRTM Collection User Guide* (revised Oct 2015,
<https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf>), read 2026-11-13.

| Field | SRTMGL1 (elevation) | SRTMGL1N (source number) |
|---|---|---|
| Short name / version | `SRTMGL1` / `003` | `SRTMGL1N` / `003` |
| DOI | 10.5067/MEASURES/SRTM/SRTMGL1.003 | 10.5067/MEASURES/SRTM/SRTMGL1N.003 |
| CMR concept id | C2763266360-LPCLOUD | C2763266368-LPCLOUD |
| Producer / archive | NASA JPL (with NGA) / NASA LP DAAC | same |
| Granule naming | `N38W111.SRTMGL1.hgt.zip` → `N38W111.hgt` | `N38W111.SRTMGL1N.num.zip` → `N38W111.num` |
| Tile | 1° × 1°, 3601 × 3601 | same grid |
| Data type | int16, big-endian, row-major from north, no header | uint8 (one byte per pixel) |
| Registration | Name = centre of lower-left pixel; edge pixels centred on whole degrees; edge rows/columns duplicated in neighbours | same |
| Horizontal reference | WGS84 geographic | same |
| Vertical reference | WGS84/EGM96 geoid | — |
| Units | metre | code |
| No-data | −32768 flags voids in v1/v2; v3 has no voids | — |
| Coverage | 60° N to 56° S | same |
| Access | `https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/SRTMGL1.003/<tile>.SRTMGL1.hgt/<tile>.SRTMGL1.hgt.zip` — **Earthdata Login required** (anonymous request → HTTP 401, verified) | `.../SRTMGL1N.003/<tile>.SRTMGL1N.num/<tile>.SRTMGL1N.num.zip` |
| Checksums | not published in CMR; zip CRC checked; local MD5 recorded | same |
| Terms | "openly shared, without restriction" per EOSDIS Data Use and Citation Guidance (catalog page) | same |

## Void fill (Version 3)

Voids were filled primarily from ASTER GDEM2, secondarily from GMTED2010 (7.5″, bicubic to 1″)
or, for the conterminous US, northern Mexico and Hawaii, from NED, using a modified Delta
Surface Fill. ASTER fills inconsistent with SRTM by ≥ 80 m were rejected and refilled.

## NUM codes (User Guide Table 2) and how they are used

| Code | Meaning | Class used here |
|---|---|---|
| 1 | Water-masked SRTM void | water (set to no-data) |
| 2 | Water-masked SRTM non-void | water |
| 5 | GDEM elevation = 0 in SRTM void | water (guide: codes < 6 are water) |
| 11 | NGA-interpolated SRTM | **fill** (interpolated) |
| 21 | GMTED2010 oversampled from 7.5″ | fill |
| 25 | SRTM within GDEM (SRTM 3″ oversampled) | **fill** (not direct 1″ SRTM) |
| 31 | NGA fill of SRTM via GDEM | fill |
| 51 / 52 / 53 | USGS NED / NED via GDEM / Alaska NED via GDEM | fill |
| 72 | Canadian DEM (CDED) via GDEM | fill |
| 101–200 | ASTER scene count | fill |
| 201–224 | SRTM swath count | **SRTM** |
| other | not in the table | rejected with an error |

## Tile used: N38W111 (38–39° N, 110–111° W, near Hanksville, Utah)

| File | Size | Local MD5 (2026-11-13) |
|---|---|---|
| `N38W111.SRTMGL1.hgt.zip` | 11,827,705 B (member 25,934,402 B) | `93525F7299231DA1D003AE77DFBC5B33` |
| `N38W111.SRTMGL1N.num.zip` | 392,681 B (member 12,967,201 B) | `8779DE6CE6555351C7A88EA5F6D975B2` |

Source shares over the whole tile: SRTM 98.51 %, fill 1.26 % (codes 11, 31, 51, 101–140),
water 0.23 %, voids 0. Elevation 1,096–3,510 m.

## Citations

- NASA JPL. (2013). NASA Shuttle Radar Topography Mission Global 1 arc second [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MEASURES/SRTM/SRTMGL1.003
- NASA JPL. (2013). NASA Shuttle Radar Topography Mission Global 1 arc second number [Data set]. NASA Land Processes Distributed Active Archive Center. https://doi.org/10.5067/MEASURES/SRTM/SRTMGL1N.003

## Not verified

- The non-void-filled SRTM control product (DOI 10.5066/F7K072R7, USGS EROS) — not used.
