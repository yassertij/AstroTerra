export const FEATURE_LABELS: Record<string, { label: string; unit: string }> = {
  slope_median_deg: { label: "Median slope", unit: "°" },
  relief_5km_m: { label: "Local relief, 5 km windows", unit: "m" },
  relief_10km_m: { label: "Local relief, 10 km windows", unit: "m" },
  relief_20km_m: { label: "Local relief, 20 km windows", unit: "m" },
  roughness_5km_m: { label: "Roughness, 5 km windows", unit: "m" },
  roughness_10km_m: { label: "Roughness, 10 km windows", unit: "m" },
  roughness_20km_m: { label: "Roughness, 20 km windows", unit: "m" },
};

export const FEATURE_KEYS = Object.keys(FEATURE_LABELS);

export function label(f: string): string {
  return FEATURE_LABELS[f]?.label ?? f;
}
export function unit(f: string): string {
  return FEATURE_LABELS[f]?.unit ?? "";
}

/** A candidate's own value for feature f, recovered from target value minus (target - candidate). */
export function candidateValue(
  res: { ranking: { target_features: Record<string, number> } },
  c: { feature_differences: Record<string, number> }, f: string,
): number | null {
  const t = res.ranking.target_features[f];
  const d = c.feature_differences[f];
  return t == null || d == null ? null : t - d;
}

export function pct(x: number | null | undefined, digits = 1): string {
  return x == null ? "unknown" : `${(x * 100).toFixed(digits)} %`;
}

/** Plain-language explanation of a candidate's score. */
/** "2.0" -> "v2.0"; "V3.1" stays "V3.1" (LOLA versions already carry the V). */
export function fmtVersion(v: string): string {
  return /^v/i.test(v) ? v : `v${v}`;
}

/** Display name of a target body. */
export function bodyName(body: string | undefined): string {
  return body === "MOON" ? "Moon" : "Mars";
}

/** Short description of the target dataset for a body. */
export function bodySource(body: string | undefined): string {
  return body === "MOON" ? "LOLA LDEM_64" : "MOLA MEGDR";
}

export function explain(contrib: Record<string, number>, diffs: Record<string, number>, body = "Mars"): string {
  const top = Object.entries(contrib).sort((a, b) => b[1] - a[1]).slice(0, 2);
  if (!top.length) return "No feature differences available.";
  const parts = top.map(([f, c]) => {
    const d = diffs[f];
    const dir = d > 0 ? `higher on the ${body} target` : d < 0 ? `lower on the ${body} target` : "equal";
    return `${label(f).toLowerCase()} (${Math.round(c * 100)} % of the distance; ${dir} by ${Math.abs(d).toFixed(1)} ${unit(f)})`;
  });
  return `The distance is driven mostly by ${parts.join(" and by ")}.`;
}
