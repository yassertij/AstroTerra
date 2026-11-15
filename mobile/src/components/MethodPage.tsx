import { Sources } from "./Sources";

export function MethodPage() {
  return (
    <section aria-labelledby="meth-h">
      <div className="page-head">
        <p className="eyebrow">Methodology · about</p>
        <h2 id="meth-h">How the comparison works</h2>
        <p className="lead">Every step is deterministic and recorded in the result and its exports. The method has not been validated empirically.</p>
      </div>
      <div className="grid-cards">
        <article className="card"><p className="eyebrow">1 · Common grid</p>
          <p>Earth (SRTM, ~30 m) is block-averaged to the target spacing (Mars MOLA ~463 m; Moon LOLA LDEM_64 ~474 m north–south). Nothing is upsampled; resampling adds no information.</p></article>
        <article className="card"><p className="eyebrow">2 · Terrain metrics</p>
          <p>Median slope (°); local relief (m) and roughness (m, residual of a fitted plane) on 5, 10 and 20 km windows. Absolute heights are never compared.</p></article>
        <article className="card"><p className="eyebrow">3 · Distance</p>
          <p>Each metric is scaled by 1.4826 × MAD over the eligible Earth candidates; the distance is the weighted Euclidean norm. Lower = more similar; it is not a probability.</p></article>
        <article className="card"><p className="eyebrow">4 · Exclusions & sensitivity</p>
          <p>Candidates with &lt; 80 % valid data or &gt; 5 % SRTM void fill are excluded. Ranks are re-tested under ±50 % weight changes (500 seeded runs) and with void-fill pixels removed.</p></article>
      </div>
      <div className="card">
        <p className="eyebrow">Roadmap</p>
        <ul>
          <li>Native Android/iOS testing; MOLA and LOLA observation counts to flag interpolated cells.</li>
          <li>More Earth tiles with a fixed reference scale; hillshade previews.</li>
          <li>Moon (LOLA LDEM_64) is integrated; higher-resolution lunar tiles would need mosaicking.</li>
        </ul>
      </div>
      <Sources />
    </section>
  );
}
