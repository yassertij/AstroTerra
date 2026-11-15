// Structural and numerical checks on an analysis result BEFORE it is shown as completed.
// A result that fails any check is never displayed; the user sees the problems instead.
import type { AnalysisResult } from "./api";

const isObj = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null && !Array.isArray(x);
const isNum = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);
const isStr = (x: unknown): x is string => typeof x === "string";

export function validateResult(x: unknown): { ok: true; result: AnalysisResult } | { ok: false; problems: string[] } {
  const p: string[] = [];
  if (!isObj(x)) return { ok: false, problems: ["result is not a JSON object"] };
  if (!isStr(x.disclaimer)) p.push("disclaimer missing");
  if (typeof x.is_synthetic !== "boolean") p.push("is_synthetic missing");
  const t = x.target;
  if (!isObj(t) || (t.body !== "MARS" && t.body !== "MOON")) p.push("target body missing or unsupported");
  else if (!isNum(t.patch_km) || t.patch_km <= 0) p.push("target patch size invalid");
  const rec = x.target_record;
  if (!isObj(rec) || !isStr(rec.data_set_id) || !isStr(rec.product_version) || !Array.isArray(rec.processing_history)) {
    p.push("target provenance record incomplete");
  } else if (isObj(t) && isStr(rec.body) && rec.body !== t.body) {
    p.push(`target record body ${rec.body} does not match target ${String(t.body)}`);
  }
  if (!isObj(x.earth_records)) p.push("Earth provenance records missing");
  if (!isObj(x.coverage) || !Array.isArray(x.coverage.tiles_examined)) p.push("coverage report missing");
  if (!Array.isArray(x.limitations)) p.push("limitations missing");
  const rk = x.ranking;
  if (!isObj(rk) || !Array.isArray(rk.results) || !Array.isArray(rk.features_used) || !isObj(rk.target_features)) {
    p.push("ranking missing or incomplete");
    return { ok: false, problems: p };
  }
  for (const f of rk.features_used as unknown[]) {
    if (!isStr(f) || !isNum((rk.target_features as Record<string, unknown>)[f])) p.push(`target feature ${String(f)} missing or not finite`);
  }
  const ids = new Set<string>();
  const ranked: { rank: number; distance: number }[] = [];
  for (const [i, c] of (rk.results as unknown[]).entries()) {
    if (!isObj(c) || !isStr(c.candidate_id)) { p.push(`candidate ${i} has no id`); continue; }
    if (ids.has(c.candidate_id)) p.push(`duplicate candidate id ${c.candidate_id}`);
    ids.add(c.candidate_id);
    if (c.excluded === true) {
      if (c.rank != null || c.distance != null) p.push(`excluded candidate ${c.candidate_id} has a rank or distance`);
      if (!Array.isArray(c.exclusion_reasons) || c.exclusion_reasons.length === 0) p.push(`excluded candidate ${c.candidate_id} has no reason`);
      continue;
    }
    if (!isNum(c.distance) || c.distance < 0) p.push(`candidate ${c.candidate_id} distance missing or not finite`);
    if (!Number.isInteger(c.rank) || (c.rank as number) < 1) p.push(`candidate ${c.candidate_id} rank invalid`);
    if (!isObj(c.contributions) || !isObj(c.feature_differences)) p.push(`candidate ${c.candidate_id} explanation missing`);
    if (!isNum(c.valid_fraction) || !isNum(c.analysis_spacing_m)) p.push(`candidate ${c.candidate_id} quality fields missing`);
    if (isNum(c.distance) && Number.isInteger(c.rank)) ranked.push({ rank: c.rank as number, distance: c.distance });
  }
  const ranks = ranked.map((r) => r.rank).sort((a, b) => a - b);
  if (ranks.some((r, i) => r !== i + 1)) p.push("ranks are not 1..n without gaps");
  const byRank = [...ranked].sort((a, b) => a.rank - b.rank);
  if (byRank.some((r, i) => i > 0 && r.distance < byRank[i - 1].distance - 1e-12)) p.push("ranks are not ordered by distance");
  return p.length ? { ok: false, problems: p } : { ok: true, result: x as unknown as AnalysisResult };
}
