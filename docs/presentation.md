# Presentation readiness — NASA Space Apps

Everything below is backed by a test or a recorded run on 2026-11-15 unless marked otherwise.
Full evidence: [validation.md](validation.md) · [release-checklist.md](release-checklist.md).

## How it works (30 seconds)

1. You pick a **target** on Mars (NASA PDS MOLA MEGDR, 463 m grid) or the Moon (NASA PDS LOLA
   LDEM_64, 474 m grid) and one or more **Earth tiles** (NASA LP DAAC SRTM GL1 v3, 30 m).
2. The server cuts a 40 km square around the target and slides 40 km windows across each
   Earth tile. Earth data is **block-averaged** to the target's grid (never upsampled).
3. For every patch it computes 7 **shape** statistics: median slope; local relief and
   detrended roughness on 5, 10 and 20 km windows. Absolute heights are never compared
   (Mars areoid, lunar sphere and Earth geoid are different references).
4. Each feature is scaled by its robust spread (1.4826 × MAD) across the Earth candidates;
   the score is a weighted Euclidean distance. **Lower = more similar; 0 = identical.** It
   is not a probability.
5. Candidates with too little valid data, more than 5 % non-SRTM void fill, missing
   features or an incompatible grid are **excluded with a reason**, never scored.
6. Every result records datasets, versions, DOIs, processing steps, settings, weights,
   sensitivity runs and limitations; exports carry the same.

## What is genuinely implemented and verified

- Real data on disk and validated against labels / archive checksums: MOLA tile
  `megt00n090hb` (MD5 = archive), LOLA `LDEM_64` (size = label; registration cross-checked
  against `LDEM_16`), SRTM `N38W111` + NUM.
- Full workflow in the web build against the real API: Mars (Gale crater) and Moon
  (Taurus-Littrow) targets vs N38W111, 40 candidates each; screen = API = JSON = CSV.
- Reproducibility: rerunning Gale gave a result identical to the recorded run.
- 167 backend tests and 54 app tests pass (counts in validation.md).

## Not verified / limitations (say these out loud)

- The app has been run end to end on **one** phone (Galaxy S24 Ultra, Android 16) over a
  USB cable: Mars analysis, results and CSV export. The Moon flow, permissions and offline
  behaviour have not been checked on the phone yet.
- Only **one Earth tile** (N38W111, Utah) is on disk, so "best analog" means best within
  that tile — both recorded runs say *no close analog* (best distances 8.1 and 8.8).
- The method is **not validated** against known analog sites; scores are relative to the
  candidate pool and not comparable across analyses.
- Interpolated MOLA/LOLA cells can't be identified (count products not loaded).
- No Earth place names (no verified geocoding source); no API authentication.

## Live demo (≈ 4 minutes)

Before (phone over USB, tested):
1. Phone: Developer options → USB debugging on; Samsung **Auto Blocker off**; plug in, tap Allow.
2. PC: start the API (README "Running"), then
   `adb install -r dist/AstroTerra-0.2.2-debug-usb.apk` and
   `adb reverse tcp:8765 tcp:8765` (repeat `adb reverse` after re-plugging the cable).
3. App → Settings → address `http://127.0.0.1:8765` → **Test connection** → "Connected".

Laptop-only alternative: start the API and web app; open `http://127.0.0.1:5173`.

1. **Overview** — counts of real data on the server (1 Mars tile, 1 Moon product, 1 Earth tile).
2. **Analysis** → Mars, Gale crater (5.4° S, 137.8° E), 40 km, tick N38W111 → Run.
   The server finishes in about 1–2 s once the SRTM tile has been extracted (job records,
   2026-11-15); the progress card jumps to 100 % almost at once.
3. **Mars** → ranking table → *Explain* the top candidate: which features drive the
   distance, the sensitivity range, void-fill share.
4. **Earth** → map: the candidate patches on the real tile footprint; note the basemap is
   imagery only.
5. **Moon** → show the LDEM_64 product card and run Taurus-Littrow (20.19° N, 30.77° E).
6. **Results → Provenance / Export** — DOIs, processing history; download the CSV.

## Backup plan

- **Backend or laptop network fails:** the two real results are saved as JSON in
  `data/processed/` (`m4_gale_vs_N38W111.json`, `moon_taurus_littrow_vs_N38W111.json`).
  Show them as *recorded runs from 2026-11-14/15*, not live computations.
- **Phone can't connect:** Settings → Test connection says why. Usually the cable was
  re-plugged (run `adb reverse tcp:8765 tcp:8765` again). Otherwise switch to the laptop browser.
- **Browser app fails:** run the analysis with `curl` (README "Workflow example") and show
  the JSON/CSV export.
- **Internet fails:** everything except the map basemap works offline on the laptop; the map
  still draws tiles and candidates without imagery and says the basemap is unavailable.

## Likely judge questions

**1. "Why compare slope and roughness instead of elevation?"**
Mars heights are relative to the areoid, lunar heights to a 1737.4 km sphere and Earth
heights to the EGM96 geoid. Absolute values are not comparable across bodies, so we only
compare shape statistics, which are relative within each patch. They are still scale-
dependent, which is why everything is compared at one common grid spacing.

**2. "Isn't 30 m SRTM unfairly sharper than 463 m MOLA?"**
Yes, so the Earth data is block-averaged to the target's grid before any metric is
computed; we never upsample the planetary data. Candidates whose achieved spacing differs
from the target by more than 5 % are excluded. The cost is that Earth detail below ~460 m
is averaged away, and we say so in every result.

**3. "How do you know the score means anything?"**
We don't claim it measures geological similarity. Tests prove the arithmetic (identical
terrain → 0, flat → 0, known slopes and steps), real-data checks prove the inputs are read
correctly, and a seeded weight-sensitivity analysis shows how stable each rank is. Validating
against expert-recognised analog sites (e.g. known Mars analog field areas) is the next
scientific step and has not been done.
