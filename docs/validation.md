# Validation status

Last updated 2026-11-15 (software 0.2.0). "Verified" means checked by an automated test or a
recorded run on this machine (Windows 11, Python 3.12, Node 24). Nothing else is claimed.

## Scientific validation

**None against ground truth.** No reference set of accepted Mars–Earth or Moon–Earth
analogs was used, so the distance has not been shown to match expert judgement of analog
quality. The tests check that the computations do what the methodology says, and the
real-data checks below confirm that the inputs are read correctly. They do not show that the
method is scientifically right.

## Acceptance criteria (brief §12)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Frontend and backend correctly connected | **Verified in the web build** (browser, real API). Not verified inside the native app | Live run 2026-11-15: Moon analysis submitted from the Analyse page, polled and shown; every app call maps to an implemented endpoint ([api.md](api.md)) |
| 2 | Main workflow completes with real validated data | **Verified** for Mars and Moon targets vs SRTM N38W111 | Recorded runs below |
| 3 | Every reported value from a traceable computation | **Verified for displayed results**: the app shows only results that pass `validateResult`; every record carries processing history | `validate.ts` tests; provenance in results |
| 4 | Sources and assumptions documented | **Done** | [dataset cards](datasets/), [manifest.json](datasets/manifest.json), [methodology](methodology.md), [citations](citations.md) |
| 5 | Missing coverage and invalid data handled safely | **Verified** | exclusion, no-data, NaN/Inf, outside-coverage, truncated-file and wrong-label tests |
| 6 | Mars and Earth comparison passes the scientific tests | **Verified** | `test_scientific_acceptance.py` + existing metric/similarity tests |
| 7 | Lunar analysis enabled only after passing the same standards | **Verified**: Moon is offered only when a LOLA product passes label validation; same metrics, rules and tests; real-data cross-check passes | `test_lola_gdr.py`, `test_real_lola.py`, `test_api_hardening.py::test_moon_analysis_lifecycle`; UI test that Moon is disabled without a product |
| 8 | Rankings reproducible and explainable | **Verified** | Gale rerun identical to the 2026-11-14 record (below); seeded sensitivity; per-feature contributions |
| 9 | Exports agree with on-screen results | **Verified** (web build) | Real Moon run: on-screen table, `/result`, JSON export and CSV export identical for all 40 ranked rows; export has no coordinates by default |
| 10 | Android packaging and critical E2E flows pass | **Partly.** Debug and release APKs build; release manifest has cleartext off. **No emulator or device was available: nothing was run natively** | Gradle builds; merged-manifest check |
| 11 | Production configuration secure and documented | **Done in code and docs; hosting not deployed** | HTTPS rule in the app, debug-only cleartext, body/rate/queue limits, structured errors ([api.md](api.md)) |
| 12 | Limitations disclosed | **Done** | README, methodology, this file |

## Brief §9 scientific test cases

| Case | Test |
|---|---|
| Flat terrain → zero slope, relief, roughness | `test_scientific_acceptance.py::test_flat_terrain_has_zero_slope_relief_and_roughness` |
| Plane → predictable slope (Mars and Moon grids) | `test_metrics_slope.py`, `test_scientific_acceptance.py::test_plane_gives_predictable_slope_on_the_moon_grid` |
| Known step → known relief | `::test_known_step_gives_known_relief` |
| Identical patches → zero distance | `::test_identical_patches_processed_identically_give_zero_distance`, `test_similarity.py` |
| Missing data never improves a score | `::test_missing_data_never_improves_a_score`, `::test_no_data_blocks_stay_no_data_after_aggregation` |
| Incompatible grid rejected | `::test_incompatible_grid_rejected` (upsampling refused; >5 % spacing mismatch excluded) |

## Test inventory (all passing on 2026-11-15)

| Suite | Count | Notes |
|---|---|---|
| Python (`tests/`) | 154 passed, 0 skipped with all data present | includes 11 real-data tests (MOLA + SRTM 5, LOLA 6); they skip themselves when the files are absent. Was 112 before this repair |
| Mobile (`mobile/src/test`) | 50 passed | adds API-address rule, bounded retries, idempotency key reuse, result validation (7 corruption cases), stall stop/resume, Moon page and form |
| Typecheck / web build | clean | `tsc --noEmit`, `vite build` |
| Android | builds only | `assembleDebug`, `assembleRelease` (unsigned) |

## Recorded real-data runs

**Mars (reproduced 2026-11-15):** Gale crater (5.4° S, 137.8° E, 40 km, MEGDR v2.0) vs SRTM
N38W111, stride 10 km. 40 candidates, best distance 8.117. The rerun with software 0.2.0
matched the 2026-11-14 record exactly: same candidate ids, identical ranks, maximum distance
difference 0.0, identical target features.

**Moon (2026-11-15):** Taurus-Littrow valley (20.19° N, 30.77° E, 40 km, LDEM_64 V3.1) vs SRTM
N38W111, stride 10 km, effective target spacing 459 m. Target: mean height −1931 ± 584 m
above the 1737.4 km sphere; median slope 8.3°; relief 884 / 1609 / 2295 m at 5 / 10 / 20 km.
40 candidates ranked, none excluded; best distance 8.75, all 8.75–13.14. Interpretation: no
close topographic analog in this tile; the lunar massifs' relief is about three times that of
the best Earth patch. Saved as `data/processed/moon_taurus_littrow_vs_N38W111.json`.

**LOLA cross-check (real files):** at six random locations, the 4 × 4 block mean of LDEM_64
matched LDEM_16 with median absolute differences of 5–23 m (local relief 3.0–9.3 km), and a
one-pixel shift raised them to 14–113 m. This confirms registration, byte order and the
DN × 0.5 m scaling (no OFFSET added).

## Not verified / open

- **Native Android**: install, launch, permission prompts, networking from the WebView,
  export download inside the WebView, restart/offline behaviour. No emulator or device here.
- iOS: not built (needs macOS).
- Hosted deployment with TLS: documented, not deployed.
- MOLA and LOLA interpolated cells are not identified (count products not loaded).
- Earth region/country names: not provided (no verified geocoding source; shown as "not available").
- Multi-tile mosaics (target or Earth); only one SRTM tile per candidate.
- Colour-vision simulation and screen-reader walkthrough on devices.
