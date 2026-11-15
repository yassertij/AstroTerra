import type { AnalysisResult, Datasets } from "../lib/api";
import type { Route } from "../App";
import { Button } from "./ui/Button";
import { Icon } from "./ui/Icon";

export function Overview({ go, datasets, result }: { go: (r: Route) => void; datasets: Datasets | null; result: AnalysisResult | null }) {
  const best = result?.ranking.results.find((r) => r.rank === 1);
  return (
    <section aria-labelledby="ov-h">
      <div className="hero">
        <p className="eyebrow">Planetary analogue research platform</p>
        <h1 id="ov-h">Earth is our testing ground.</h1>
        <p className="lead">
          Discover terrestrial landscapes whose <em>topography</em> resembles regions of Mars — measured with NASA
          elevation data, compared metric by metric, and documented down to the source file.
        </p>
        <div className="row" style={{ marginTop: 24 }}>
          <Button variant="aurora" size="lg" onClick={() => go("earth")} icon={<Icon name="earth" />}>Explore Earth locations</Button>
          <Button variant="ghost" size="lg" onClick={() => go("compare")} icon={<Icon name="compare" />}>Compare planetary environments</Button>
        </div>
      </div>

      <div className="grid-cards">
        <article className="card earth lift">
          <p className="eyebrow">Earth · SRTM GL1 v3</p>
          <div className="stat">{datasets ? datasets.earth_srtm.length : "—"}</div>
          <p>SRTM tile{datasets?.earth_srtm.length === 1 ? "" : "s"} available on the server (1″ ≈ 30 m, 60° N–56° S only).</p>
          <Button size="sm" onClick={() => go("earth")} icon={<Icon name="arrow" />}>Open map</Button>
        </article>
        <article className="card mars lift">
          <p className="eyebrow">Mars · MOLA MEGDR</p>
          <div className="stat">{datasets ? datasets.mars_megdr.length : "—"}</div>
          <p>MEGDR topography tile{datasets?.mars_megdr.length === 1 ? "" : "s"} (128 px/°, ≈ 463 m), heights relative to the areoid.</p>
          <Button size="sm" onClick={() => go("mars")} icon={<Icon name="arrow" />}>Mars analogues</Button>
        </article>
        <article className="card moon lift">
          <p className="eyebrow">Moon · LOLA LDEM_64</p>
          <div className="stat">{datasets ? (datasets.moon_lola?.length ?? 0) : "—"}</div>
          <p>{datasets && (datasets.moon_lola?.length ?? 0) > 0
            ? "Validated LOLA height grid (64 px/°, ≈ 474 m), heights above a 1737.4 km sphere."
            : "No validated lunar product on the server, so Moon analysis is unavailable."}</p>
          <Button size="sm" onClick={() => go("moon")} icon={<Icon name="arrow" />}>Moon analogues</Button>
        </article>
        <article className="card lift">
          <p className="eyebrow">Latest analysis</p>
          {best ? (
            <>
              <div className="stat mono">{best.distance?.toFixed(2)}</div>
              <p>Best distance (lower = more similar) among {result!.ranking.results.filter((r) => !r.excluded).length} Earth candidates — {best.candidate_id}.</p>
            </>
          ) : <p>No analysis in this session yet.</p>}
          <Button size="sm" variant="blue" onClick={() => go(best ? (result!.target.body === "MOON" ? "moon" : "mars") : "analysis")} icon={<Icon name="analysis" />}>
            {best ? "View ranking" : "Run an analysis"}
          </Button>
        </article>
      </div>

      <div className="card">
        <p className="eyebrow">Read before using the results</p>
        <ul>
          <li>This is a <strong>topographic analog assessment</strong>. It is not proof of geological, chemical, biological or
            environmental equivalence, and it does not mean a site is suitable for a settlement. Climate, temperature,
            vegetation, radiation and composition are <strong>not compared</strong>.</li>
          <li>The score is a distance: <strong>lower means more similar</strong>. It is not a probability, and the method has
            <strong> not been validated empirically</strong>.</li>
          <li>SRTM covers only <strong>60° N to 56° S</strong>; only the Earth tiles you select are examined — no global coverage.</li>
          <li>SRTM voids were filled with non-SRTM data (ASTER GDEM, GMTED2010, NED); their share is shown per candidate and
            candidates with more than 5 % fill are excluded.</li>
          <li>On Mars, cells without MOLA observations hold interpolated values that cannot yet be identified.</li>
          <li>Mars and Earth heights use different references (areoid vs EGM96 geoid), so absolute elevations are never compared.</li>
        </ul>
      </div>
    </section>
  );
}
