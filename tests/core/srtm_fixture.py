"""SYNTHETIC SRTM GL1 tile builder - not real SRTM data.

Writes zips shaped like LP DAAC granules (N38W111.SRTMGL1.hgt.zip containing a
3601x3601 big-endian int16 .hgt, and N38W111.SRTMGL1N.num.zip with a uint8 .num).
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np

N = 3601


def write_tile(folder: Path, name: str = "N38W111", hgt: np.ndarray | None = None,
               num: np.ndarray | None = None, with_num: bool = True, hgt_bytes: bytes | None = None) -> tuple[Path, Path | None]:
    folder.mkdir(parents=True, exist_ok=True)
    if hgt is None:
        hgt = np.zeros((N, N), dtype=np.int16)
    hz = folder / f"{name}.SRTMGL1.hgt.zip"
    with zipfile.ZipFile(hz, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{name}.hgt", hgt_bytes if hgt_bytes is not None else hgt.astype(">i2").tobytes())
    nz = None
    if with_num:
        if num is None:
            num = np.full((N, N), 203, dtype=np.uint8)  # SRTM, 3 swaths
        nz = folder / f"{name}.SRTMGL1N.num.zip"
        with zipfile.ZipFile(nz, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{name}.num", num.astype(np.uint8).tobytes())
    return hz, nz
