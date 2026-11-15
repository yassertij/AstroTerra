# Release checklist — 0.2.0 (2026-11-15)

Legend: ✅ verified here (test or recorded run) · ⚠️ implemented, not verified · ⛔ blocked or not done.

## Verified

| Item | Evidence |
|---|---|
| ✅ Mars (MOLA MEGDR v2.0) target ingestion, MD5 matches archive | `test_real_megdr.py` |
| ✅ Earth (SRTM GL1 v3 + NUM) ingestion, void-fill classification | `test_real_srtm.py` |
| ✅ Moon (LOLA LDEM_64 V3.1) ingestion; scaling and registration cross-checked against LDEM_16 | `test_real_lola.py` |
| ✅ Scientific acceptance cases (flat, plane, step, identical, missing data, incompatible grid) | `test_scientific_acceptance.py` |
| ✅ Full analysis lifecycle via API (submit → poll → result → export), Mars and Moon | API tests; real runs in [validation.md](validation.md) |
| ✅ Reproducibility (Gale rerun identical to the earlier record) | validation.md |
| ✅ Exports equal on-screen results (real Moon run, 40 rows, JSON + CSV) | live browser check |
| ✅ Restart recovery, cancellation, idempotency, rate/size/queue limits, structured errors | `test_api.py`, `test_api_hardening.py` |
| ✅ App shows only validated results; bounded retries; polling stops on stall | `resilience.test.tsx` |
| ✅ Moon offered only when a validated LOLA product exists | `resilience.test.tsx`, live run |
| ✅ Release Android manifest: cleartext disabled; app origin https | merged manifest, synced `capacitor.config.json` |
| ✅ Debug APK builds | `dist/PlanetaryAnalogFinder-0.2.0-debug.apk` |

## Not verified

| Item | Why |
|---|---|
| ⚠️ App installed and run on Android (emulator or device): navigation, analysis, export download in the WebView, permission prompts, restart/offline | No emulator or device available on this machine |
| ⚠️ Release APK signing and store packaging | Needs the owner's keystore; `app-release-unsigned.apk` only |
| ⚠️ Hosted HTTPS deployment, CORS for release origins | Hosting not chosen; documented in [api.md](api.md) |
| ⚠️ Rate limiting behind a reverse proxy | All clients may share the proxy address; configure limits at the proxy |
| ⚠️ Accessibility on devices (screen reader, colour-vision simulation) | Not tested on devices |

## Not done (disclosed limitations)

| Item | Note |
|---|---|
| ⛔ Empirical validation against known analog sites | No reference set; the score is not a probability |
| ⛔ Identification of interpolated MOLA/LOLA cells | Count products (MEGC, LDAC) not loaded; flagged on every result |
| ⛔ Earth country/region names | No verified geocoding source; shown as "not available" |
| ⛔ Multi-tile mosaics (target or Earth), global Earth search | One MEGDR tile / LDEM_64 and listed SRTM tiles only |
| ⛔ API authentication | Run only on a trusted network or behind an authenticating proxy |
| ⛔ iOS | Needs macOS |

## Before a public release

1. Run the APK on at least one emulator and one device; record results in validation.md.
2. Deploy the API behind TLS; build with `VITE_PAF_API_BASE=https://…` and `PAF_RELEASE=1`.
3. Choose the final `appId`, sign the release APK, set `versionCode`/`versionName`.
4. Decide on authentication for the API.
