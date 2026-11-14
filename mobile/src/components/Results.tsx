import { useState } from "react";
import { api, type AnalysisResult, type CandidateResult, type DatasetRecord } from "../lib/api";
import { explain, label, pct, unit } from "../lib/labels";
import { SEQUENTIAL } from "../lib/palette";
import type { useJob } from "../lib/useJob";
import type { PhotoState } from "./PhotoPanel";
import { JobStatus } from "./JobStatus";

function barColour(share: number): string {
  return SEQUENTIAL[Math.min(SEQUENTIAL.length - 1, Math.floor(share * SEQUENTIAL.length))];
}

function Contributions({ c }: { c: CandidateResult }) {
  const rows = Object.entries(c.contributions).sort((a, b) => b[1] - a[1]);
  return (
    <figure aria-label="Share of the distance contributed by each feature" style={{ margin: 0 }}>
      {rows.map(([f, share]) => (
        <div className="bar" key={f}>
          <span>{label(f)}</span>
          <div className="track" aria-hidden="true">
            <div className="fill" style={{ width: `${Math.max(1, share * 100)}%`, background: barColour(share) }} />
          </div>
          <span>{(share * 100).toFixed(0)} %</span>
        </div>
      ))}
      <figcaption className="hint">Bar length and the percentage both show each feature's share of the distance.</figcaption>
    </figure>
  );
}

