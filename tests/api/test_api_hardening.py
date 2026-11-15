"""API lifecycle, safety limits and the Moon pipeline, on SYNTHETIC data (SYNTHETIC marker present)."""

import json
import sqlite3

import numpy as np
import pytest
from fastapi.testclient import TestClient

from paf_api.config import Settings
from paf_api.jobs import JobStore
from paf_api.main import create_app

from tests.api.test_api import TARGET, wait
from tests.core.lola_fixture import RES as LRES, write_lola
from tests.core.megdr_fixture import RES, write_megdr
from tests.core.srtm_fixture import N, write_tile

MOON = {"target": {"body": "MOON", "lat": 0.0, "lon_east": 11.0, "patch_km": 40}, "earth_tiles": ["N38W111"],
        "stride_km": 10}


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("hardening")
    rng = np.random.default_rng(11)
    (d / "raw" / "mola_megdr").mkdir(parents=True)
    write_megdr(d / "raw" / "mola_megdr", np.cumsum(rng.normal(0, 20, (RES, RES)), axis=0).astype(np.int16))
    write_lola(d / "raw" / "lola_gdr", np.cumsum(rng.normal(0, 40, (2 * LRES, 2 * LRES)), axis=1).astype(np.int16))
    write_tile(d / "raw" / "srtm", hgt=(1500 + np.cumsum(rng.normal(0, 3, (N, N)), axis=1)).astype(np.int16))
    (d / "SYNTHETIC").write_text("test fixture data")
    return d


def settings(data_dir, tmp_path, **kw):
    return Settings(data_dir=data_dir, db_path=tmp_path / "jobs.sqlite3", **kw)


def test_ready_endpoint(data_dir, tmp_path):
    with TestClient(create_app(settings(data_dir, tmp_path))) as c:
        r = c.get("/v1/ready")
        assert r.status_code == 200 and r.json()["ready"] is True
        ch = r.json()["checks"]
        assert ch["database"] and ch["worker"] and ch["mars_target_products"] == 1 and ch["moon_target_products"] == 1
    empty = tmp_path / "empty"
    empty.mkdir()
    with TestClient(create_app(settings(empty, tmp_path))) as c:
        r = c.get("/v1/ready")
        assert r.status_code == 503 and r.json()["ready"] is False and len(r.json()["problems"]) == 2


@pytest.mark.parametrize("raw", [
    '{"target": {"lat": NaN, "lon_east": 90.5}, "earth_tiles": ["N38W111"]}',
    '{"target": {"lat": -0.5, "lon_east": 90.5}, "earth_tiles": ["N38W111"], "stride_km": Infinity}',
    '{"target": {"lat": -0.5, "lon_east": 90.5}, "earth_tiles": ["N38W111"], "weights": '
    '{"slope_median_deg": NaN, "relief_5km_m": 1, "relief_10km_m": 1, "relief_20km_m": 1, '
    '"roughness_5km_m": 1, "roughness_10km_m": 1, "roughness_20km_m": 1}}',
])
def test_nan_and_infinite_values_rejected(data_dir, tmp_path, raw):
    with TestClient(create_app(settings(data_dir, tmp_path), start_worker=False)) as c:
        r = c.post("/v1/analyses", content=raw, headers={"Content-Type": "application/json"})
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_idempotent_submission(data_dir, tmp_path):
    with TestClient(create_app(settings(data_dir, tmp_path), start_worker=False)) as c:
        h = {"Idempotency-Key": "abc12345-key"}
        a = c.post("/v1/analyses", json=TARGET, headers=h)
        b = c.post("/v1/analyses", json=TARGET, headers=h)
        assert a.status_code == 202 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
        conflict = c.post("/v1/analyses", json={**TARGET, "stride_km": 12}, headers=h)
        assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "idempotency_conflict"
        # Without a key, an identical active job is reused rather than queued twice.
        d = c.post("/v1/analyses", json=TARGET)
        assert d.status_code == 200 and d.json()["id"] == a.json()["id"]
        bad = c.post("/v1/analyses", json=TARGET, headers={"Idempotency-Key": "x"})
        assert bad.status_code == 422
        assert len(c.get("/v1/jobs").json()) == 1


