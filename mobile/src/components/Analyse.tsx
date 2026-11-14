import { useEffect, useState } from "react";
import { api, ApiError, type Datasets } from "../lib/api";
import { FEATURE_KEYS, label } from "../lib/labels";
import type { useJob } from "../lib/useJob";
import { JobStatus } from "./JobStatus";
import { ErrorBox } from "./ErrorBox";

type Jobs = ReturnType<typeof useJob>;

export function Analyse({ jobs, extraTiles, onShowResults }: { jobs: Jobs; extraTiles: string[]; onShowResults: () => void }) {
  const [ds, setDs] = useState<Datasets | null>(null);
  const [loadErr, setLoadErr] = useState<ApiError | null>(null);
  const [lat, setLat] = useState("-5.4");
  const [lon, setLon] = useState("137.8");
  const [patch, setPatch] = useState("40");
  const [stride, setStride] = useState("10");
  const [tiles, setTiles] = useState<string[]>([]);
  const [custom, setCustom] = useState(false);
  const [weights, setWeights] = useState<Record<string, string>>(Object.fromEntries(FEATURE_KEYS.map((k) => [k, "1"])));
  const [submitErr, setSubmitErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoadErr(null);
    api.datasets().then((d) => {
      setDs(d);
      setTiles((t) => (t.length ? t : d.earth_srtm.map((x) => x.tile)));
    }).catch(setLoadErr);
  };
  useEffect(load, []);
  useEffect(() => {
    if (extraTiles.length) setTiles((t) => Array.from(new Set([...t, ...extraTiles])));
  }, [extraTiles]);

  const running = jobs.job && (jobs.job.status === "queued" || jobs.job.status === "running");
  const allTiles = Array.from(new Set([...(ds?.earth_srtm.map((x) => x.tile) ?? []), ...extraTiles]));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitErr(null);
    setBusy(true);
    try {
      const w = custom ? Object.fromEntries(Object.entries(weights).map(([k, v]) => [k, Number(v)])) : null;
      const j = await api.submit({
        target: { lat: Number(lat), lon_east: Number(lon), patch_km: Number(patch) },
        earth_tiles: tiles, stride_km: Number(stride), weights: w,
      });
      jobs.start(j.id);
    } catch (err) {
      setSubmitErr(err as ApiError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="an-h">
      <h2 id="an-h">Analyse</h2>
      {jobs.jobId && <JobStatus jobs={jobs} onShowResults={onShowResults} />}
      {loadErr && <ErrorBox error={loadErr} onRetry={load} />}

      <form onSubmit={submit}>
        <div className="card">
          <h3>Mars target (MOLA MEGDR)</h3>
          {ds && ds.mars_megdr.length === 0 && <p>No MOLA tile is available on the server.</p>}
          {ds?.mars_megdr.map((m) => (
            <p key={m.product_id} className="hint">
              Available: {m.product_id} v{m.version} — latitude {m.lat[0]}° to {m.lat[1]}°, east longitude {m.lon_east[0]}° to {m.lon_east[1]}°
              (planetocentric). Heights relative to the areoid.
            </p>
          ))}
          <div className="grid2">
            <div>
              <label htmlFor="lat">Centre latitude (°, planetocentric)</label>
              <input id="lat" type="number" step="0.01" min={-88} max={88} required value={lat} onChange={(e) => setLat(e.target.value)} />
            </div>
            <div>
              <label htmlFor="lon">Centre longitude (° east, 0–360)</label>
              <input id="lon" type="number" step="0.01" min={0} max={359.99} required value={lon} onChange={(e) => setLon(e.target.value)} />
            </div>
            <div>
              <label htmlFor="patch">Patch size (km)</label>
              <input id="patch" type="number" step="1" min={10} max={80} required value={patch} onChange={(e) => setPatch(e.target.value)} />
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Earth candidates (SRTM GL1 v3)</h3>
          <p className="hint">Only the tiles ticked here are examined. Coverage: 60° N to 56° S.</p>
          {allTiles.length === 0 && <p>No SRTM tile is available on the server yet.</p>}
          <fieldset style={{ border: 0, padding: 0 }}>
            <legend className="sr-only">Earth tiles</legend>
            {allTiles.map((t) => {
              const info = ds?.earth_srtm.find((x) => x.tile === t);
              return (
                <label key={t} className="check">
                  <input type="checkbox" checked={tiles.includes(t)}
                    onChange={(e) => setTiles((xs) => (e.target.checked ? [...xs, t] : xs.filter((x) => x !== t)))} />
                  {t}{" "}
                  {!info ? "— from photo location; not downloaded on the server (will be reported as unavailable)"
                    : info.num_file ? "" : "— NUM file missing: void-fill unknown, candidates will be excluded"}
                </label>
              );
            })}
          </fieldset>
          <label htmlFor="stride">Spacing between candidate patches (km)</label>
          <input id="stride" type="number" step="1" min={2} max={40} required value={stride} onChange={(e) => setStride(e.target.value)} />
        </div>

        <div className="card">
          <h3>Similarity settings</h3>
          <label className="check">
            <input type="checkbox" checked={custom} onChange={(e) => setCustom(e.target.checked)} />
            Use custom feature weights (default: equal)
          </label>
          {custom && (
            <div className="grid2">
              {FEATURE_KEYS.map((k) => (
                <div key={k}>
                  <label htmlFor={`w-${k}`}>{label(k)}</label>
                  <input id={`w-${k}`} type="number" min={0} step="0.1" value={weights[k]}
                    onChange={(e) => setWeights((w) => ({ ...w, [k]: e.target.value }))} />
                </div>
              ))}
            </div>
          )}
        </div>

        {submitErr && <ErrorBox error={submitErr} />}
        <button className="primary" type="submit" disabled={busy || !!running || tiles.length === 0}>
          {running ? "Analysis running…" : "Run analysis"}
        </button>
      </form>
    </section>
  );
}