function Detail({ r, res, photo }: { r: CandidateResult; res: AnalysisResult; photo: PhotoState }) {
  const s = r.sensitivity;
  const attached = photo.photoUrl && photo.attachedTo === r.candidate_id;
  return (
    <div className="card">
      <h3>#{r.rank} — {r.candidate_id}</h3>
      <p><strong>Distance {r.distance?.toFixed(2)}</strong> (lower = more similar; 0 = identical; not a probability).</p>
      <p>{explain(r.contributions, r.feature_differences)}</p>
      <Contributions c={r} />
      <table>
        <caption className="sr-only">Feature values</caption>
        <thead><tr><th>Feature</th><th>Mars target</th><th>This candidate</th><th>Difference</th></tr></thead>
        <tbody>
          {Object.keys(r.feature_differences).map((f) => {
            const t = res.ranking.target_features[f];
            const d = r.feature_differences[f];
            return (
              <tr key={f}>
                <td>{label(f)}</td>
                <td>{t.toFixed(1)} {unit(f)}</td>
                <td>{(t - d).toFixed(1)} {unit(f)}</td>
                <td>{d > 0 ? "+" : ""}{d.toFixed(1)} {unit(f)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <h4>Quality</h4>
      <ul>
        <li>Valid data: {pct(r.valid_fraction)}; void-fill (non-SRTM) share: {pct(r.fill_fraction)}</li>
        <li>Resolution: native ~{r.native_spacing_m.toFixed(0)} m, compared at ~{r.analysis_spacing_m.toFixed(0)} m (block mean, adds no information)</li>
        <li>Rank under ±50 % weight changes: median {s.weight_perturbation_rank_median}, range {s.rank_p05}–{s.rank_p95}; ranked first in {pct(s.top1_fraction, 0)} of runs</li>
        <li>Rank with void-fill pixels removed: {s.fill_excluded_rank ?? "not available"}</li>
      </ul>
      {attached && (
        <div className="photo-pair">
          <figure style={{ margin: 0 }}>
            <img src={photo.photoUrl!} alt="Your field photo" />
            <figcaption><strong>Photo observation</strong> — a visual reference, not a measurement.</figcaption>
          </figure>
          <p className="hint">Terrain previews (hillshade) are planned after the MVP; compare using the metrics above.</p>
        </div>
      )}
    </div>
  );
}

function Provenance({ name, rec }: { name: string; rec: DatasetRecord }) {
  return (
    <details className="card">
      <summary><strong>{name}</strong>: {rec.data_set_id} v{rec.product_version} ({rec.product_id})</summary>
      <ul>
        <li>DOI: {rec.doi}</li>
        <li>Mission / instrument: {rec.mission} / {rec.instrument}</li>
        <li>Archive: {rec.archive}</li>
        <li>Grid: {rec.projection}; {rec.horizontal_reference}</li>
        <li>Vertical reference: {rec.vertical_reference}; units: {rec.units}; no-data: {rec.fill_value}</li>
        <li>Citation: {rec.citation}</li>
      </ul>
      <h4>Processing history</h4>
      <ol>{rec.processing_history.map((s, i) => <li key={i}>{s.operation}{s.note ? ` — ${s.note}` : ""}</li>)}</ol>
      {rec.quality_flags.length > 0 && (<><h4>Quality flags</h4><ul>{rec.quality_flags.map((f) => <li key={f}>{f}</li>)}</ul></>)}
    </details>
  );
}

function Exports({ jobId }: { jobId: string }) {
  const [coords, setCoords] = useState(false);
  return (
    <div className="card">
      <h3>Export</h3>
      <p className="hint">Exports record datasets, versions, citations, settings, weights, normalisation, quality flags and limitations.</p>
      <label className="check">
        <input type="checkbox" checked={coords} onChange={(e) => setCoords(e.target.checked)} />
        Include region coordinates (rounded to about 1 km). Off by default.
      </label>
      <div className="row">
        <a className="button" href={api.exportUrl(jobId, "json", coords)} download>Download JSON</a>
        <a className="button" href={api.exportUrl(jobId, "csv", coords)} download>Download CSV</a>
      </div>
      <p className="hint">Photos and your device or photo location are never included in exports.</p>
    </div>
  );
}

export function Results({ jobs, photo }: { jobs: ReturnType<typeof useJob>; photo: PhotoState }) {
  const res = jobs.result;
  const [open, setOpen] = useState<string | null>(null);
  if (!jobs.jobId) return <p>No analysis yet. Start one from the Analyse tab.</p>;
  if (!res) return <JobStatus jobs={jobs} />;
  const ranked = res.ranking.results.filter((r) => !r.excluded);
  const excluded = res.ranking.results.filter((r) => r.excluded);
  const sel = ranked.find((r) => r.candidate_id === open) ?? ranked[0];
  const c = res.coverage;
  return (
    <section aria-labelledby="res-h">
      <h2 id="res-h">Results</h2>
      {res.is_synthetic && <div className="banner" role="alert"><strong>Synthetic demo data.</strong> Not a real finding.</div>}
      <div className="banner"><strong>Warnings</strong>
        <ul>{[res.ranking.score_meaning, ...res.limitations, ...res.ranking.flags].map((w) => <li key={w}>{w}</li>)}</ul>
      </div>

      <div className="card">
        <h3>Coverage</h3>
        <p>{c.selection_method} {c.note}</p>
        <ul>
          <li>Examined: {c.tiles_examined.join(", ") || "none"}</li>
          {Object.keys(c.tiles_unavailable).length > 0 && <li>Unavailable: {Object.entries(c.tiles_unavailable).map(([t, m]) => `${t} (${m})`).join(", ")}</li>}
          {c.tiles_outside_coverage.length > 0 && <li>Outside SRTM coverage: {c.tiles_outside_coverage.join(", ")}</li>}
          {Object.keys(c.tiles_failed).length > 0 && <li>Failed: {Object.entries(c.tiles_failed).map(([t, m]) => `${t} (${m})`).join("; ")}</li>}
        </ul>
      </div>

      <h3>Ranking ({ranked.length} candidates)</h3>
      <div style={{ overflowX: "auto" }}>
        <table>
          <caption className="sr-only">Earth candidates ranked by distance to the Mars target</caption>
          <thead><tr><th>Rank</th><th>Candidate</th><th>Distance</th><th>Rank range</th><th>Void fill</th><th></th></tr></thead>
          <tbody>
            {ranked.map((r) => (
              <tr key={r.candidate_id} aria-current={sel?.candidate_id === r.candidate_id ? "true" : undefined}>
                <td>{r.rank}</td><td>{r.candidate_id}</td><td>{r.distance?.toFixed(2)}</td>
                <td>{r.sensitivity.rank_p05}–{r.sensitivity.rank_p95}</td><td>{pct(r.fill_fraction)}</td>
                <td><button onClick={() => setOpen(r.candidate_id)} aria-label={`Explain ${r.candidate_id}`}>Explain</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sel && <Detail r={sel} res={res} photo={photo} />}

      {excluded.length > 0 && (
        <details className="card">
          <summary>{excluded.length} excluded candidate(s)</summary>
          <ul>{excluded.map((r) => <li key={r.candidate_id}>{r.candidate_id}: {r.exclusion_reasons.join("; ")}</li>)}</ul>
        </details>
      )}

      <h3>Provenance</h3>
      <Provenance name="Mars target" rec={res.target_record} />
      {Object.entries(res.earth_records).map(([t, rec]) => <Provenance key={t} name={`Earth ${t}`} rec={rec} />)}

      <Exports jobId={jobs.jobId} />
    </section>
  );
}
