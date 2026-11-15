"""API tests against a SYNTHETIC data directory (marked with a SYNTHETIC file)."""

import logging
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from paf_api.config import Settings
from paf_api.jobs import JobStore
from paf_api.main import create_app
from paf_core.errors import MetricError

from tests.core.megdr_fixture import RES, write_megdr
from tests.core.srtm_fixture import N, write_tile

TARGET = {"target": {"lat": -0.5, "lon_east": 90.5, "patch_km": 40}, "earth_tiles": ["N38W111"], "stride_km": 10}


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("apidata")
    rng = np.random.default_rng(3)
    (d / "raw" / "mola_megdr").mkdir(parents=True)
    write_megdr(d / "raw" / "mola_megdr", np.cumsum(rng.normal(0, 20, (RES, RES)), axis=0).astype(np.int16))
    write_tile(d / "raw" / "srtm", hgt=(1500 + np.cumsum(rng.normal(0, 3, (N, N)), axis=1)).astype(np.int16))
    (d / "SYNTHETIC").write_text("test fixture data")
    return d


def settings_for(data_dir, tmp_path):
    return Settings(data_dir=data_dir, db_path=tmp_path / "jobs.sqlite3")


def wait(client, jid, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/v1/jobs/{jid}").json()
        if j["status"] in ("succeeded", "failed", "cancelled"):
            return j
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_read_endpoints(data_dir, tmp_path):
    with TestClient(create_app(settings_for(data_dir, tmp_path))) as c:
        h = c.get("/v1/health").json()
        assert h["status"] == "ok" and h["synthetic_data"] is True
        s = c.get("/v1/sources").json()
        assert {x["data_set_id"] for x in s["approved"]} == {
            "MGS-M-MOLA-5-MEGDR-L3-V1.0", "LRO-L-LOLA-4-GDR-V1.0", "SRTMGL1.003", "SRTMGL1N.003"}
        assert "SLDEM2015" in s["excluded"]
        r = c.get("/v1/datasets")
        assert r.json()["earth_srtm"] == [{"tile": "N38W111", "num_file": True}]
        assert str(data_dir) not in r.text and str(data_dir).replace("\\", "\\\\") not in r.text


@pytest.mark.parametrize("lat, lon, status, tile", [
    (38.4, -110.8, "inside", "N38W111"), (60.0, 10.0, "inside", "N60E010"),
    (75.4, -89.8, "outside_coverage", None), (-56.5, -68.0, "outside_coverage", None),
])
def test_coverage_check(data_dir, tmp_path, lat, lon, status, tile):
    with TestClient(create_app(settings_for(data_dir, tmp_path), start_worker=False)) as c:
        j = c.post("/v1/coverage/check", json={"lat": lat, "lon": lon}).json()
        assert j["status"] == status and j["tile"] == tile
        assert j["tile_available_locally"] is (tile == "N38W111")


@pytest.mark.parametrize("body, where", [
    ({**TARGET, "target": {"lat": 89.0, "lon_east": 90.5}}, "lat"),
    ({**TARGET, "target": {"lat": -0.5, "lon_east": 360.0}}, "lon_east"),
    ({**TARGET, "earth_tiles": ["X38W111"]}, "earth_tiles"),
    ({**TARGET, "earth_tiles": ["N38W111", "N38W111"]}, "earth_tiles"),
    ({**TARGET, "earth_tiles": []}, "earth_tiles"),
    ({**TARGET, "weights": {"slope_median_deg": 1.0}}, "weights"),
    ({**TARGET, "extra": 1}, "extra"),
    ({"target": {"lat": "abc", "lon_east": 90}, "earth_tiles": ["N38W111"]}, "lat"),
])
def test_invalid_requests_return_structured_errors(data_dir, tmp_path, body, where):
    with TestClient(create_app(settings_for(data_dir, tmp_path), start_worker=False)) as c:
        r = c.post("/v1/analyses", json=body)
        assert r.status_code == 422
        e = r.json()["error"]
        assert e["code"] == "validation_error" and any(where in "/".join(map(str, d["loc"])) for d in e["details"])


def test_target_outside_local_megdr(data_dir, tmp_path):
    with TestClient(create_app(settings_for(data_dir, tmp_path), start_worker=False)) as c:
        r = c.post("/v1/analyses", json={**TARGET, "target": {"lat": -5.4, "lon_east": 137.8}})
        assert r.status_code == 422 and r.json()["error"]["code"] == "target_not_available"
        assert r.json()["error"]["details"][0]["product_id"] == "MEGT00N090HB.IMG"


def test_full_job_lifecycle_and_synthetic_label(data_dir, tmp_path, caplog):
    caplog.set_level(logging.INFO)
    with TestClient(create_app(settings_for(data_dir, tmp_path))) as c:
        r = c.post("/v1/analyses", json=TARGET)
        assert r.status_code == 202 and r.json()["status"] == "queued"
        jid = r.json()["id"]
        j = wait(c, jid)
        assert j["status"] == "succeeded" and j["progress"] == 1.0, j
        res = c.get(f"/v1/jobs/{jid}/result").json()
        assert res["is_synthetic"] is True and res["disclaimer"].startswith("SYNTHETIC DEMO DATA")
        assert res["coverage"]["tiles_examined"] == ["N38W111"]
        assert res["ranking"]["results"][0]["rank"] == 1
        assert any(x["id"] == jid for x in c.get("/v1/jobs").json())
    logs = caplog.text
    assert jid in logs and "90.5" not in logs and "-0.5" not in logs  # no coordinates in logs


def test_result_not_ready_and_cancel_queued(data_dir, tmp_path):
    with TestClient(create_app(settings_for(data_dir, tmp_path), start_worker=False)) as c:
        jid = c.post("/v1/analyses", json=TARGET).json()["id"]
        r = c.get(f"/v1/jobs/{jid}/result")
        assert r.status_code == 409 and r.json()["error"]["code"] == "result_not_ready"
        assert c.post(f"/v1/jobs/{jid}/cancel").json()["status"] == "cancelled"
        assert c.post(f"/v1/jobs/{jid}/cancel").json()["status"] == "cancelled"  # idempotent
        assert c.get("/v1/jobs/nope").status_code == 404
        assert c.post("/v1/jobs/nope/cancel").json()["error"]["code"] == "job_not_found"


def test_cancel_running_job(data_dir, tmp_path):
    started = threading.Event()

    def slow_runner(params, progress, should_cancel):
        started.set()
        for i in range(500):
            progress(i / 500, "working")
            if should_cancel():
                from paf_core.errors import JobCancelled
                raise JobCancelled("stop")
            time.sleep(0.01)
        return {"never": True}

    with TestClient(create_app(settings_for(data_dir, tmp_path), runner=slow_runner)) as c:
        jid = c.post("/v1/analyses", json=TARGET).json()["id"]
        assert started.wait(10)
        assert c.post(f"/v1/jobs/{jid}/cancel").status_code == 200
        assert wait(c, jid)["status"] == "cancelled"


def test_failures_are_reported_and_worker_survives(data_dir, tmp_path):
    calls = {"n": 0}

    def flaky(params, progress, should_cancel):
        calls["n"] += 1
        if calls["n"] == 1:
            raise MetricError("Only 2 eligible candidates")
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return {"ok": True}

    with TestClient(create_app(settings_for(data_dir, tmp_path), runner=flaky)) as c:
        # distinct requests (identical active requests are deduplicated by design)
        ids = [c.post("/v1/analyses", json={**TARGET, "stride_km": 10 + k}).json()["id"] for k in range(3)]
        a, b, ok = (wait(c, i) for i in ids)
        assert a["status"] == "failed" and a["error"]["code"] == "MetricError"
        assert b["status"] == "failed" and b["error"]["code"] == "internal_error" and "boom" not in b["error"]["message"]
        assert ok["status"] == "succeeded"


def test_interrupted_jobs_marked_failed_on_startup(data_dir, tmp_path):
    s = settings_for(data_dir, tmp_path)
    store = JobStore(s.db_path)
    jid = store.create("mars_earth_analysis", TARGET)
    store.update(jid, status="running")
    store.close()
    with TestClient(create_app(s, start_worker=False)) as c:
        j = c.get(f"/v1/jobs/{jid}").json()
        assert j["status"] == "failed" and j["error"]["code"] == "interrupted"
