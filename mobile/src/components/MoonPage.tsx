import type { Datasets } from "../lib/api";
import type { Route } from "../App";
import type { useJob } from "../lib/useJob";
import { fmtVersion, label, unit } from "../lib/labels";
import type { PhotoState } from "./PhotoPanel";
import { emptyPhotoState } from "./PhotoPanel";
import { Results } from "./Results";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";

// Moon analysis is offered only when the server has a LOLA product that passed validation.
// Everything shown here comes from the server's dataset list or from a validated result.
export function MoonPage({ datasets, go, jobs, photo = emptyPhotoState }: {
  datasets: Datasets | null; go: (r: Route) => void; jobs?: ReturnType<typeof useJob>; photo?: PhotoState;
}) {
  const products = datasets?.moon_lola ?? [];
  const res = jobs?.result?.target.body === "MOON" ? jobs.result : null;

  if (products.length === 0 && !res) {
    return (
      <section aria-labelledby="moon-h">
        <div className="page-head">
          <p className="eyebrow" style={{ color: "#BF40FA" }}>Moon analogues · LOLA LDEM</p>
          <h2 id="moon-h">Lunar analogues are not available yet.</h2>
          <p className="lead">
            {datasets ? "The server has no validated lunar elevation product" : "The server's dataset list could not be loaded"}, so this
            app shows no Moon measurements and no Moon–Earth similarity. Nothing here suggests that an Earth site is suitable for a lunar base.
          </p>
        </div>
        <div className="grid-cards">
          <article className="card moon">
            <p className="eyebrow">How to enable</p>
            <h3>Download LDEM_64</h3>
            <p>The server accepts NASA PDS <strong>LRO-L-LOLA-4-GDR-V1.0</strong> product <strong>LDEM_64</strong> (version V3.1)
              after checking its label. See the README, “Moon: LOLA LDEM_64”.</p>
          </article>
          <OutOfScope />
        </div>
        <div className="row">
          <Button variant="aurora" onClick={() => go("mars")} icon={<Icon name="mars" />}>Explore Mars analogues</Button>
          <Button variant="ghost" onClick={() => go("method")} icon={<Icon name="method" />}>Methodology</Button>
        </div>
      </section>
    );
  }

  const tm = res?.target_metrics;
  return (
    <section aria-labelledby="moon-h">
      <div className="page-head">
        <p className="eyebrow" style={{ color: "#BF40FA" }}>Moon analogues · LOLA LDEM_64</p>
        <h2 id="moon-h">Moon target and its closest Earth terrain</h2>
        <p className="lead">Terrain-shape statistics only (slope, local relief, roughness), compared with Earth SRTM patches block-averaged to the target's grid spacing (LDEM_64: 474 m north–south, narrower east–west away from the equator).</p>
      </div>
      <div className="split">
        <article className="card moon">
          <p className="eyebrow">Lunar data on the server</p>
          {products.map((p) => (
            <dl className="kv" key={p.product_id}>
              <dt>Product</dt><dd>{p.product_id} {fmtVersion(p.version)} ({p.data_set_id})</dd>
              <dt>Coverage</dt><dd>latitude {p.lat[0]}° to {p.lat[1]}°, east longitude {p.lon_east[0]}° to {p.lon_east[1]}° (planetocentric)</dd>
              <dt>Grid spacing</dt><dd>{p.spacing_m != null ? `${p.spacing_m.toFixed(1)} m` : "unknown"} (north–south)</dd>
              <dt>Heights</dt><dd>above a 1737.4 km sphere — never compared with Earth heights</dd>
              <dt>Quality flags</dt><dd><ul>{p.quality_flags.map((f) => <li key={f}>{f}</li>)}</ul></dd>
            </dl>
          ))}
        </article>
        <article className="card moon">
          <p className="eyebrow">Moon target (reference data, not Earth)</p>
          {res ? (
            <dl className="kv">
              <dt>Centre</dt><dd>{res.target.center_lat != null ? `${Math.abs(res.target.center_lat).toFixed(2)}° ${res.target.center_lat >= 0 ? "N" : "S"}, ${res.target.center_lon_east?.toFixed(2)}° E (planetocentric)` : "—"}</dd>
              <dt>Patch</dt><dd>{res.target.patch_km} km · {res.target_record.product_id} {fmtVersion(res.target_record.product_version)}</dd>
              <dt>Height</dt><dd>{tm?.elevation_mean_m != null ? `mean ${tm.elevation_mean_m.toFixed(0)} ± ${tm.elevation_std_m?.toFixed(0)} m above the 1737.4 km sphere` : "—"}</dd>
              {Object.entries(res.ranking.target_features).map(([f, v]) => (
                <div key={f} style={{ display: "contents" }}><dt>{label(f)}</dt><dd className="mono">{v.toFixed(1)} {unit(f)}</dd></div>
              ))}
            </dl>
          ) : (
            <>
              <p>No Moon analysis in this session yet.</p>
              <Button variant="aurora" onClick={() => go("analysis")} icon={<Icon name="analysis" />}>Set up a Moon analysis</Button>
            </>
          )}
        </article>
      </div>
      {res && jobs && <Results jobs={jobs} photo={photo} />}
      <div className="grid-cards"><OutOfScope /></div>
    </section>
  );
}

function OutOfScope() {
  return (
    <article className="card moon">
      <p className="eyebrow">Out of scope</p>
      <h3>Not measured by this app</h3>
      <p>Temperature extremes, solar exposure, radiation, regolith composition, water-ice potential, resources and
        accessibility. These matter for settlement studies but need datasets the app does not use.</p>
    </article>
  );
}
