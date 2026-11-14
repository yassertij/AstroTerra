import type { Datasets } from "../lib/api";
import type { Route } from "../App";
import type { useJob } from "../lib/useJob";
import { label, unit } from "../lib/labels";
import type { PhotoState } from "./PhotoPanel";
import { Results } from "./Results";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";

/** Equirectangular sketch of Mars: available MEGDR tiles and the analysed target (real extents only). */
function MarsExtent({ datasets, target }: { datasets: Datasets | null; target?: { lat_min: number; lat_max: number; lon_min: number; lon_max: number } }) {
  const W = 360, H = 180;
  const x = (lon: number) => lon, y = (lat: number) => 90 - lat;
  return (
    <svg className="chart-svg" viewBox={`-2 -2 ${W + 4} ${H + 14}`} role="img"
      aria-label="Mars longitude 0 to 360 east, latitude 90 north to 90 south, showing available MOLA tiles and the analysed target">
      <rect x={0} y={0} width={W} height={H} fill="#040607" stroke="#E3D9FC" strokeOpacity={0.4} rx={4} />
      {[30, 60, 90, 120, 150].map((v) => <line key={v} x1={0} x2={W} y1={v} y2={v} stroke="#E3D9FC" strokeOpacity={0.08} />)}
      {[60, 120, 180, 240, 300].map((v) => <line key={v} y1={0} y2={H} x1={v} x2={v} stroke="#E3D9FC" strokeOpacity={0.08} />)}
      <line x1={0} x2={W} y1={90} y2={90} stroke="#E3D9FC" strokeOpacity={0.3} />
      {datasets?.mars_megdr.map((m) => (
        <rect key={m.product_id} x={x(m.lon_east[0])} y={y(m.lat[1])} width={m.lon_east[1] - m.lon_east[0]} height={m.lat[1] - m.lat[0]}
          fill="#5B2A62" fillOpacity={0.5} stroke="#E3D9FC" strokeOpacity={0.7}><title>{m.product_id}</title></rect>
      ))}
      {target && (
        <rect x={x(target.lon_min) - 1.5} y={y(target.lat_max) - 1.5} width={target.lon_max - target.lon_min + 3} height={target.lat_max - target.lat_min + 3}
          fill="#BF40FA" stroke="#E3D9FC" strokeWidth={1}><title>Analysed target</title></rect>
      )}
      <text x={2} y={H + 11}>0° E</text><text x={W / 2 - 12} y={H + 11}>180° E</text><text x={W - 34} y={H + 11}>360° E</text>
    </svg>
  );
}

export function MarsPage({ jobs, photo, datasets, go }: { jobs: ReturnType<typeof useJob>; photo: PhotoState; datasets: Datasets | null; go: (r: Route) => void }) {
  const res = jobs.result;
  const tm = res?.target_metrics;
  return (
    <section aria-labelledby="mars-h">
      <div className="page-head">
        <p className="eyebrow">Mars analogues · MOLA MEGDR</p>
        <h2 id="mars-h">Mars target and its closest Earth terrain</h2>
        <p className="lead">Why a patch ranks high: its slope, relief and roughness statistics are closest to the Mars target's. Nothing more is implied.</p>
      </div>

      <div className="split">
        <article className="card mars">
          <p className="eyebrow">Mars target (reference data, not Earth)</p>
          {res ? (
            <dl className="kv">
              <dt>Centre</dt><dd>{res.target.center_lat != null ? `${Math.abs(res.target.center_lat).toFixed(2)}° ${res.target.center_lat >= 0 ? "N" : "S"}, ${res.target.center_lon_east?.toFixed(2)}° E (planetocentric)` : "—"}</dd>
              <dt>Patch</dt><dd>{res.target.patch_km} km · {res.target_record.product_id} v{res.target_record.product_version}</dd>
              <dt>Elevation</dt><dd>{tm?.elevation_mean_m != null ? `mean ${tm.elevation_mean_m.toFixed(0)} ± ${tm.elevation_std_m?.toFixed(0)} m, relative to the areoid — not comparable with Earth heights` : "—"}</dd>
              {Object.entries(res.ranking.target_features).map(([f, v]) => (
                <div key={f} style={{ display: "contents" }}><dt>{label(f)}</dt><dd className="mono">{v.toFixed(1)} {unit(f)}</dd></div>
              ))}
              <dt>Not measured</dt><dd className="na">Temperature, dust, atmosphere, soil composition, water evidence</dd>
            </dl>
          ) : (
            <>
              <p>No analysis yet. Choose a Mars target and Earth tiles to rank candidates.</p>
              <Button variant="aurora" onClick={() => go("analysis")} icon={<Icon name="analysis" />}>Set up an analysis</Button>
            </>
          )}
        </article>
        <article className="card mars">
          <p className="eyebrow">Where on Mars</p>
          <MarsExtent datasets={datasets} target={res?.target.bounds} />
          <p className="hint">Velvet: MOLA tiles on the server. Magenta: analysed patch (enlarged so it stays visible).</p>
        </article>
      </div>

      <Results jobs={jobs} photo={photo} />
    </section>
  );
}
