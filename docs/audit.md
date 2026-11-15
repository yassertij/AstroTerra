# Audit — Planetary Analog Finder (2026-11-15)

Scope: the whole repository at commit `6d29b83` (core, API, mobile web app, Android project,
docs, tests, data folder). Method: read every source file, ran the existing test suites,
inspected the real data files on disk and the NASA archive pages they come from.
The status of each item after repair is in the [traceability table](#traceability) and in
[validation.md](validation.md).

## 1. What is actually present

| Layer | Finding |
|---|---|
| Frontend | React 19.3, Vite 8, TypeScript 7, hash routes `overview, earth, moon, mars, compare, analysis, method, settings`; state in `App.tsx` + `useJob` hook (job id kept in `localStorage`). Leaflet map with NASA GIBS Blue Marble basemap. |
| Android | Capacitor 8.6 project in `mobile/android` (Gradle 8.14, SDK 36, JDK 21). Debug APK previously built (`dist/PlanetaryAnalogFinder-0.1.0-debug.apk`), never run on a device. |
| Backend | FastAPI, `/v1` prefix: `health, sources, datasets, coverage/check, analyses, jobs, jobs/{id}, jobs/{id}/cancel, jobs/{id}/result, jobs/{id}/export`. SQLite job table, one worker thread. |
| Config | `PAF_DATA_DIR`, `PAF_DB_PATH`, `PAF_CORS_ORIGINS`. App API base defaults to `http://127.0.0.1:8765`, editable in Settings. |
| Science | `paf_core`: PDS3 label parser; MOLA MEGDR reader (label-driven, validated); SRTM GL1 v3 reader with mandatory NUM source file; slope (central differences on metric spacing), local relief and detrended roughness on 5/10/20 km windows; block-mean aggregation (never upsamples); robust (MAD) normalisation, weighted Euclidean distance, exclusions, seeded weight-sensitivity and void-fill sensitivity runs. |
| Data on disk | `megt00n090hb` (MOLA MEGDR v2.0, MD5 matches archive), SRTM `N38W111` + NUM. No lunar data. |
| Tests | 112 Python tests pass (incl. 5 real-data tests), 25 mobile tests. |

The interface leads given in the brief were checked: Mars does use MOLA MEGDR
(`MGS-M-MOLA-5-MEGDR-L3-V1.0`, product version 2.0, verified against the label); Earth uses
SRTM GL1 v3; GIBS is basemap imagery only (it is never read by the pipeline); lunar LOLA is
not integrated (Moon page says so); job submission/result retrieval is real and works end to
end; Earth candidates have no country/region names (the app says "not available").

## 2. Confirmed defects

| ID | Area | Severity | Defect |
|---|---|---|---|
| B1 | API | High | Jobs still `queued` when the server stops are never run after restart: the queue is in memory, only `running` jobs are marked failed. The app would poll them forever. |
| B2 | API | Medium | No readiness endpoint (DB writable, worker alive, data present); only `/health`. |
| B3 | API | High | `weights` accept `NaN`/`Infinity` (Python's JSON parser allows them; `x < 0` and `sum <= 0` are both false for NaN), which would make every distance NaN. |
| B4 | API | Medium | No duplicate-submission protection: a retried or double-tapped submit queues the same analysis twice. |
| B5 | API | Medium | No request-size limit, no rate limit, no cap on queued jobs. |
| B6 | API | Medium | Unhandled exceptions in request handlers return Starlette's plain-text 500 instead of the structured error format. |
| B7 | API | Low | Finished jobs (including results) are kept forever; no retention rule. |
| S1 | Science | High | Lunar pipeline absent (no LOLA reader, no Moon target, no allow-list entry). |
| S2 | Science | High (latent) | The MEGDR reader computes `DN * SCALING_FACTOR + OFFSET`. That is correct for MEGDR (no scale/offset declared) but **wrong for LOLA**, whose `OFFSET = 1737400 m` is the reference-sphere radius: height is `DN * 0.5` only (label note). Reusing the reader would silently turn heights into radii. |
| S3 | Science | Medium | The Earth grid is aggregated by integer factors, so its achieved spacing can differ from the target's; nothing checks that the difference is small, so a mis-matched grid would be compared silently. |
| S4 | Science | Low | No single test file demonstrates the brief's scientific acceptance cases (step → known relief, missing data never improves a score, incompatible grid rejected); some are covered only indirectly. |
| F1 | App | High | Default API base `http://127.0.0.1:8765` is the phone itself on a device; there is no build-time production URL. |
| F2 | App | High | The result JSON is displayed without validation; a malformed or partial response would be shown as a completed analysis. |
| F3 | App | Medium | Only job polling retries; reads (`datasets`, `health`) fail on the first transient error, and submit has no idempotency key, so it cannot be retried safely. |
| F4 | App | Medium | Polling never ends while a job stays `queued`/`running` (e.g. orphaned by B1); no stall detection. |
| F5 | App | Medium | All result wording is hard-coded to "Mars target"; a Moon result would be mislabelled. |
| F6 | App | Low | Earth map does not state that the GIBS basemap is imagery, not the elevation source. |
| X1 | Android | High | Release builds would allow cleartext HTTP to any host (`usesCleartextTraffic="true"`, `androidScheme: "http"`) — production must use HTTPS. |

## 3. Suspected / unverifiable here

- Export download inside the Android WebView (an `<a download>` link to the API): likely does
  nothing in a Capacitor WebView. Needs a device; not verifiable here.
- Native permission prompts (location, media) — need a device or emulator.
- No reverse geocoder exists; region names are honestly shown as unavailable.

## 4. Missing infrastructure

- An Android emulator or device for E2E tests (none attached to this machine).
- TLS-terminated hosting for the API (a hosting decision for the owner).
- An authoritative source for Earth place names (not added; see §7).

## 5. Security risks

- Cleartext HTTP in release (X1). API has no authentication — acceptable only on a trusted
  network; documented. No secrets found in the repository (`git grep` for keys/tokens/passwords;
  the SRTM download script prompts and does not store credentials). Logs contain job ids
  and states only, never coordinates (tested). Error bodies contain no stack traces except
  for B6.

## 6. Scientific validity risks

- The method is not empirically validated against accepted analog lists (documented, unchanged).
- Distances are relative to the candidate pool (MAD normalisation) — compare only within one analysis.
- MOLA and LOLA grids contain interpolated cells that cannot be identified from the
  elevation product alone (flagged on every result).
- SRTM void fill comes from non-SRTM sources (ASTER GDEM, GMTED2010, NED…); excluded above 5 %
  per candidate and tested in a sensitivity run.

## 7. Prioritised repair plan

1. **Backend lifecycle**: B1, B3, B6 (correctness) → B4, B5, B2, B7.
2. **Science**: S3 grid-compatibility check and S4 acceptance tests; then S1/S2 lunar pipeline
   from a verified LOLA product (LDEM_64, 64 px/deg ≈ 474 m, chosen because it is the
   LOLA grid closest to MEGDR's 463 m, so both bodies are compared at nearly the same scale).
3. **App**: F1/X1 configuration, F2 validation, F3/F4 resilience, F5 body-aware wording,
   Moon target in the analysis form, F6 map note.
4. **Docs, tests, build**: update methodology, dataset cards, API doc, validation report;
   rebuild APK.

Not planned: reverse geocoding (no source verified for this project; inventing names is
forbidden, and "not available" is the honest state); Copernicus/SLDEM2015 (excluded by the
project's NASA-only policy).

## Traceability

| Defect | Code change | Test(s) | Status |
|---|---|---|---|
| B1 | `api/paf_api/jobs.py` `JobStore.queued_ids`, `main.py` lifespan re-enqueues | `tests/api/test_api_hardening.py::test_queued_jobs_resume_after_restart` | Fixed, tested |
| B2 | `main.py` `/v1/ready` | `test_api_hardening.py::test_ready_endpoint` | Fixed, tested |
| B3 | `schemas.py` `allow_inf_nan=False` | `test_api_hardening.py::test_nan_and_infinite_values_rejected` | Fixed, tested |
| B4 | `main.py` `Idempotency-Key` + identical-active-job reuse, `jobs.py` `find_active` | `test_api_hardening.py::test_idempotent_submission` | Fixed, tested |
| B5 | `main.py` body-size middleware, per-client rate limit, queue cap | `test_api_hardening.py::test_body_size_limit`, `::test_rate_limit_and_queue_cap` | Fixed, tested |
| B6 | `main.py` catch-all handler | `test_api_hardening.py::test_unhandled_error_is_structured` | Fixed, tested |
| B7 | `jobs.py` `purge_older_than`, `PAF_JOB_RETENTION_DAYS` | `test_api_hardening.py::test_retention_purge` | Fixed, tested |
| S1/S2 | `core/paf_core/sources/lola_gdr.py`, registry entry, `search.analyze_target`, API `body: MOON` | `tests/core/test_lola_gdr.py`, `tests/core/test_real_lola.py`, `tests/api/test_api_hardening.py::test_moon_analysis_lifecycle` | Fixed, tested incl. real LDEM_64 + LDEM_16 cross-check |
| S3 | `search.py` spacing tolerance check | `tests/core/test_scientific_acceptance.py::test_incompatible_grid_rejected` | Fixed, tested |
| S4 | — | `tests/core/test_scientific_acceptance.py` | Fixed, tested |
| F1/X1 | `mobile/src/lib/api.ts` `VITE_PAF_API_BASE` + HTTPS rule; `capacitor.config.ts` release mode; `build.gradle` per-build-type cleartext + `tools:replace` in the manifest | `mobile/src/test/resilience.test.tsx` (address rule), merged release manifest = `false` | Fixed, tested (unit + merged-manifest check); not run on a device |
| F2 | `mobile/src/lib/validate.ts`, `useJob.ts` | `resilience.test.tsx` | Fixed, tested |
| F3 | `api.ts` bounded retry + idempotency key | `resilience.test.tsx` | Fixed, tested |
| F4 | `useJob.ts` stall detection | `resilience.test.tsx` | Fixed, tested |
| F5 | `labels.ts` `bodyName`/`bodySource`, Results, Compare, Earth, Mars, Moon pages | existing Mars-wording tests still pass; Moon wording checked in the live browser run (no dedicated unit test) | Fixed, verified in browser |
| F6 | `EarthMap.tsx` legend note | none (the map is mocked in unit tests) | Fixed, not tested |
| F7 (found in E2E run) | `App.tsx` reloads the dataset list on each page change; `MoonPage` shows a validated Moon result even with a stale list | live browser run only | Fixed, verified in browser |
| F8 (found in E2E run) | `labels.fmtVersion`: LOLA version printed "vV3.1" | `resilience.test.tsx` | Fixed |
| F9 (found on a real phone) | Debug APK defaulted to the emulator-only address `10.0.2.2`; error didn't say why. Errors now name the address and explain; Settings has Test connection; USB build defaults to `127.0.0.1` + `adb reverse` | `resilience.test.tsx` (2 tests); device run in validation.md | Fixed, verified on device |
| X2 (found in build) | Release build failed: Capacitor's generated plugin manifest forced `usesCleartextTraffic=true`; `tools:replace` added | `assembleRelease` succeeds, merged manifest `false` | Fixed |

## Final audit (2026-11-15)

All defects above are fixed. All except F5–F7 have automated tests; F5 and F7 were checked in
a live browser run against the real API, and F6 (a text note) is untested. See [validation.md](validation.md) for
results and for what remains unverified (native Android runtime, hosted TLS deployment,
interpolated-cell identification, Earth place names).
