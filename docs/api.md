# API reference and deployment (v1)

Base path `/v1`. Interactive schema at `/docs` while the server runs. All errors use
`{"error": {"code", "message", "details"}}`; messages never contain stack traces, local
paths or credentials.

## Endpoints

| Method | Path | Purpose | Main responses |
|---|---|---|---|
| GET | `/health` | Liveness, versions, synthetic-data flag | 200 |
| GET | `/ready` | Readiness: job DB usable, worker alive, ≥1 validated target product (Mars or Moon), ≥1 SRTM tile | 200 ready / 503 with `problems` |
| GET | `/sources` | NASA allow-list (MOLA MEGDR, LOLA GDR, SRTMGL1, SRTMGL1N) and excluded products | 200 |
| GET | `/datasets` | Data actually present and validated: `mars_megdr`, `moon_lola` (with extents, spacing, quality flags), `earth_srtm` (tile, NUM present) | 200 |
| POST | `/coverage/check` | `{lat, lon}` → inside/outside SRTM coverage and tile name (coordinates not stored or logged) | 200, 422 |
| POST | `/analyses` | Submit an analysis job (body below) | 202 new job; 200 existing job (idempotent replay or identical active job); 409 `idempotency_conflict`; 413 `payload_too_large`; 422 `validation_error` / `target_not_available`; 429 `rate_limited`; 503 `server_busy` |
| GET | `/jobs?limit=` | Recent jobs (id, status, progress — no parameters) | 200 |
| GET | `/jobs/{id}` | Status: `queued`, `running`, `succeeded`, `failed`, `cancelled`; progress 0–1; message; error | 200, 404 |
| POST | `/jobs/{id}/cancel` | Queued → cancelled at once; running → cancelled at the next checkpoint | 200, 404 |
| GET | `/jobs/{id}/result` | Full result (only for `succeeded`) | 200, 404, 409 `result_not_ready` |
| GET | `/jobs/{id}/export?format=json|csv&include_coordinates=false` | Export; coordinates and pixel offsets removed by default, rounded to 0.01° on opt-in | 200, 404, 409, 422 |

### Analysis request

```json
{
  "target": {"body": "MARS", "lat": -5.4, "lon_east": 137.8, "patch_km": 40},
  "earth_tiles": ["N38W111"],
  "stride_km": 10,
  "weights": null
}
```

- `body`: `MARS` (MOLA MEGDR) or `MOON` (LOLA LDEM_64); default `MARS`.
- `lat` −88…88 (planetocentric), `lon_east` 0…<360 (east-positive), `patch_km` 10…80,
  `stride_km` 2…40, 1–20 unique SRTM tile names.
- `weights`: `null` (equal) or a value ≥ 0 for each of the 7 features, positive sum.
- Unknown fields, `NaN` and `Infinity` are rejected.
- Optional header `Idempotency-Key` (8–64 chars `[A-Za-z0-9_-]`): resending the same key with
  the same body returns the original job; with a different body returns 409. Without a key,
  an identical request that is still queued or running returns that job instead of queuing
  a duplicate.

## Job lifecycle

`queued → running → succeeded | failed | cancelled`. One worker thread runs jobs in order.
Job records persist in SQLite. On startup: jobs left `running` are marked `failed`
(`interrupted`); jobs still `queued` are put back on the queue; finished jobs older than
`PAF_JOB_RETENTION_DAYS` are deleted. Logs contain job ids and states only.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `PAF_DATA_DIR` | `./data` | Root containing `raw/mola_megdr`, `raw/lola_gdr`, `raw/srtm`, `processed/` |
| `PAF_DB_PATH` | `data/processed/paf_jobs.sqlite3` | Job database |
| `PAF_CORS_ORIGINS` | Vite dev + Capacitor origins | Comma-separated allowed origins |
| `PAF_MAX_BODY_BYTES` | 16384 | Request body limit (413 above) |
| `PAF_MAX_ACTIVE_JOBS` | 20 | Queued + running jobs before 503 |
| `PAF_SUBMIT_RATE_PER_MINUTE` | 10 | Submissions per client address per minute (429 above) |
| `PAF_JOB_RETENTION_DAYS` | 30 | Finished jobs and results deleted after this |

A file named `SYNTHETIC` in the data directory marks every result as synthetic.

## Deployment

The API has **no authentication**. Run it only on a trusted network, or behind a reverse
proxy that terminates TLS and adds access control. For a hosted deployment:

1. Run `uvicorn paf_api.main:create_app --factory --host 127.0.0.1 --port 8765` behind a TLS
   reverse proxy (e.g. Caddy or nginx) serving `https://<your-host>`.
2. Set `PAF_CORS_ORIGINS=https://localhost,capacitor://localhost` (Capacitor release origins)
   plus any web origin you serve the app from.
3. Build the app with `VITE_PAF_API_BASE=https://<your-host>` and sync Capacitor with
   `PAF_RELEASE=1` (see README). Release builds refuse plain HTTP.
4. Rate limits are per process and in memory; behind a proxy every client may appear as the
   proxy address — configure the proxy to rate-limit instead, or raise the limit.

Persistent state: the SQLite file and the read-only raw data. Back up the database if job
history matters; results can be regenerated from the same data and settings.
