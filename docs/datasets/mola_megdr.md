# Dataset card — MOLA MEGDR (Mars)

| Field | Value | Verified from |
|---|---|---|
| Data set ID | `MGS-M-MOLA-5-MEGDR-L3-V1.0` | product label, `megdrds.cat` |
| DOI | 10.17189/1519460 | PDS Geosciences `dataserv/doi.htm` |
| Product version | `PRODUCT_VERSION_ID = "2.0"` (final), `PRODUCT_CREATION_TIME = 2003-03-21T01:00:00` | label; megdr.html |
| Volume | `MGSL_300X`, data set release 2003-04-19 | `voldesc.cat`, `megdrds.cat` |
| Mission / instrument | Mars Global Surveyor / Mars Orbiter Laser Altimeter (MOLA) | label |
| Archive | NASA PDS Geosciences Node, <https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/> | directory listing |
| Format | PDS3 detached label + raw image, `MSB_INTEGER`, 16 bit | label |
| Resolutions | 4, 16, 32, 64, 128 px/deg; 64 and 128 tiled in 44° × 90° tiles | megdr.html |
| Tile used | `megt00n090hb` — 0° to 44° S, 90° to 180° E, 5632 lines × 11520 samples | label |
| Projection | `SIMPLE CYLINDRICAL`, centre lat 0°, centre lon 180°, `LINE_PROJECTION_OFFSET = 0.5`, `SAMPLE_PROJECTION_OFFSET = 11520.5`; edge-registered | label |
| Coordinates | `PLANETOCENTRIC`, `BODY-FIXED ROTATING`, `POSITIVE_LONGITUDE_DIRECTION = "EAST"` (0–360), IAU2000 | label |
| Body radius | sphere, `A = B = C = 3396.0 km` | label |
| Map scale | `MAP_RESOLUTION = 128.0 px/deg`, `MAP_SCALE = 0.463 km/pixel` | label |
| Vertical reference | Areoid from Goddard Mars potential model GMM3 (mgm1025) to degree/order 50; topography = planetary radius − areoid radius | label `DESCRIPTION` |
| Units | metre (`UNIT = METER`) | label |
| Scale factor / offset | not present in the label (values used as stored) | label |
| Fill value | none declared (`MISSING_CONSTANT` absent) | label |
| Processing history | Median of MOLA observations per bin; bins without observations interpolated; first-order crossover adjustment; mapping-phase data Feb 1999 – Jun 2001 | label `DESCRIPTION` |
| Data quality | Near the equator ~55 % of bins contain at least one shot; gaps up to 12 km between profiles; dataset-wide range −8,208 to 21,249 m | label |
| Checksums | `.img` MD5 `1F2C70C407976DD22E79DFBB3469EBF1`; `.lbl` MD5 `3EA548315445CDEE09B54FCBBC722E14` (volume file `mgsl_300x_201204.md5`; both verified locally) | md5 file |
| Licence / terms | unknown (not stated on the pages read) | — |
| Citation | Smith, D.E., Zuber, Neumann, Guinness, and Slavney, 2003. MOLA Mission Experiment Gridded Data Record, MGS-M-MOLA-5-MEGDR-L3-V1.0, NASA Planetary Data System. doi:10.17189/1519460 | `megdrds.cat`, doi.htm |

Notes
- Since 2026-08-25 the Geosciences Node lists a PDS4 bundle ("MGS MOLA Derived Topography",
  DOI 10.17189/1z1b-kv84) as the maintained version; the PDS3 volume "remains available for
  the time being". PDS4 is not supported yet.
- Observation-count (`megc*`) tiles exist and would identify interpolated cells; not yet used.
- The MEGDR Software Interface Specification (`document/egdrsis.pdf`) has not been read.
