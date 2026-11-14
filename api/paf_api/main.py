"""FastAPI application. Run:  uvicorn paf_api.main:create_app --factory  (see README)."""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from paf_core import DISCLAIMER, __version__ as core_version
from paf_core.errors import PafError
from paf_core.search import analyze_mars_target
from paf_core.sources import mola_megdr, srtm_gl1
from paf_core.sources.registry import EXCLUDED, MOLA_MEGDR, SRTM_GL1, SRTM_GL1N

from . import API_VERSION
from .config import Settings
from .jobs import JobStore, Worker
from .schemas import AnalysisRequest, CoverageCheckRequest, CoverageCheckResponse, JobView

log = logging.getLogger("paf_api")
P = f"/{API_VERSION}"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: object = None):
        self.status, self.code, self.message, self.details = status, code, message, details


class TargetNotAvailable(PafError):
    def __init__(self, message: str, extents: list):
        super().__init__(message)
        self.extents = extents


def _err(status: int, code: str, message: str, details: object = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})


def _megdr_tiles(settings: Settings) -> list[mola_megdr.MegdrProduct]:
    out = []
    for lbl in sorted(settings.megdr_dir.glob("*.lbl")) if settings.megdr_dir.exists() else []:
        try:
            out.append(mola_megdr.open_megdr(lbl))
        except PafError as exc:
            log.warning("MEGDR label %s rejected: %s", lbl.name, type(exc).__name__)
    return out


def _megdr_for(settings: Settings, lat: float, lon: float, patch_km: float) -> Path:
    tiles = _megdr_tiles(settings)
    for p in tiles:
        a, b, c, d = mola_megdr.window_from_center_km(p, lat, lon, patch_km)
        g = p.grid
        if g.lat_bottom <= a and b <= g.lat_top and g.lon_west <= c and d <= g.lon_east:
            return p.label_path
    extents = [{"product_id": p.record.product_id, "lat": [p.grid.lat_bottom, p.grid.lat_top],
                "lon_east": [p.grid.lon_west, p.grid.lon_east]} for p in tiles]
    raise TargetNotAvailable(
        "No local MOLA MEGDR tile fully contains the requested target patch. "
        "Choose a target inside an available tile or download the covering tile.", extents)


def make_runner(settings: Settings):
    def run(params: dict, progress, should_cancel) -> dict:
        req = AnalysisRequest.model_validate(params)
        t = req.target
        label = _megdr_for(settings, t.lat, t.lon_east, t.patch_km)
        res = analyze_mars_target(
            label, t.lat, t.lon_east, req.earth_tiles, settings.srtm_dir, settings.work_dir,
            patch_km=t.patch_km, stride_km=req.stride_km, weights=req.weights,
            progress=progress, should_cancel=should_cancel,
        )
        if settings.is_synthetic:
            res.is_synthetic = True
            res.disclaimer = "SYNTHETIC DEMO DATA - not a real finding. " + res.disclaimer
        return json.loads(res.model_dump_json())
    return run


def _view(job: dict) -> JobView:
    return JobView(
        id=job["id"], kind=job["kind"], status=job["status"], progress=job["progress"], message=job["message"],
        error=json.loads(job["error"]) if job["error"] else None, created=job["created"], updated=job["updated"],
        links={"self": f"{P}/jobs/{job['id']}", "result": f"{P}/jobs/{job['id']}/result",
               "cancel": f"{P}/jobs/{job['id']}/cancel"},
    )


