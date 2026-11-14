import { useCallback, useMemo, useState } from "react";
import type { AnalysisResult, CandidateResult, Datasets } from "../lib/api";
import type { Route } from "../App";
import { candidateValue, explain, label, pct, unit } from "../lib/labels";
import { EarthMap, tileBounds, type MapTile } from "./EarthMap";
import { PhotoPanel, type PhotoState } from "./PhotoPanel";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";

const NA = <span className="na">Not available — this app compares topography only</span>;

function fmtLat(x: number) { return `${Math.abs(x).toFixed(2)}° ${x >= 0 ? "N" : "S"}`; }
function fmtLon(x: number) { return `${Math.abs(x).toFixed(2)}° ${x >= 0 ? "E" : "W"}`; }

function LocationPanel({ c, res, onCompare, inCompare, go }: {
  c: CandidateResult; res: AnalysisResult; onCompare: () => void; inCompare: boolean; go: (r: Route) => void;
}) {
  const r = c.region;
  const e = c.elevation_m;
  const terrain = ["slope_median_deg", "relief_20km_m", "roughness_10km_m"];
  const t = res.target;
  return (
    <article className="card earth fade-in" aria-labelledby="loc-h">
      <p className="eyebrow">Earth location</p>
      <h3 id="loc-h">{c.excluded ? "Excluded" : `#${c.rank}`} · {c.candidate_id}</h3>
      <dl className="kv">
        <dt>Country / region</dt><dd><span className="na">Not available — the app does not geocode locations</span></dd>
        <dt>Coordinates</dt><dd>{r ? `${fmtLat(r.lat_min)}–${fmtLat(r.lat_max)}, ${fmtLon(r.lon_min)}–${fmtLon(r.lon_max)}` : "—"} (SRTM tile {c.tile})</dd>
        <dt>Elevation</dt>
        <dd>{e ? `${e.min.toFixed(0)}–${e.max.toFixed(0)} m (mean ${e.mean.toFixed(0)} ± ${e.std.toFixed(0)} m), above the EGM96 geoid` : "Not available for this result (re-run the analysis)"}</dd>
        <dt>Terrain</dt>
        <dd>{c.excluded ? "Not computed (excluded)" : terrain.map((f) => {
          const v = candidateValue(res, c, f);
          return <div key={f}>{label(f)}: {v == null ? "—" : `${v.toFixed(1)} ${unit(f)}`}</div>;
        })}</dd>
        <dt>Temperature range</dt><dd>{NA}</dd>
        <dt>Climate</dt><dd>{NA}</dd>
        <dt>Geology</dt><dd>{NA}</dd>
        <dt>Similarity</dt>
        <dd>{c.excluded ? c.exclusion_reasons.join("; ") : <>Distance <strong className="mono">{c.distance?.toFixed(2)}</strong> (lower = more similar). {explain(c.contributions, c.feature_differences)}</>}</dd>
        <dt>Planetary analogue</dt>
        <dd>Mars target{t.center_lat != null ? ` at ${Math.abs(t.center_lat).toFixed(2)}° ${t.center_lat >= 0 ? "N" : "S"}, ${t.center_lon_east?.toFixed(2)}° E` : ""}, {t.patch_km} km patch (MOLA MEGDR)</dd>
        <dt>Data quality</dt><dd>Valid {pct(c.valid_fraction)} · void fill {pct(c.fill_fraction)} · compared at ~{c.analysis_spacing_m.toFixed(0)} m</dd>
      </dl>
      <div className="row" style={{ marginTop: 12 }}>
        {!c.excluded && <Button size="sm" variant="blue" onClick={onCompare} icon={<Icon name="compare" />}>{inCompare ? "Remove from comparison" : "Add to comparison"}</Button>}
        <Button size="sm" variant="ghost" onClick={() => go("mars")} icon={<Icon name="mars" />}>Full explanation</Button>
      </div>
    </article>
  );
}

