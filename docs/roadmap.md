# Roadmap

## Done (MVP milestones 1–7)

Audit → MOLA slice → SRTM slice → ranking + sensitivity → API with jobs → mobile app with
photo and exports → documentation and validation report.

## Done (0.2.0, 2026-11-15)

Audit and repair ([audit.md](audit.md)); API hardening (readiness, idempotency, limits,
restart recovery, retention); LOLA LDEM_64 Moon pipeline with real-data cross-check; app
result validation, retries, stall handling, HTTPS-only release configuration.

## Next, in priority order

0. **Device/emulator E2E**: install the debug APK on an emulator or phone and run the
   critical flows (analysis, results, export, permissions, restart, offline).
1. **Native builds**: `npx cap add android` / `ios`, permission usage strings, native photo
   picker and file sharing for exports; emulator/simulator E2E tests for photo import and
   permissions (needs Android Studio; iOS needs macOS).
2. **MOLA observation counts** (`megc*` tiles): measure and optionally exclude interpolated cells.
3. **More Earth tiles**: multi-tile scan with resumable downloads, disk cache and a coverage map
   of examined tiles; fixed reference scale so distances compare across analyses.
4. **Hillshade previews** of target and candidate with the same vertical exaggeration.
5. **Accessibility review**: colour-vision simulation, screen-reader testing on devices.
6. **Hosting decision** (to choose), authentication and TLS for a non-local backend.

## Later (desirable)

PDS4 MEGDR; PDF report; analysis history with
configuration ids; Plotly charts; offline mode; student mode with glossary; sensitivity
dashboard; French/English interface; shareable configuration links without personal data;
non-void-filled SRTM control once verified.

## Out of scope

Global coverage beyond SRTM's 60° N–56° S; climate, vegetation or mineral analysis;
peer-review-level validation.
