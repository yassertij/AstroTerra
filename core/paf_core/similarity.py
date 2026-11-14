"""Topographic similarity ranking (documented, reproducible). Lower distance = more similar.

Features (shape only; never absolute elevation, since datums differ between bodies):
    slope_median_deg, relief_{5,10,20}km_m, roughness_{5,10,20}km_m

Normalisation (robust): for each feature f, scale s_f = 1.4826 * MAD_f over the eligible
Earth candidates (MAD = median absolute deviation from the candidate median). A feature
whose MAD is 0 cannot be normalised and is dropped with a flag (no substitute value).

Distance: weighted Euclidean on normalised differences,
    z_f = (target_f - candidate_f) / s_f
    D   = sqrt( sum_f w_f z_f^2 / sum_f w_f )
Contribution of f = w_f z_f^2 / sum_g w_g z_g^2 (share of the squared distance).
D = 0 means identical feature values. D is a dissimilarity in MAD units; it is NOT a
probability and has not been validated empirically.

Exclusion: a candidate is excluded (with reason) if valid fraction < MIN_VALID_FRACTION,
if its non-SRTM (void-fill) fraction > MAX_FILL_FRACTION or unknown, or if a feature
is missing.

Sensitivity: N_PERTURB runs with each weight multiplied by U(1-PERTURB, 1+PERTURB)
(seeded), reporting each candidate's rank distribution.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from .errors import MetricError
from .metrics import TerrainMetrics

FEATURES = (
    "slope_median_deg",
    "relief_5km_m", "relief_10km_m", "relief_20km_m",
    "roughness_5km_m", "roughness_10km_m", "roughness_20km_m",
)
MIN_VALID_FRACTION = 0.8
MAX_FILL_FRACTION = 0.05
MAD_TO_SIGMA = 1.4826
MIN_ELIGIBLE = 3
N_PERTURB = 500
PERTURB = 0.5
SEED = 20261113


def features_from_metrics(tm: TerrainMetrics) -> dict[str, float]:
    out = {"slope_median_deg": tm.slope.median}
    for w in tm.windows:
        k = f"{w.window_m / 1000:g}km"
        out[f"relief_{k}_m"] = w.local_relief_m_median
        out[f"roughness_{k}_m"] = w.roughness_m_median
    return out


class Candidate(BaseModel):
    candidate_id: str
    tile: str
    region: dict  # pixel window + bounds in degrees (public terrain, not user location)
    features: dict[str, float]
    valid_fraction: float
    fill_fraction: float | None
    native_spacing_m: float
    analysis_spacing_m: float
    flags: list[str] = Field(default_factory=list)
    # Descriptive only, never used in the distance: heights use each body's own datum.
    elevation_m: dict[str, float] | None = None


class CandidateResult(BaseModel):
    candidate_id: str
    tile: str
    region: dict
    rank: int | None
    distance: float | None
    feature_differences: dict[str, float] = Field(default_factory=dict)  # target - candidate, native units
    normalized_differences: dict[str, float] = Field(default_factory=dict)
    contributions: dict[str, float] = Field(default_factory=dict)
    valid_fraction: float
    fill_fraction: float | None
    native_spacing_m: float
    analysis_spacing_m: float
    excluded: bool = False
    exclusion_reasons: list[str] = Field(default_factory=list)
    sensitivity: dict = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    elevation_m: dict[str, float] | None = None


class Ranking(BaseModel):
    score_meaning: str = (
        "Distance in robust (MAD) units; lower = more similar topographic statistics; "
        "0 = identical features. Not a probability; not empirically validated."
    )
    features_used: list[str]
    features_dropped: dict[str, str]
    weights: dict[str, float]
    normalization: dict[str, dict[str, float]]
    exclusion_rules: dict[str, float]
    sensitivity_method: dict
    target_features: dict[str, float]
    results: list[CandidateResult]
    flags: list[str] = Field(default_factory=list)


def _eligibility(c: Candidate, needed: list[str]) -> list[str]:
    reasons = []
    if c.valid_fraction < MIN_VALID_FRACTION:
        reasons.append(f"valid fraction {c.valid_fraction:.3f} < {MIN_VALID_FRACTION}")
    if c.fill_fraction is None:
        reasons.append("void-fill fraction unknown (no NUM file)")
    elif c.fill_fraction > MAX_FILL_FRACTION:
        reasons.append(f"non-SRTM fill fraction {c.fill_fraction:.3f} > {MAX_FILL_FRACTION}")
    missing = [f for f in needed if f not in c.features]
    if missing:
        reasons.append(f"features unavailable: {', '.join(missing)}")
    return reasons


def _distances(T: np.ndarray, C: np.ndarray, s: np.ndarray, w: np.ndarray) -> np.ndarray:
    z2 = ((T[None, :] - C) / s[None, :]) ** 2
    return np.sqrt((z2 * w[None, :]).sum(axis=1) / w.sum())


def _ranks(d: np.ndarray) -> np.ndarray:
    order = np.argsort(d, kind="stable")
    r = np.empty(len(d), dtype=int)
    r[order] = np.arange(1, len(d) + 1)
    return r


def rank_candidates(target: dict[str, float], candidates: list[Candidate],
                    weights: dict[str, float] | None = None) -> Ranking:
    needed = [f for f in FEATURES if f in target]
    flags = []
    if missing := [f for f in FEATURES if f not in target]:
        flags.append(f"target features unavailable: {', '.join(missing)}")
    w_all = {f: 1.0 for f in needed} if weights is None else {f: float(weights[f]) for f in needed}
    if any(v < 0 for v in w_all.values()) or sum(w_all.values()) <= 0:
        raise MetricError("Weights must be non-negative with a positive sum.")

    results: dict[str, CandidateResult] = {}
    eligible: list[Candidate] = []
    for c in candidates:
        reasons = _eligibility(c, needed)
        res = CandidateResult(
            candidate_id=c.candidate_id, tile=c.tile, region=c.region, rank=None, distance=None,
            valid_fraction=c.valid_fraction, fill_fraction=c.fill_fraction,
            native_spacing_m=c.native_spacing_m, analysis_spacing_m=c.analysis_spacing_m,
            excluded=bool(reasons), exclusion_reasons=reasons, flags=list(c.flags),
            elevation_m=c.elevation_m,
        )
        results[c.candidate_id] = res
        if not reasons:
            eligible.append(c)
    if len(eligible) < MIN_ELIGIBLE:
        raise MetricError(
            f"Only {len(eligible)} eligible candidates (minimum {MIN_ELIGIBLE}) - robust normalisation "
            "is unreliable. Examine more Earth area or relax the documented exclusion rules."
        )

    C = np.array([[c.features[f] for f in needed] for c in eligible])
    med = np.median(C, axis=0)
    scale = MAD_TO_SIGMA * np.median(np.abs(C - med), axis=0)
    dropped = {f: "MAD = 0 over candidates; cannot normalise" for f, s in zip(needed, scale) if s == 0}
    keep = [i for i, f in enumerate(needed) if f not in dropped]
    if not keep:
        raise MetricError("No feature can be normalised (all MADs are zero).")
    used = [needed[i] for i in keep]
    C, med, scale = C[:, keep], med[keep], scale[keep]
    T = np.array([target[f] for f in used])
    w = np.array([w_all[f] for f in used])

    d = _distances(T, C, scale, w)
    ranks = _ranks(d)
    z = (T[None, :] - C) / scale[None, :]
    wz2 = w[None, :] * z ** 2
    for k, c in enumerate(eligible):
        res = results[c.candidate_id]
        res.distance, res.rank = float(d[k]), int(ranks[k])
        res.feature_differences = {f: float(T[i] - C[k, i]) for i, f in enumerate(used)}
        res.normalized_differences = {f: float(z[k, i]) for i, f in enumerate(used)}
        tot = wz2[k].sum()
        res.contributions = {f: (float(wz2[k, i] / tot) if tot > 0 else 0.0) for i, f in enumerate(used)}

    # Sensitivity to weights.
    rng = np.random.default_rng(SEED)
    runs = np.empty((N_PERTURB, len(eligible)), dtype=int)
    for j in range(N_PERTURB):
        wj = w * rng.uniform(1 - PERTURB, 1 + PERTURB, size=w.shape)
        runs[j] = _ranks(_distances(T, C, scale, wj))
    for k, c in enumerate(eligible):
        rk = runs[:, k]
        results[c.candidate_id].sensitivity = {
            "weight_perturbation_rank_median": float(np.median(rk)),
            "rank_p05": int(np.percentile(rk, 5)), "rank_p95": int(np.percentile(rk, 95)),
            "same_rank_fraction": float(np.mean(rk == ranks[k])),
            "top1_fraction": float(np.mean(rk == 1)),
        }

    ordered = sorted(results.values(), key=lambda r: (r.rank is None, r.rank or 0, r.candidate_id))
    return Ranking(
        features_used=used, features_dropped=dropped,
        weights={f: float(x) for f, x in zip(used, w / w.sum())},
        normalization={f: {"median": float(m), "scale_1.4826MAD": float(s)} for f, m, s in zip(used, med, scale)},
        exclusion_rules={"min_valid_fraction": MIN_VALID_FRACTION, "max_fill_fraction": MAX_FILL_FRACTION},
        sensitivity_method={"runs": N_PERTURB, "weight_multiplier_range": [1 - PERTURB, 1 + PERTURB], "seed": SEED},
        target_features={f: float(target[f]) for f in used},
        results=ordered, flags=flags,
    )