export function EarthPage({ datasets, dsError, onRetry, result, photo, setPhoto, onUseTile, go, compareIds = [], setCompareIds }: {
  datasets: Datasets | null; dsError: string | null; onRetry: () => void; result: AnalysisResult | null;
  photo: PhotoState; setPhoto: (f: (s: PhotoState) => PhotoState) => void; onUseTile: (t: string) => void; go: (r: Route) => void;
  compareIds?: string[]; setCompareIds?: (f: (s: string[]) => string[]) => void;
}) {
  const [q, setQ] = useState("");
  const [showExcluded, setShowExcluded] = useState(false);
  const [maxFill, setMaxFill] = useState("any");
  const [selected, setSelected] = useState<string | null>(null);

  const tiles: MapTile[] = useMemo(
    () => (datasets?.earth_srtm ?? []).map((t) => tileBounds(t.tile)).filter((t): t is MapTile => !!t),
    [datasets],
  );
  const candidates = useMemo(() => {
    const all = result?.ranking.results ?? [];
    const lim = maxFill === "any" ? Infinity : Number(maxFill);
    const needle = q.trim().toUpperCase();
    return all.filter((c) =>
      (showExcluded || !c.excluded) &&
      (c.fill_fraction == null ? maxFill === "any" : c.fill_fraction <= lim) &&
      (!needle || c.candidate_id.toUpperCase().includes(needle) || c.tile.toUpperCase().includes(needle)));
  }, [result, q, showExcluded, maxFill]);
  const sel = candidates.find((c) => c.candidate_id === selected) ?? null;
  const onSelect = useCallback((id: string) => setSelected(id), []);

  return (
    <section aria-labelledby="earth-h">
      <div className="page-head">
        <p className="eyebrow">Earth locations · SRTM GL1 v3</p>
        <h2 id="earth-h">Where on Earth does the terrain look like Mars?</h2>
        <p className="lead">Candidate patches from the latest analysis, on NASA imagery. Only downloaded tiles are examined.</p>
      </div>
      {dsError && (
        <div className="banner" role="alert"><strong>Error:</strong> {dsError} <Button size="sm" onClick={onRetry}>Try again</Button></div>
      )}

      <div className="split">
        <EarthMap tiles={tiles} candidates={candidates} selected={selected} onSelect={onSelect} />
        <div>
          <div className="card">
            <label htmlFor="earth-q"><Icon name="search" size={16} /> Search tile or candidate</label>
            <input id="earth-q" type="search" placeholder="e.g. N38W111" value={q} onChange={(e) => setQ(e.target.value)} />
            <div className="grid2">
              <div>
                <label htmlFor="fill">Max void fill</label>
                <select id="fill" value={maxFill} onChange={(e) => setMaxFill(e.target.value)}>
                  <option value="any">Any</option><option value="0.01">≤ 1 %</option><option value="0.05">≤ 5 %</option>
                </select>
              </div>
              <label className="check" style={{ marginTop: 28 }}>
                <input type="checkbox" checked={showExcluded} onChange={(e) => setShowExcluded(e.target.checked)} />Show excluded
              </label>
            </div>
          </div>

          {!result && (
            <div className="card">
              <p>No analysis in this session yet, so there are no candidates to show. {tiles.length} SRTM tile(s) are on the server.</p>
              <Button variant="aurora" onClick={() => go("analysis")} icon={<Icon name="analysis" />}>Run an analysis</Button>
            </div>
          )}
          {result && !sel && (
            <div className="card">
              <p className="eyebrow">{candidates.length} candidate(s) match</p>
              <div className="table-wrap" style={{ maxHeight: 320, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Rank</th><th>Candidate</th><th>Distance</th></tr></thead>
                  <tbody>
                    {candidates.map((c) => (
                      <tr key={c.candidate_id}>
                        <td className="num">{c.rank ?? "—"}</td>
                        <td><button className="btn btn-sm btn-ghost" onClick={() => setSelected(c.candidate_id)}>{c.candidate_id}</button></td>
                        <td className="num">{c.distance?.toFixed(2) ?? "excluded"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {result && sel && (
            <>
              <Button size="sm" variant="ghost" onClick={() => setSelected(null)}>← All candidates</Button>
              <LocationPanel c={sel} res={result} go={go} inCompare={compareIds.includes(sel.candidate_id)}
                onCompare={() => setCompareIds?.((xs) => xs.includes(sel.candidate_id) ? xs.filter((x) => x !== sel.candidate_id) : [...xs, sel.candidate_id].slice(-3))} />
            </>
          )}
        </div>
      </div>

      <div className="card">
        <p className="eyebrow"><Icon name="photo" size={14} /> Field photo · location and reference</p>
        <PhotoPanel state={photo} setState={setPhoto} result={result} onUseTile={onUseTile} />
      </div>
    </section>
  );
}
