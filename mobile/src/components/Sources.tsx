import { useEffect, useState } from "react";
import { api, ApiError, type Source } from "../lib/api";
import { ErrorBox } from "./ErrorBox";

export function Sources() {
  const [data, setData] = useState<{ approved: Source[]; excluded: Record<string, string> } | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const load = () => { setErr(null); api.sources().then(setData).catch(setErr); };
  useEffect(load, []);
  if (err) return <ErrorBox error={err} onRetry={load} />;
  if (!data) return <p>Loading the source catalogue…</p>;
  return (
    <section aria-labelledby="src-h">
      <h2 id="src-h">Data sources and citations</h2>
      <p>Only NASA-distributed datasets are used. Each entry was checked against the official archive.</p>
      {data.approved.map((s) => (
        <div className="card" key={s.key}>
          <h3>{s.data_set_id} ({s.body.toLowerCase()})</h3>
          <ul>
            <li>DOI: {s.doi}</li>
            <li>{s.mission} — {s.instrument}</li>
            <li>Archive: {s.archive}</li>
            <li>Vertical reference: {s.vertical_reference}</li>
            {s.notes && <li>Notes: {s.notes}</li>}
          </ul>
          <p><strong>Citation:</strong> {s.citation}</p>
        </div>
      ))}
      <h3>Excluded by policy</h3>
      <ul>{Object.entries(data.excluded).map(([k, v]) => <li key={k}><strong>{k}</strong>: {v}</li>)}</ul>
    </section>
  );
}
