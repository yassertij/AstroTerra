"""Provenance records. Any metadata that could not be verified is the string ``"unknown"``.

Records hold file *names* only, never absolute local paths, so they are safe to export.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

UNKNOWN = "unknown"


class ProcessingStep(BaseModel):
    operation: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DatasetRecord(BaseModel):
    product_id: str
    data_set_id: str
    product_version: str
    doi: str = UNKNOWN
    mission: str = UNKNOWN
    instrument: str = UNKNOWN
    archive: str = UNKNOWN
    access_url: str = UNKNOWN
    file_format: str = UNKNOWN
    license_or_terms: str = UNKNOWN
    body: str
    horizontal_reference: str = UNKNOWN
    projection: str = UNKNOWN
    latitude_type: str = UNKNOWN
    longitude_convention: str = UNKNOWN
    vertical_reference: str = UNKNOWN
    units: str = UNKNOWN
    scale_factor: str = UNKNOWN
    offset: str = UNKNOWN
    fill_value: str = UNKNOWN
    citation: str = UNKNOWN
    source_files: list[str] = Field(default_factory=list)
    checksum_md5: str = UNKNOWN
    checksum_verified: bool | None = None
    processing_history: list[ProcessingStep] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)
    is_synthetic: bool = False

    def add_step(self, operation: str, note: str = "", **parameters: Any) -> None:
        self.processing_history.append(ProcessingStep(operation=operation, parameters=parameters, note=note))


def md5_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest().upper()


def verify_md5(path: Path, expected: str) -> bool:
    return md5_file(path) == expected.strip().upper()


def parse_md5_manifest(text: str) -> dict[str, str]:
    """Parse ``HASH  path`` lines (PDS volumes use Windows backslashes). Keys are lowercase basenames."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 32:
            name = parts[-1].replace("\\", "/").rsplit("/", 1)[-1].lower()
            out[name] = parts[0].upper()
    return out
