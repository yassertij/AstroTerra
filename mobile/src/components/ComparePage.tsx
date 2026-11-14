import type { AnalysisResult } from "../lib/api";
import type { Route } from "../App";
import { candidateValue, label, pct, unit } from "../lib/labels";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";

// Distinct series colours from the palette; each series is also labelled in text.
const SERIES = ["#BF40FA", "#4928C2", "#E3D9FC"];
const TARGET = "#5B2A62";

type Series = { name: string; colour: string; values: Record<string, number | null> };

function FeatureChart({ f, series }: { f: string; series: Series[] }) {
  const vals = series.map((s) => s.values[f]).filter((v): v is number => v != null);
  const max = Math.max(...vals.map(Math.abs), 1e-9);
  const W = 300, rowH = 26, labelW = 0;
  return (
    <figure className="card lift" style={{ margin: 0 }}>
      <figcaption className="eyebrow">{label(f)} ({unit(f)})</figcaption>
      <svg className="chart-svg" viewBox={`0 0 ${W} ${series.length * rowH}`} width="100%" role="img"
        aria-label={`${label(f)}: ${series.map((s) => `${s.name} ${s.values[f] == null ? "unavailable" : s.values[f]!.toFixed(1) + " " + unit(f)}`).join("; ")}`}>
        {series.map((s, i) => {
          const v = s.values[f];
          const w = v == null ? 0 : (Math.abs(v) / max) * (W - 90 - labelW);
          return (
            <g key={s.name} transform={`translate(0 ${i * rowH})`}>
              <rect x={0} y={5} width={Math.max(w, v == null ? 0 : 1)} height={14} rx={7} fill={s.colour} stroke="#E3D9FC" strokeOpacity={0.6} />
              <text x={Math.max(w, 0) + 6} y={16}>{v == null ? "unavailable" : `${v.toFixed(1)} ${unit(f)}`}</text>
            </g>
          );
        })}
      </svg>
    </figure>
  );
}

export function ComparePage({ result, selected, setSelected, go }: {
  result: AnalysisResult | null; selected: string[]; setSelected: (f: (s: string[]) => string[]) => void; go: (r: Route) => void;
}) {
  if (!result) {
    return (
      <section aria-labelledby="cmp-h">
        <div className="page-head">
          <p className="eyebrow">Comparison</p>
          <h2 id="cmp-h">Compare planetary environments</h2>
          <p className="lead">Comparisons use the results of an analysis. Run one first; nothing is pre-filled or invented.</p>
        </div>
        <Button variant="aurora" onClick={() => go("analysis")} icon={<Icon name="analysis" />}>Run an analysis</Button>
      </section>
    );
  }
  const ranked = result.ranking.results.filter((r) => !r.excluded);
  const ids = selected.filter((id) => ranked.some((r) => r.candidate_id === id));
  const chosen = (ids.length ? ids : ranked.slice(0, 3).map((r) => r.candidate_id))
    .map((id) => ranked.find((r) => r.candidate_id === id)!).filter(Boolean);
  const feats = result.ranking.features_used;
  const series: Series[] = [
    { name: "Mars target", colour: TARGET, values: Object.fromEntries(feats.map((f) => [f, result.ranking.target_features[f] ?? null])) },
    ...chosen.map((c, i) => ({ name: `Earth #${c.rank}`, colour: SERIES[i % SERIES.length], values: Object.fromEntries(feats.map((f) => [f, candidateValue(result, c, f)])) })),
  ];
  const toggle = (id: string) => setSelected((xs) => {
    const base = xs.length ? xs : chosen.map((c) => c.candidate_id);
    return base.includes(id) ? base.filter((x) => x !== id) : [...base, id].slice(-3);
  });

  return (
    <section aria-labelledby="cmp-h">
      <div className="page-head">
        <p className="eyebrow">Comparison · metric by metric</p>
        <h2 id="cmp-h">Mars target vs Earth candidates</h2>
        <p className="lead">Values come straight from the analysis. Mars values are reference data from MOLA; Earth values are measured from SRTM on the same ~{chosen[0]?.analysis_spacing_m.toFixed(0) ?? "462"} m grid.</p>
      </div>

      <div className="card">
        <p className="eyebrow">Choose up to 3 Earth candidates</p>
        <div className="row">
          {ranked.slice(0, 12).map((r) => (
            <label key={r.candidate_id} className="check" style={{ margin: 0 }}>
              <input type="checkbox" checked={chosen.some((c) => c.candidate_id === r.candidate_id)} onChange={() => toggle(r.candidate_id)} />
              #{r.rank} {r.candidate_id}
            </label>
          ))}
        </div>
        <p className="hint">Showing the top 12 ranked candidates; add others from the Earth map.</p>
      </div>

      <div className="row" aria-label="Series legend">
        {series.map((s) => (
          <span key={s.name} className="row" style={{ gap: 6 }}>
            <svg width="14" height="14" aria-hidden="true"><rect width="14" height="14" rx="7" fill={s.colour} stroke="#E3D9FC" strokeOpacity={0.6} /></svg>{s.name}
          </span>
        ))}
      </div>

      <div className="grid-cards" style={{ marginTop: 12 }}>
        {feats.map((f) => <FeatureChart key={f} f={f} series={series} />)}
      </div>

      <div className="card">
        <p className="eyebrow">Table</p>
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Feature values for the Mars target and the selected Earth candidates</caption>
            <thead><tr><th>Metric</th>{series.map((s) => <th key={s.name}>{s.name}</th>)}</tr></thead>
            <tbody>
              {feats.map((f) => (
                <tr key={f}>
                  <td>{label(f)}</td>
                  {series.map((s) => <td key={s.name} className="num">{s.values[f] == null ? "unavailable" : `${s.values[f]!.toFixed(1)} ${unit(f)}`}</td>)}
                </tr>
              ))}
              <tr><td>Distance to target</td><td className="num">0 (reference)</td>{chosen.map((c) => <td key={c.candidate_id} className="num">{c.distance?.toFixed(2)}</td>)}</tr>
              <tr><td>Void-fill share</td><td className="num">unknown (MOLA)</td>{chosen.map((c) => <td key={c.candidate_id} className="num">{pct(c.fill_fraction)}</td>)}</tr>
              <tr><td>Temperature, climate, geology</td>{series.map((s) => <td key={s.name}><span className="na">not measured</span></td>)}</tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid-cards">
        <div className="card moon"><p className="eyebrow">Earth vs Moon</p><p>Unavailable — no lunar data is integrated yet.</p></div>
        <div className="card moon"><p className="eyebrow">Moon vs Mars</p><p>Unavailable — no lunar data is integrated yet.</p></div>
      </div>
    </section>
  );
}
