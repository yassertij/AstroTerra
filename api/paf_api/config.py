"""Backend settings from environment variables (no secrets are needed by the API)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173", "http://127.0.0.1:5173",  # Vite dev server
        "capacitor://localhost", "http://localhost", "https://localhost",  # Capacitor iOS / Android webviews
    )
    max_body_bytes: int = 16_384  # analysis requests are < 2 KB
    max_active_jobs: int = 20  # queued + running; beyond this submissions get 503
    submit_rate_per_minute: int = 10  # per client address
    job_retention_days: float = 30.0  # finished jobs and their results are deleted after this

    @property
    def lola_dir(self) -> Path:
        return self.data_dir / "raw" / "lola_gdr"

    @property
    def megdr_dir(self) -> Path:
        return self.data_dir / "raw" / "mola_megdr"

    @property
    def srtm_dir(self) -> Path:
        return self.data_dir / "raw" / "srtm"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "processed" / "srtm"

    @property
    def is_synthetic(self) -> bool:
        """A data directory containing a file named SYNTHETIC holds demo/test data only."""
        return (self.data_dir / "SYNTHETIC").exists()

    @classmethod
    def from_env(cls) -> "Settings":
        data = Path(os.environ.get("PAF_DATA_DIR", REPO_ROOT / "data")).resolve()
        db = Path(os.environ.get("PAF_DB_PATH", data / "processed" / "paf_jobs.sqlite3")).resolve()
        kw: dict = {}
        origins = os.environ.get("PAF_CORS_ORIGINS")
        if origins:
            kw["cors_origins"] = tuple(o.strip() for o in origins.split(",") if o.strip())
        for env, key, typ in (("PAF_MAX_BODY_BYTES", "max_body_bytes", int), ("PAF_MAX_ACTIVE_JOBS", "max_active_jobs", int),
                              ("PAF_SUBMIT_RATE_PER_MINUTE", "submit_rate_per_minute", int),
                              ("PAF_JOB_RETENTION_DAYS", "job_retention_days", float)):
            if os.environ.get(env):
                kw[key] = typ(os.environ[env])
        return cls(data_dir=data, db_path=db, **kw)
