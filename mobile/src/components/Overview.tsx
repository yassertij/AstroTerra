export function Overview({ onStart }: { onStart: () => void }) {
  return (
    <section aria-labelledby="ov-h">
      <h2 id="ov-h">What this app does</h2>
      <p>
        It compares the <em>shape</em> of a Mars region (slope, local relief and roughness) with candidate regions on
        Earth, using only NASA elevation data: MOLA MEGDR for Mars and SRTM GL1 v3 for Earth.
      </p>
      <div className="card">
        <h3>Read before using the results</h3>
        <ul>
          <li>This is a <strong>topographic analog assessment</strong>. It is not proof of geological, chemical,
            biological or environmental equivalence. Climate, vegetation and composition are not compared.</li>
          <li>The score is a distance: <strong>lower means more similar</strong>. It is not a probability, and the
            method has <strong>not been validated empirically</strong>.</li>
          <li>SRTM covers only <strong>60° N to 56° S</strong>. Only the Earth tiles you select are examined; there is
            no global coverage.</li>
          <li>SRTM voids were filled with non-SRTM data (ASTER GDEM, GMTED2010, NED). Their share is shown for every
            candidate, and candidates with more than 5 % fill are excluded.</li>
          <li>On Mars, cells without MOLA observations hold interpolated values that cannot yet be identified.</li>
          <li>Mars and Earth heights use different references (areoid vs EGM96 geoid), so absolute elevations are never compared.</li>
        </ul>
      </div>
      <button className="primary" onClick={onStart}>Start an analysis</button>
    </section>
  );
}
