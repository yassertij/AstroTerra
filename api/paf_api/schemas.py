"""Request/response models. Unknown fields are rejected."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from paf_core.similarity import FEATURES

TileName = Annotated[str, Field(pattern=r"^[NS]\d{2}[EW]\d{3}$", description="SRTM tile, e.g. N38W111")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Target(Strict):
    body: Literal["MARS", "MOON"] = Field(default="MARS", description="MARS: MOLA MEGDR; MOON: LOLA LDEM_64")
    lat: float = Field(ge=-88.0, le=88.0, description="Planetocentric latitude, degrees")
    lon_east: float = Field(ge=0.0, lt=360.0, description="East longitude, 0-360 degrees")
    patch_km: float = Field(default=40.0, ge=10.0, le=80.0)


MarsTarget = Target  # backward-compatible name


class AnalysisRequest(Strict):
    target: Target
    earth_tiles: list[TileName] = Field(min_length=1, max_length=20)
    stride_km: float = Field(default=10.0, ge=2.0, le=40.0)
    weights: dict[str, float] | None = None

    @field_validator("earth_tiles")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("earth_tiles contains duplicates")
        return v

    @field_validator("weights")
    @classmethod
    def _weights(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is None:
            return v
        unknown = set(v) - set(FEATURES)
        if unknown:
            raise ValueError(f"unknown features {sorted(unknown)}; allowed: {list(FEATURES)}")
        if set(v) != set(FEATURES):
            raise ValueError(f"weights must give every feature: {list(FEATURES)}")
        if any(x < 0 for x in v.values()) or sum(v.values()) <= 0:
            raise ValueError("weights must be non-negative with a positive sum")
        return v


class CoverageCheckRequest(Strict):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class CoverageCheckResponse(BaseModel):
    status: Literal["inside", "outside_coverage"]
    tile: str | None
    tile_available_locally: bool
    message: str


class JobView(BaseModel):
    id: str
    kind: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    progress: float
    message: str
    error: dict | None
    created: str
    updated: str
    links: dict[str, str]
