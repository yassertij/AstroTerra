# Validation status

Last updated 2026-11-14. "Verified" means checked by an automated test or a recorded run on
this machine (Windows 11, Python 3.12.16, Node 24.19.0). Nothing else is claimed.

## Scientific validation

**None.** No reference dataset of accepted Mars–Earth analogs was used. The distance has not
been shown to correspond to expert judgement of analog quality. Software tests check that
the computations do what the methodology says, not that the method is scientifically right.

## MVP acceptance criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Backend and mobile run from a clean, documented environment | **Met for backend + web build.** Native iOS/Android **not verified** | Fresh `git clone` of commit cb3fa23 → README install steps → 107 Python tests passed, 5 real-data tests skipped (no data in a clone); `npm ci` → 25 tests passed, typecheck and build clean |
| 2 | Loads and validates a real MOLA MEGDR region | **Met** | `test_real_megdr.py`: MD5 = archive, 100 km Gale window |
| 3 | Loads and validates a real SRTM GL1 v3 tile with its NUM file | **Met** | `test_real_srtm.py`: N38W111, every NUM code documented |
| 4 | Metrics with explicit units and tested missing-data handling | **Met** | `test_metrics_slope.py`, `test_resample_windows.py` |
| 5 | Ranking with a documented, reproducible method | **Met** | `similarity.py`, `docs/methodology.md`, seeded sensitivity, `test_similarity.py` |
| 6 | Mobile interface explains scores and shows provenance | **Met in the web build** | `components.test.tsx`; live browser run |
| 7 | Photo import for location and reference, permissions and privacy | **Met in the web build / unit tests.** Native permission dialogs **not verified** | `lib.test.ts`, `components.test.tsx` |
| 8 | Exports without coordinates by default; settings recorded | **Met** | `test_export.py`; in-page fetch of the live export |
| 9 | Tests pass on core, API and mobile | **Met for unit/integration tests.** Native simulator E2E **not run** | counts below |
| 10 | No synthetic result presented as real | **Met** | `SYNTHETIC` marker → `is_synthetic` + disclaimer prefix + UI banner (tested) |
| 11 | Documentation matches implementation and limitations | Reviewed against the code at this commit | this folder |

## Test inventory (all passing at this commit)

| Suite | Count | Covers |
|---|---|---|
| Core (`tests/core`) | 88 (5 need the real tiles) | PDS3 parser; allow-list rejects SLDEM2015/Copernicus/unknown; MD5; MEGDR validation (version, units, projection offsets, radius, planetographic/west-positive, radius/count products, truncated download, missing image); SRTM (registration, NUM table, unknown codes, missing NUM, voids, wrong size, corrupt zip, mismatched NUM, coverage edges, WGS84 spacing vs independent geodesic); slope vs analytic planes (north, east with latitude), flat, gaps; aggregation (no upsampling, NaN blocks, fill fractions); relief/roughness (plane → 0, controlled noise); ranking (identical → 0, hand-computed distance, weights, exclusions, zero-MAD, too few, seeded sensitivity); end-to-end search with coverage report; real-data tests (5) |
| API (`tests/api`) | 24 | Read endpoints, coverage check, 8 invalid-request cases, target not available, full job lifecycle, result-not-ready, cancel queued and running, failures and worker survival, restart recovery, no coordinates in logs, exports (default/opt-in/errors), CORS |
| Mobile (`mobile/src/test`) | 25 | WCAG contrast of every palette pair used (and the failing pairs avoided); on-device coverage; EXIF with GPS / without / malformed / not an image; permission granted / declined; Photo screen privacy (no coordinates in any request) and coverage; Results explanation, exclusions, provenance, private exports; job recovery after network loss |

## Recorded real-data run (2026-11-14)

Gale crater target (5.4° S, 137.8° E, 40 km patch, MEGDR v2.0) vs SRTM tile N38W111
(40 patches, 10 km stride, common spacing 462 m): best distance 8.12, all candidates
8.12–10.89, none excluded. Top candidate first in 90 % of weight-perturbation runs; rank 2 in
the void-fill-excluded run. Interpretation: no close topographic analog in this tile, chiefly
because the target's 20 km relief (3,375 m) far exceeds the tile's.

## Not verified / open

- Native iOS and Android builds, permission dialogs, photo picker EXIF behaviour (iOS may
  remove GPS from picked photos), file download inside native webviews.
- Colour-vision-deficiency simulation of the palette and charts.
- Screen-reader walkthrough on real devices (only semantic structure and keyboard access in the browser).
- MOLA interpolated-cell identification (MEGC counts), PDS4 MEGDR, non-void-filled SRTM control.
- Performance beyond one MEGDR tile and a handful of SRTM tiles.
