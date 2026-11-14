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
        return cls(data_dir=data, db_path=db)