def create_app(settings: Settings | None = None, start_worker: bool = True, runner=None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = JobStore(settings.db_path)
    worker = Worker(store, runner or make_runner(settings))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        n = store.mark_interrupted()
        if n:
            log.warning("%d interrupted job(s) marked failed", n)
        if start_worker:
            worker.start()
        yield
        if start_worker:
            worker.stop()
        store.close()

    app = FastAPI(title="Planetary Analog Finder API", version=core_version, lifespan=lifespan,
                  description=DISCLAIMER)
    app.state.settings, app.state.store, app.state.worker = settings, store, worker

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _err(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(TargetNotAvailable)
    async def _target(_: Request, exc: TargetNotAvailable):
        return _err(422, "target_not_available", str(exc), exc.extents)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return _err(422, "validation_error", "The request is invalid; see details.", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _err(exc.status_code, "http_error", str(exc.detail))

    @app.get(f"{P}/health")
    def health():
        return {"status": "ok", "api_version": API_VERSION, "core_version": core_version,
                "synthetic_data": settings.is_synthetic, "disclaimer": DISCLAIMER}

    @app.get(f"{P}/sources")
    def sources():
        return {"approved": [asdict(s) for s in (MOLA_MEGDR, SRTM_GL1, SRTM_GL1N)], "excluded": EXCLUDED}

    @app.get(f"{P}/datasets")
    def datasets():
        mars = [{"product_id": p.record.product_id, "data_set_id": p.record.data_set_id,
                 "version": p.record.product_version, "lat": [p.grid.lat_bottom, p.grid.lat_top],
                 "lon_east": [p.grid.lon_west, p.grid.lon_east], "quality_flags": p.record.quality_flags}
                for p in _megdr_tiles(settings)]
        earth = []
        if settings.srtm_dir.exists():
            for z in sorted(settings.srtm_dir.glob("*.SRTMGL1.hgt.zip")):
                name = z.name.split(".")[0]
                earth.append({"tile": name, "num_file": (settings.srtm_dir / f"{name}.SRTMGL1N.num.zip").exists()})
        return {"synthetic_data": settings.is_synthetic, "mars_megdr": mars, "earth_srtm": earth}

    @app.post(f"{P}/coverage/check", response_model=CoverageCheckResponse)
    def coverage_check(req: CoverageCheckRequest):
        # Coordinates are used for this check only: not stored, not logged.
        if srtm_gl1.coverage_status(req.lat) != "inside":
            return CoverageCheckResponse(status="outside_coverage", tile=None, tile_available_locally=False,
                                         message="Outside SRTM coverage (60 N to 56 S); analysis is not offered here.")
        tile = srtm_gl1.TileId.containing(req.lat, req.lon).name
        have = (settings.srtm_dir / f"{tile}.SRTMGL1.hgt.zip").exists()
        return CoverageCheckResponse(status="inside", tile=tile, tile_available_locally=have,
                                     message="Inside SRTM coverage." + ("" if have else " Tile not downloaded on the server."))

    @app.post(f"{P}/analyses", status_code=202, response_model=JobView)
    def submit(req: AnalysisRequest):
        _megdr_for(settings, req.target.lat, req.target.lon_east, req.target.patch_km)  # fail fast
        jid = store.create("mars_earth_analysis", json.loads(req.model_dump_json()))
        worker.submit(jid)
        return _view(store.get(jid))

    @app.get(f"{P}/jobs", response_model=list[JobView])
    def jobs(limit: int = 50):
        return [_view(j) for j in store.list(max(1, min(limit, 200)))]

    def _job(jid: str) -> dict:
        job = store.get(jid)
        if job is None:
            raise ApiError(404, "job_not_found", f"No job with id {jid!r}.")
        return job

    @app.get(f"{P}/jobs/{{jid}}", response_model=JobView)
    def job(jid: str):
        return _view(_job(jid))

    @app.post(f"{P}/jobs/{{jid}}/cancel", response_model=JobView)
    def cancel(jid: str):
        _job(jid)
        return _view(store.request_cancel(jid))

    @app.get(f"{P}/jobs/{{jid}}/result")
    def result(jid: str):
        job = _job(jid)
        if job["status"] != "succeeded":
            raise ApiError(409, "result_not_ready", f"Job is {job['status']}; a result exists only for succeeded jobs.",
                           {"status": job["status"], "error": json.loads(job["error"]) if job["error"] else None})
        return JSONResponse(json.loads(job["result"]))

    return app


