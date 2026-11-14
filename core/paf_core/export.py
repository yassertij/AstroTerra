"""CSV and JSON exports of an analysis result.

Privacy default: every latitude/longitude value AND every pixel offset (which would let
a reader recover the location) is removed; candidates are relabelled ``<tile>#<n>``.
Tile names are kept. With ``include_coordinates=True`` coordinates are kept but rounded
to 0.01 degree (about 1.1 km on Earth, 0.6 km on Mars) and pixel offsets stay removed.
Exports never contain local file paths, credentials, photos or device location.
"""

from __future__ import annotations

import copy
import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from . import __version__

COORD_KEYS = {"lat", "lon", "lon_east", "center_lat", "center_lon_east", "lat_min", "lat_max", "lon_min", "lon_max"}
OFFSET_KEYS = {"rows", "cols", "aggregated_rows", "aggregated_cols"}
COORD_PRECISION_DEG = 0.01

METRIC_DEFINITIONS = {
    "slope_median_deg": "Median slope (degrees) from central differences on metric spacing; edges/gaps excluded.",
    "relief_{w}km_m": "Median over non-overlapping w-km windows of max(z) - min(z) (metres).",
    "roughness_{w}km_m": "Median over w-km windows of the std. dev. of residuals from a least-squares plane (metres).",
    "distance": "Weighted Euclidean distance of features normalised by 1.4826*MAD over eligible candidates. "
                "Lower = more similar; 0 = identical; not a probability.",
    "contribution": "Share of a candidate's squared distance due to each feature (sums to 1).",
    "valid_fraction": "Fraction of analysis-grid pixels with valid data.",
    "fill_fraction": "Mean fraction of each pixel's area from non-SRTM void-fill sources (SRTMGL1N codes).",
}


def _scrub(obj: Any, include: bool) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in OFFSET_KEYS:
                continue
            if k in COORD_KEYS:
                if include and isinstance(v, (int, float)):
                    out[k] = round(round(v / COORD_PRECISION_DEG) * COORD_PRECISION_DEG, 2)
                elif include and isinstance(v, list):
                    out[k] = [round(round(x / COORD_PRECISION_DEG) * COORD_PRECISION_DEG, 2) for x in v]
                continue
            out[k] = _scrub(v, include)
        return out
    if isinstance(obj, list):
        return [_scrub(v, include) for v in obj]
    return obj


def prepare(result: dict, include_coordinates: bool = False) -> dict:
    data = copy.deepcopy(result)
    if not include_coordinates:
        counters: dict[str, int] = {}
        for r in data.get("ranking", {}).get("results", []):
            tile = r.get("tile", "candidate")
            counters[tile] = counters.get(tile, 0) + 1
            r["candidate_id"] = f"{tile}#{counters[tile]}"
    data = _scrub(data, include_coordinates)
    data["export_info"] = {
        "software_version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "coordinates_included": include_coordinates,
        "coordinate_precision_deg": COORD_PRECISION_DEG if include_coordinates else None,
        "privacy_note": "Coordinates and pixel offsets removed." if not include_coordinates
        else "Coordinates rounded to 0.01 degree; pixel offsets removed.",
    }
    data["metric_definitions"] = METRIC_DEFINITIONS
    return data


def to_json(result: dict, include_coordinates: bool = False) -> str:
    return json.dumps(prepare(result, include_coordinates), indent=1, ensure_ascii=False)


def to_csv(result: dict, include_coordinates: bool = False) -> str:
    d = prepare(result, include_coordinates)
    rk = d["ranking"]
    feats = rk["features_used"]
    buf = io.StringIO()
    meta = [
        ("disclaimer", d["disclaimer"]),
        ("is_synthetic", d["is_synthetic"]),
        ("software_version", d["software_version"]),
        ("exported_at", d["export_info"]["exported_at"]),
        ("coordinates_included", include_coordinates),
        ("target_dataset", f"{d['target_record']['data_set_id']} v{d['target_record']['product_version']} "
                           f"({d['target_record']['product_id']}) doi:{d['target_record']['doi']}"),
        ("target_vertical_reference", d["target_record"]["vertical_reference"]),
        ("earth_datasets", "; ".join(f"{k}: {v['data_set_id']} doi:{v['doi']}" for k, v in d["earth_records"].items())),
        ("citations", " | ".join({d["target_record"]["citation"], *(v["citation"] for v in d["earth_records"].values())})),
        ("settings", json.dumps(d["settings"])),
        ("weights", json.dumps(rk["weights"])),
        ("normalization", json.dumps(rk["normalization"])),
        ("exclusion_rules", json.dumps(rk["exclusion_rules"])),
        ("sensitivity_method", json.dumps(rk["sensitivity_method"])),
        ("coverage", json.dumps({k: v for k, v in d["coverage"].items()})),
        ("quality_flags_target", json.dumps(d["target_record"]["quality_flags"])),
        ("ranking_flags", json.dumps(rk["flags"])),
        ("limitations", " | ".join(d["limitations"])),
        ("score_meaning", rk["score_meaning"]),
    ]
    for k, v in meta:
        buf.write(f"# {k}: {str(v).replace(chr(10), ' ')}\n")
    cols = ["rank", "candidate", "tile", "distance", "excluded", "exclusion_reasons", "valid_fraction",
            "fill_fraction", "native_spacing_m", "analysis_spacing_m",
            "sens_rank_median", "sens_rank_p05", "sens_rank_p95", "sens_top1_fraction", "fill_excluded_rank"]
    cols += [f"diff_{f}" for f in feats] + [f"contrib_{f}" for f in feats]
    if include_coordinates:
        cols += ["lat_min", "lat_max", "lon_min", "lon_max"]
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    for r in rk["results"]:
        s = r.get("sensitivity", {})
        row = {
            "rank": r["rank"], "candidate": r["candidate_id"], "tile": r["tile"], "distance": r["distance"],
            "excluded": r["excluded"], "exclusion_reasons": "; ".join(r["exclusion_reasons"]),
            "valid_fraction": r["valid_fraction"], "fill_fraction": r["fill_fraction"],
            "native_spacing_m": r["native_spacing_m"], "analysis_spacing_m": r["analysis_spacing_m"],
            "sens_rank_median": s.get("weight_perturbation_rank_median"), "sens_rank_p05": s.get("rank_p05"),
            "sens_rank_p95": s.get("rank_p95"), "sens_top1_fraction": s.get("top1_fraction"),
            "fill_excluded_rank": s.get("fill_excluded_rank"),
        }
        row.update({f"diff_{f}": r["feature_differences"].get(f) for f in feats})
        row.update({f"contrib_{f}": r["contributions"].get(f) for f in feats})
        if include_coordinates:
            row.update({k: r["region"].get(k) for k in ("lat_min", "lat_max", "lon_min", "lon_max")})
        w.writerow(row)
    return buf.getvalue()