def test_body_size_limit(data_dir, tmp_path):
    with TestClient(create_app(settings(data_dir, tmp_path, max_body_bytes=200), start_worker=False)) as c:
        r = c.post("/v1/analyses", content=b"{" + b" " * 500 + b"}", headers={"Content-Type": "application/json"})
        assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_rate_limit_and_queue_cap(data_dir, tmp_path):
    with TestClient(create_app(settings(data_dir, tmp_path, submit_rate_per_minute=2), start_worker=False)) as c:
        codes = [c.post("/v1/analyses", json={**TARGET, "stride_km": 10 + k}).status_code for k in range(3)]
        assert codes == [202, 202, 429]
    with TestClient(create_app(settings(data_dir, tmp_path / "q", max_active_jobs=1), start_worker=False)) as c:
        assert c.post("/v1/analyses", json=TARGET).status_code == 202
        r = c.post("/v1/analyses", json={**TARGET, "stride_km": 11})
        assert r.status_code == 503 and r.json()["error"]["code"] == "server_busy"


def test_unhandled_error_is_structured(data_dir, tmp_path):
    app = create_app(settings(data_dir, tmp_path), start_worker=False)
    with TestClient(app, raise_server_exceptions=False) as c:
        def broken(_):
            raise RuntimeError("secret internal detail C:\\path")
        app.state.store.get = broken
        r = c.get("/v1/jobs/abc")
        assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
        assert "secret" not in r.text and "Traceback" not in r.text


def test_queued_jobs_resume_after_restart(data_dir, tmp_path):
    s = settings(data_dir, tmp_path)
    store = JobStore(s.db_path)
    jid = store.create("mars_earth_analysis", TARGET)
    store.close()
    with TestClient(create_app(s, runner=lambda p, prog, cancel: {"ok": True})) as c:
        assert wait(c, jid)["status"] == "succeeded"


def test_retention_purge(tmp_path):
    store = JobStore(tmp_path / "j.sqlite3")
    old, new, running = (store.create("k", {"n": i}) for i in range(3))
    store.update(old, status="succeeded", result="{}")
    store.update(new, status="failed")
    store.update(running, status="running")
    db = sqlite3.connect(tmp_path / "j.sqlite3")
    db.execute("UPDATE jobs SET updated = '2000-01-01T00:00:00+00:00' WHERE id IN (?, ?)", (old, running))
    db.commit()
    db.close()
    assert store.purge_older_than(30) == 1
    assert store.get(old) is None and store.get(new) and store.get(running)  # running jobs are never purged


def test_moon_analysis_lifecycle(data_dir, tmp_path):
    with TestClient(create_app(settings(data_dir, tmp_path))) as c:
        ds = c.get("/v1/datasets").json()
        assert ds["moon_lola"][0]["product_id"] == "LDEM_64" and ds["moon_lola"][0]["spacing_m"] == pytest.approx(473.8, abs=0.1)
        r = c.post("/v1/analyses", json=MOON)
        assert r.status_code == 202, r.text
        j = wait(c, r.json()["id"], timeout=300)
        assert j["status"] == "succeeded", j
        res = c.get(f"/v1/jobs/{j['id']}/result").json()
        assert res["target"]["body"] == "MOON" and res["is_synthetic"] is True
        assert res["target_record"]["data_set_id"] == "LRO-L-LOLA-4-GDR-V1.0"
        assert "OFFSET" in res["target_record"]["vertical_reference"]
        assert any("1737.4 km sphere" in x for x in res["limitations"])
        sp = res["settings"]["analysis_spacing_m"]
        assert sp == pytest.approx(473.8, abs=0.5)
        ranked = [x for x in res["ranking"]["results"] if not x["excluded"]]
        assert ranked and all(abs(x["analysis_spacing_m"] - sp) / sp <= 0.05 for x in ranked)
        # export agrees with the result
        exp = json.loads(c.get(f"/v1/jobs/{j['id']}/export?format=json&include_coordinates=true").text)
        assert [x["distance"] for x in exp["ranking"]["results"]] == [x["distance"] for x in res["ranking"]["results"]]


def test_moon_target_outside_product(data_dir, tmp_path):
    with TestClient(create_app(settings(data_dir, tmp_path), start_worker=False)) as c:
        r = c.post("/v1/analyses", json={**MOON, "target": {**MOON["target"], "lat": 30.0}})
        assert r.status_code == 422 and r.json()["error"]["code"] == "target_not_available"
