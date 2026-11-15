"""FastAPI application. Run:  uvicorn paf_api.main:create_app --factory  (see README)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from paf_core import DISCLAIMER, __version__ as core_version
from paf_core import export
from paf_core.errors import PafError
from paf_core.search import analyze_target
from paf_core.sources import lola_gdr, mola_megdr, srtm_gl1
from paf_core.sources.registry import EXCLUDED, LOLA_GDR, MOLA_MEGDR, SRTM_GL1, SRTM_GL1N

from . import API_VERSION
from .config import Settings
from .jobs import JobStore, Worker
from .schemas import AnalysisRequest, CoverageCheckRequest, CoverageCheckResponse, JobView

log = logging.getLogger("paf_api")
P = f"/{API_VERSION}"
IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class _TooLarge(Exception):
    pass


class BodyLimit:
    """Pure-ASGI guard: rejects request bodies larger than ``max_bytes`` with a structured 413."""

    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def _reject(self, send) -> None:
        body = json.dumps({"error": {"code": "payload_too_large",
                                     "message": f"Request body exceeds {self.max_bytes} bytes.", "details": None}}).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers") or []).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > self.max_bytes):
            return await self._reject(send)
        seen = 0

        async def limited():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.max_bytes:
                    raise _TooLarge()
            return msg

        try:
            await self.app(scope, limited, send)
        except _TooLarge:
            await self._reject(send)


class RateLimiter:
    """Sliding one-minute window per client address (in memory; resets on restart)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client: str) -> float | None:
        """Record a hit; return seconds to wait if over the limit, else None."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[client]
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return 60 - (now - q[0])
            q.append(now)
            return None


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


def _lola_products(settings: Settings) -> list[lola_gdr.LolaProduct]:
    out = []
    for lbl in sorted(settings.lola_dir.glob("*.lbl")) if settings.lola_dir.exists() else []:
        try:
            out.append(lola_gdr.open_lola(lbl))
        except (PafError, OSError) as exc:
            log.warning("LOLA label %s rejected: %s", lbl.name, type(exc).__name__)
    return out


def _lola_for(settings: Settings, lat: float, lon: float, patch_km: float) -> Path:
    products = _lola_products(settings)
    for p in products:
        if lola_gdr.contains(p, *lola_gdr.window_from_center_km(p, lat, lon, patch_km)):
            return p.label_path
    extents = [{"product_id": p.record.product_id, "lat": [p.grid.lat_bottom, p.grid.lat_top],
                "lon_east": [p.grid.lon_west, p.grid.lon_east]} for p in products]
    raise TargetNotAvailable(
        "No validated local LOLA LDEM product contains the requested target patch. "
        "Download LDEM_64 (see README) or choose another target.", extents)


def _target_label(settings: Settings, body: str, lat: float, lon: float, patch_km: float) -> Path:
    return (_lola_for if body == "MOON" else _megdr_for)(settings, lat, lon, patch_km)


def make_runner(settings: Settings):
    def run(params: dict, progress, should_cancel) -> dict:
        req = AnalysisRequest.model_validate(params)
        t = req.target
        label = _target_label(settings, t.body, t.lat, t.lon_east, t.patch_km)
        res = analyze_target(
            t.body, label, t.lat, t.lon_east, req.earth_tiles, settings.srtm_dir, settings.work_dir,
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
        purged = store.purge_older_than(settings.job_retention_days)
        if purged:
            log.info("%d finished job(s) older than %g days deleted", purged, settings.job_retention_days)
        if start_worker:
            worker.start()
            for jid in store.queued_ids():  # the queue lives in memory: resume jobs queued before a restart
                worker.submit(jid)
        yield
        if start_worker:
            worker.stop()
        store.close()

    app = FastAPI(title="Planetary Analog Finder API", version=core_version, lifespan=lifespan,
                  description=DISCLAIMER)
    app.state.settings, app.state.store, app.state.worker = settings, store, worker
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Idempotency-Key"])
    app.add_middleware(BodyLimit, max_bytes=settings.max_body_bytes)
    limiter = RateLimiter(settings.submit_rate_per_minute)

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

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.error("unhandled %s in request handler", type(exc).__name__, exc_info=exc)
        return _err(500, "internal_error", "Unexpected server error; the details are in the server log.")

    @app.get(f"{P}/ready")
    def ready():
        """Readiness: database usable, worker alive, at least one target product and one Earth tile."""
        mars, moon = _megdr_tiles(settings), _lola_products(settings)
        earth = sorted(settings.srtm_dir.glob("*.SRTMGL1.hgt.zip")) if settings.srtm_dir.exists() else []
        checks = {"database": store.ping(), "worker": worker.alive if start_worker else None,
                  "mars_target_products": len(mars), "moon_target_products": len(moon), "earth_tiles": len(earth)}
        problems = []
        if not checks["database"]:
            problems.append("job database not usable")
        if start_worker and not checks["worker"]:
            problems.append("background worker is not running")
        if not (mars or moon):
            problems.append("no validated Mars or Moon target product in the data directory")
        if not earth:
            problems.append("no SRTM tile in the data directory")
        return JSONResponse({"ready": not problems, "checks": checks, "problems": problems},
                            status_code=200 if not problems else 503)

    @app.get(f"{P}/health")
    def health():
        return {"status": "ok", "api_version": API_VERSION, "core_version": core_version,
                "synthetic_data": settings.is_synthetic, "disclaimer": DISCLAIMER}

    @app.get(f"{P}/sources")
    def sources():
        return {"approved": [asdict(s) for s in (MOLA_MEGDR, LOLA_GDR, SRTM_GL1, SRTM_GL1N)], "excluded": EXCLUDED}

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
        moon = [{"product_id": p.record.product_id, "data_set_id": p.record.data_set_id,
                 "version": p.record.product_version, "lat": [p.grid.lat_bottom, p.grid.lat_top],
                 "lon_east": [p.grid.lon_west, p.grid.lon_east], "spacing_m": round(float(p.grid.dy_m()[0]), 1),
                 "quality_flags": p.record.quality_flags}
                for p in _lola_products(settings)]
        return {"synthetic_data": settings.is_synthetic, "mars_megdr": mars, "moon_lola": moon, "earth_srtm": earth}

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
    def submit(req: AnalysisRequest, request: Request,
               idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
        params = json.loads(req.model_dump_json())
        kind = f"{req.target.body.lower()}_earth_analysis"
        fp = store.fingerprint(kind, params)
        if idempotency_key is not None:
            if not IDEMPOTENCY_KEY_RE.match(idempotency_key):
                raise ApiError(422, "validation_error", "Idempotency-Key must be 8-64 characters [A-Za-z0-9_-].")
            prior = store.find_by_key(idempotency_key)
            if prior is not None:
                if prior["fingerprint"] != fp:
                    raise ApiError(409, "idempotency_conflict",
                                   "This Idempotency-Key was already used for a different request.")
                return JSONResponse(json.loads(_view(prior).model_dump_json()), status_code=200)
        active = store.find_active(fp)
        if active is not None:  # identical analysis already queued or running: reuse it
            return JSONResponse(json.loads(_view(active).model_dump_json()), status_code=200)
        wait = limiter.check(request.client.host if request.client else "unknown")
        if wait is not None:
            raise ApiError(429, "rate_limited", f"Too many submissions; try again in {wait:.0f} s.",
                           {"retry_after_s": round(wait)})
        if store.count_active() >= settings.max_active_jobs:
            raise ApiError(503, "server_busy", "Too many analyses are queued or running; try again later.")
        _target_label(settings, req.target.body, req.target.lat, req.target.lon_east, req.target.patch_km)  # fail fast
        jid = store.create(kind, params, idempotency_key)
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

    @app.get(f"{P}/jobs/{{jid}}/export")
    def export_result(jid: str, format: str = Query("json", pattern="^(json|csv)$"),
                      include_coordinates: bool = False):
        res = result(jid)  # raises 404 / 409 as appropriate
        data = json.loads(res.body)
        stem = f"planetary-analog-{jid[:8]}"
        if format == "csv":
            body, media = export.to_csv(data, include_coordinates), "text/csv; charset=utf-8"
        else:
            body, media = export.to_json(data, include_coordinates), "application/json"
        return Response(body, media_type=media,
                        headers={"Content-Disposition": f'attachment; filename="{stem}.{format}"'})

    return app


