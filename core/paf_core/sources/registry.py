"""NASA-only allow-list of datasets.

Only entries here may be loaded. Every value below was checked against the official
archive (MOLA, SRTM: 2026-11-13; LOLA: 2026-11-15); the ``verified_from`` field says
where.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import UnapprovedSourceError


@dataclass(frozen=True)
class ApprovedSource:
    key: str
    data_set_id: str
    final_product_version: str
    doi: str
    body: str
    mission: str
    instrument: str
    archive: str
    access_url: str
    vertical_reference: str
    citation: str
    verified_from: tuple[str, ...]
    notes: str = ""


MOLA_MEGDR = ApprovedSource(
    key="mola_megdr",
    data_set_id="MGS-M-MOLA-5-MEGDR-L3-V1.0",
    final_product_version="2.0",
    doi="10.17189/1519460",
    body="MARS",
    mission="Mars Global Surveyor",
    instrument="Mars Orbiter Laser Altimeter (MOLA)",
    archive="NASA PDS Geosciences Node (PDS3 volume MGSL_300X)",
    access_url="https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/",
    vertical_reference=(
        "Areoid: Goddard Mars potential model GMM3 (mgm1025) evaluated to degree and "
        "order 50. Topography = planetary radius minus areoid radius (per product label)."
    ),
    citation=(
        # Author list as given in megdrds.cat CITATION_DESC; title as listed on doi.htm.
        "Smith, D.E., Zuber, Neumann, Guinness, and Slavney, 2003. "
        "MOLA Mission Experiment Gridded Data Record, "
        "MGS-M-MOLA-5-MEGDR-L3-V1.0, NASA Planetary Data System. doi:10.17189/1519460"
    ),
    verified_from=(
        "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
        "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg128/megt00n090hb.lbl",
        "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/catalog/megdrds.cat",
        "https://pds-geosciences.wustl.edu/dataserv/doi.htm",
    ),
    notes=(
        "Since 2026-08-25 the Geosciences Node lists a PDS4 bundle (DOI 10.17189/1z1b-kv84) "
        "as the maintained version; the PDS3 volume 'remains available for the time being'. "
        "PDS4 support is not implemented."
    ),
)

_SRTM_GUIDE = "https://lpdaac.usgs.gov/documents/179/SRTM_User_Guide_V3.pdf"

SRTM_GL1 = ApprovedSource(
    key="srtm_gl1",
    data_set_id="SRTMGL1.003",
    final_product_version="003",
    doi="10.5067/MEASURES/SRTM/SRTMGL1.003",
    body="EARTH",
    mission="Shuttle Radar Topography Mission (SRTM)",
    instrument="SRTM C-band interferometric radar",
    archive="NASA LP DAAC (NASA EOSDIS), collection SRTMGL1_003 / C2763266360-LPCLOUD",
    access_url="https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/SRTMGL1.003/",
    vertical_reference="WGS84/EGM96 geoid (SRTM User Guide V3, sec. 2.1.4)",
    citation=(
        "NASA JPL. (2013). NASA Shuttle Radar Topography Mission Global 1 arc second "
        "[Data set]. NASA Land Processes Distributed Active Archive Center. "
        "https://doi.org/10.5067/MEASURES/SRTM/SRTMGL1.003"
    ),
    verified_from=(
        "https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1-003",
        "https://cmr.earthdata.nasa.gov/search/collections.json?short_name=SRTMGL1&version=003",
        _SRTM_GUIDE,
    ),
    notes="Voids filled with ASTER GDEM2, GMTED2010 or NED; per-pixel source in SRTMGL1N.",
)

SRTM_GL1N = ApprovedSource(
    key="srtm_gl1n",
    data_set_id="SRTMGL1N.003",
    final_product_version="003",
    doi="10.5067/MEASURES/SRTM/SRTMGL1N.003",
    body="EARTH",
    mission=SRTM_GL1.mission,
    instrument=SRTM_GL1.instrument,
    archive="NASA LP DAAC (NASA EOSDIS), collection SRTMGL1N_003 / C2763266368-LPCLOUD",
    access_url="https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/SRTMGL1N.003/",
    vertical_reference="n/a (per-pixel source codes, not elevation)",
    citation=(
        "NASA JPL. (2013). NASA Shuttle Radar Topography Mission Global 1 arc second number "
        "[Data set]. NASA Land Processes Distributed Active Archive Center. "
        "https://doi.org/10.5067/MEASURES/SRTM/SRTMGL1N.003"
    ),
    verified_from=("https://www.earthdata.nasa.gov/data/catalog/lpcloud-srtmgl1n-003", _SRTM_GUIDE),
)

_LOLA_VOL = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx"

LOLA_GDR = ApprovedSource(
    key="lola_gdr",
    data_set_id="LRO-L-LOLA-4-GDR-V1.0",
    # Verified for LDEM_64 only (label PRODUCT_VERSION_ID). Other LDEM files are not approved yet.
    final_product_version="V3.1",
    # DOI of the PDS4 bundle urn:nasa:pds:lro_lola_rdr, which contains this same file
    # (ldem_64.xml, LID urn:nasa:pds:lro_lola_rdr:data_gridded:ldem_64).
    doi="10.17189/tnyt-7007",
    body="MOON",
    mission="Lunar Reconnaissance Orbiter (LRO)",
    instrument="Lunar Orbiter Laser Altimeter (LOLA)",
    archive="NASA PDS Geosciences Node (PDS3 volume LROLOL_1XXX / PDS4 bundle lro_lola_rdr)",
    access_url=f"{_LOLA_VOL}/data/lola_gdr/cylindrical/img/",
    vertical_reference=(
        "Height above a sphere of radius 1737.4 km (label OFFSET = 1737400 m, the reference "
        "radius). HEIGHT = DN x SCALING_FACTOR (0.5 m); the OFFSET is NOT added. Not an "
        "equipotential (geoid) surface."
    ),
    citation=(
        # Bundle Citation_Information (bundle_lola_rdr.xml) and gdr_ds.cat CITATION_DESC.
        "Smith, D.E. and Neumann, G.A., 2023. Lunar Reconnaissance Orbiter LOLA Processed (RDR) "
        "Data Products, NASA Planetary Data System, doi:10.17189/tnyt-7007. Product LDEM_64 "
        "(LRO-L-LOLA-4-GDR-V1.0, version V3.1); data set citation: Neumann, G.A., LRO-L-LOLA-4-GDR-V1.0, "
        "NASA Planetary Data System, 2010."
    ),
    verified_from=(
        f"{_LOLA_VOL}/data/lola_gdr/cylindrical/img/ldem_64.lbl",
        f"{_LOLA_VOL}/data/lola_gdr/cylindrical/img/ldem_64.xml",
        f"{_LOLA_VOL}/catalog/dsmap.cat",
        f"{_LOLA_VOL}/catalog/gdr_ds.cat",
        f"{_LOLA_VOL}/bundle_lola_rdr.xml",
    ),
    notes=(
        "No checksum is published for ldem_64.img (none in its PDS3 or PDS4 label); the file "
        "size is checked against RECORD_BYTES x FILE_RECORDS. Gridded with GMT 'surface' to "
        "compensate for incomplete coverage (interpolated cells not identifiable); produced in "
        "45-degree latitude bands with possible edge artifacts (label DESCRIPTION)."
    ),
)

# Explicitly excluded by project policy (non-NASA or mixed provenance).
EXCLUDED = {
    "SLDEM2015": "Combines LOLA with JAXA SELENE Terrain Camera data; excluded by policy.",
    "COPERNICUS": "Copernicus DEM (ESA / Airbus); excluded by policy.",
}

_BY_DATA_SET_ID = {s.data_set_id: s for s in (MOLA_MEGDR, SRTM_GL1, SRTM_GL1N, LOLA_GDR)}


def require_approved(data_set_id: str | None) -> ApprovedSource:
    """Return the approved source for ``data_set_id`` or raise with an actionable message."""
    if not data_set_id:
        raise UnapprovedSourceError(
            "Label has no DATA_SET_ID; provenance cannot be traced to a NASA dataset. "
            "Use the original PDS label shipped with the product."
        )
    norm = data_set_id.strip().upper()
    for marker, reason in EXCLUDED.items():
        if marker in norm:
            raise UnapprovedSourceError(f"{data_set_id}: {reason}")
    src = _BY_DATA_SET_ID.get(norm)
    if src is None:
        approved = ", ".join(sorted(_BY_DATA_SET_ID))
        raise UnapprovedSourceError(
            f"{data_set_id!r} is not on the NASA-only allow-list (approved: {approved})."
        )
    return src
