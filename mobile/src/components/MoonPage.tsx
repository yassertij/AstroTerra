import type { Datasets } from "../lib/api";
import type { Route } from "../App";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";

// The Moon is not integrated yet. This page says so plainly and shows nothing measured.
export function MoonPage({ datasets, go }: { datasets: Datasets | null; go: (r: Route) => void }) {
  return (
    <section aria-labelledby="moon-h">
      <div className="page-head">
        <p className="eyebrow" style={{ color: "#BF40FA" }}>Moon analogues · LOLA GDRDEM</p>
        <h2 id="moon-h">Lunar analogues are not available yet.</h2>
        <p className="lead">
          No lunar elevation data is loaded, so this app shows no Moon measurements and no Moon–Earth similarity.
          Nothing here suggests that an Earth site is suitable for a lunar base.
        </p>
      </div>

      <div className="grid-cards">
        <article className="card moon">
          <p className="eyebrow">Status</p>
          <h3>Planned, not integrated</h3>
          <p>Source chosen: NASA PDS <strong>LRO-L-LOLA-4-GDR-V1.0</strong> (GDRDEM products only). Its identifier, height
            scaling and reference radius still have to be verified against the product labels before any use.</p>
          <p className="hint">Lunar tiles on the server: {datasets ? 0 : "—"}.</p>
        </article>
        <article className="card moon">
          <p className="eyebrow">What would be compared</p>
          <h3>Terrain shape only</h3>
          <p>The same metrics as for Mars — slope, local relief and roughness on kilometre windows — against Earth patches on a
            common grid. Absolute heights would not be compared (lunar heights use a reference radius, Earth the EGM96 geoid).</p>
        </article>
        <article className="card moon">
          <p className="eyebrow">Out of scope</p>
          <h3>Not measured by this app</h3>
          <p>Temperature extremes, solar exposure, radiation, regolith composition, water-ice potential, resources and
            accessibility. These matter for settlement studies but need datasets the app does not use.</p>
        </article>
      </div>
      <div className="row">
        <Button variant="aurora" onClick={() => go("mars")} icon={<Icon name="mars" />}>Explore Mars analogues</Button>
        <Button variant="ghost" onClick={() => go("method")} icon={<Icon name="method" />}>Roadmap and methodology</Button>
      </div>
    </section>
  );
}
