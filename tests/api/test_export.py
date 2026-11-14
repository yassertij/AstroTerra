"""Exports: settings recorded, no coordinates/paths by default, rounded coordinates on opt-in."""

import csv
import io
import json
import re

import pytest
from fastapi.testclient import TestClient

from paf_api.main import create_app

from .test_api import TARGET, data_dir, settings_for, wait  # noqa: F401  (fixture re-export)


@pytest.fixture(scope="module")
def done(data_dir, tmp_path_factory):  # noqa: F811
    tmp = tmp_path_factory.mktemp("exp")
    with TestClient(create_app(settings_for(data_dir, tmp))) as c:
        jid = c.post("/v1/analyses", json=TARGET).json()["id"]
        assert wait(c, jid)["status"] == "succeeded"
        yield c, jid, data_dir


COORD_RE = re.compile(r'"(lat|lon|lon_east|center_lat|center_lon_east|lat_min|lat_max|lon_min|lon_max|rows|cols|aggregated_rows|aggregated_cols)"')


def test_json_export_default_has_no_coordinates_or_paths(done):
    c, jid, d = done
    r = c.get(f"/v1/jobs/{jid}/export?format=json")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    text = r.text
    assert not COORD_RE.search(text)
    assert str(d) not in text and str(d).replace("\\", "\\\\") not in text
    js = json.loads(text)
    assert js["export_info"]["coordinates_included"] is False
    assert all(re.fullmatch(r"N38W111#\d+", x["candidate_id"]) for x in js["ranking"]["results"])
    for key in ("weights", "normalization", "exclusion_rules", "sensitivity_method"):
        assert js["ranking"][key]
    assert js["target_record"]["doi"] == "10.17189/1519460"
    assert js["earth_records"]["N38W111"]["doi"] == "10.5067/MEASURES/SRTM/SRTMGL1.003"
    assert "distance" in js["metric_definitions"] and js["limitations"] and js["is_synthetic"] is True


def test_csv_export_default(done):
    c, jid, _ = done
    text = c.get(f"/v1/jobs/{jid}/export?format=csv").text
    meta = [l for l in text.splitlines() if l.startswith("#")]
    assert any(l.startswith("# disclaimer: SYNTHETIC DEMO DATA") for l in meta)
    assert any("citations" in l and "doi" in l.lower() for l in meta)
    rows = list(csv.DictReader(io.StringIO("\n".join(l for l in text.splitlines() if not l.startswith("#")))))
    assert rows and "lat_min" not in rows[0] and "_r" not in rows[0]["candidate"]
    assert rows[0]["rank"] == "1" and "contrib_relief_20km_m" in rows[0]
    assert not re.search(r"-?\d+\.\d{3,}\s*(N|S|E|W)\b", text)


def test_coordinates_opt_in_are_rounded(done):
    c, jid, _ = done
    js = c.get(f"/v1/jobs/{jid}/export?format=json&include_coordinates=true").json()
    assert js["export_info"]["coordinate_precision_deg"] == 0.01
    reg = js["ranking"]["results"][0]["region"]
    for k in ("lat_min", "lat_max", "lon_min", "lon_max"):
        assert round(reg[k], 2) == reg[k]
    assert "aggregated_rows" not in reg
    rows = list(csv.DictReader(io.StringIO("\n".join(
        l for l in c.get(f"/v1/jobs/{jid}/export?format=csv&include_coordinates=true").text.splitlines() if not l.startswith("#")))))
    assert "lat_min" in rows[0]


def test_export_errors(done):
    c, jid, _ = done
    assert c.get(f"/v1/jobs/{jid}/export?format=xml").status_code == 422
    assert c.get("/v1/jobs/nope/export").status_code == 404


def test_cors_allows_capacitor_and_dev_origins(done):
    c, _, _ = done
    for origin in ("capacitor://localhost", "http://localhost:5173"):
        r = c.options("/v1/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
        assert r.headers.get("access-control-allow-origin") == origin
    r = c.options("/v1/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
