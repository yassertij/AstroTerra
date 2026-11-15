# Dataset card — LOLA GDR LDEM_64 (Moon)

Verified 2026-11-15 from the files themselves and the volume's catalog. Nothing below is
assumed from memory.

| Field | Value | Verified from |
|---|---|---|
| Data set ID | `LRO-L-LOLA-4-GDR-V1.0` | `ldem_64.lbl`, `gdr_ds.cat` |
| Product | `LDEM_64`, `PRODUCT_VERSION_ID = "V3.1"`, `PRODUCT_CREATION_TIME = 2019-03-15`, data through mission phase LRO_ES_52 | label |
| PDS4 identity | LID `urn:nasa:pds:lro_lola_rdr:data_gridded:ldem_64` (same file) | `ldem_64.xml` |
| DOI | 10.17189/tnyt-7007 — PDS4 bundle `urn:nasa:pds:lro_lola_rdr` (resolves to the PDS bundle page) | `bundle_lola_rdr.xml`, doi.org |
| Mission / instrument | Lunar Reconnaissance Orbiter / Lunar Orbiter Laser Altimeter (LOLA) | label |
| Archive | NASA PDS Geosciences Node, <https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/> | directory listing |
| Format | PDS3 detached label + raw image, `LSB_INTEGER`, 16 bit, 11520 lines × 23040 samples (530,841,600 bytes) | label, file size |
| Geolocation | precision orbits based on gravity field GRGM 900C | label `DESCRIPTION` |
| Projection | `SIMPLE CYLINDRICAL`, global (90° S–90° N, 0–360° E), centre lat 0°, centre lon 180°, `LINE_PROJECTION_OFFSET = 5759.5`, `SAMPLE_PROJECTION_OFFSET = 11519.5` (zero-based per `dsmap.cat`); pixel registered | label, `dsmap.cat` |
| Coordinates | `MEAN EARTH/POLAR AXIS OF DE421`, planetocentric latitude, `POSITIVE_LONGITUDE_DIRECTION = "EAST"` | label |
| Body radius | sphere, `A = B = C = 1737.4 km` | label |
| Map scale | `MAP_RESOLUTION = 64 pix/deg`, `MAP_SCALE = 473.802 m/pix` | label |
| Units / scaling | `UNIT = METER`, `SCALING_FACTOR = 0.5`, `OFFSET = 1737400.` | label |
| Height | **HEIGHT = DN × 0.5** (metres above the 1737.4 km sphere). `PLANETARY_RADIUS = HEIGHT + OFFSET`. The reader never adds OFFSET. | label note |
| Missing data | no `MISSING_CONSTANT`; every cell has a value | label |
| Range | DN −18251 … 21546 → −9125.5 … 10773 m | label `MINIMUM`/`MAXIMUM` |
| Checksum | none published (not in the PDS3 or PDS4 label); file size checked against the label | labels |

## Known limitations (from the label)

- "At higher resolutions, the GMT 5.4.2 program 'surface' was used to compensate for
  incomplete coverage": some cells are interpolated. The LDAC count grids would identify
  them but are not loaded, so interpolated cells are not identified (flag
  `interpolated_cells_not_identified` on every record).
- "The gridfiles were produced in 45 degree latitude bands, and there may be edge artifacts
  at this boundary": windows within 0.5° of −45°, 0° or 45° are flagged `near_band_edge`.
- The height reference is a sphere, not an equipotential surface; absolute heights are never
  compared with Earth.

## Why LDEM_64

Its spacing (473.8 m) is closest to MOLA MEGDR 128 px/deg (≈ 463 m), so Mars and Moon
targets are both compared with Earth at nearly the same scale, and a 40 km patch is
≈ 84 × 84 pixels. LDEM_16 (≈ 1.9 km) is too coarse for 5 km windows; LDEM_128 is a single
2.1 GB file and the higher-resolution grids are tiled (multi-tile mosaicking is not
implemented).

## Cross-check

`ldem_16.img` (same data set, version V3.1, 16 px/deg) is downloaded separately into
`data/raw/lola_crosscheck/` and used only by `tests/core/test_real_lola.py`: a 4 × 4 block
mean of LDEM_64 must match LDEM_16 (median absolute difference < 30 m at six random
locations), and a one-pixel shift must be clearly worse. This independently checks
registration, byte order and scaling.

## Download

```bash
mkdir -p data/raw/lola_gdr
curl -f -o data/raw/lola_gdr/ldem_64.lbl https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.lbl
curl -f -C - -o data/raw/lola_gdr/ldem_64.img https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img
```

The server lists the product in `/v1/datasets` only after its label and file size pass
validation.
