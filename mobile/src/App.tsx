import { useEffect, useRef, useState } from "react";
import { api } from "./lib/api";
import { useJob } from "./lib/useJob";
import { Overview } from "./components/Overview";
import { Analyse } from "./components/Analyse";
import { Results } from "./components/Results";
import { PhotoPanel, emptyPhotoState, type PhotoState } from "./components/PhotoPanel";
import { Sources } from "./components/Sources";
import { Settings } from "./components/Settings";

const TABS = ["Overview", "Analyse", "Results", "Photo", "Sources", "Settings"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [tab, setTab] = useState<Tab>("Overview");
  const [synthetic, setSynthetic] = useState<boolean | null>(null);
  const [readable, setReadable] = useState(false);
  const [extraTiles, setExtraTiles] = useState<string[]>([]);
  const [photo, setPhoto] = useState<PhotoState>(emptyPhotoState);
  const jobs = useJob();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    api.health().then((h) => setSynthetic(h.synthetic_data)).catch(() => setSynthetic(null));
  }, []);

  const onKey = (e: React.KeyboardEvent, i: number) => {
    const n = e.key === "ArrowRight" ? (i + 1) % TABS.length : e.key === "ArrowLeft" ? (i - 1 + TABS.length) % TABS.length : -1;
    if (n >= 0) {
      setTab(TABS[n]);
      tabRefs.current[n]?.focus();
    }
  };

  return (
    <div className={readable ? "readable" : undefined}>
      <header className="app">
        <h1>Planetary Analog Finder</h1>
        <p>Topographic analog assessment only — not proof of geological or environmental equivalence.</p>
      </header>
      {synthetic && (
        <div className="banner" role="alert">
          <strong>Synthetic demo data.</strong> The server is using test data. No result shown is a real finding.
        </div>
      )}
      <nav role="tablist" aria-label="Sections">
        {TABS.map((t, i) => (
          <button
            key={t}
            role="tab"
            id={`tab-${t}`}
            aria-selected={tab === t}
            aria-controls={`panel-${t}`}
            tabIndex={tab === t ? 0 : -1}
            ref={(el) => { tabRefs.current[i] = el; }}
            onClick={() => setTab(t)}
            onKeyDown={(e) => onKey(e, i)}
          >
            {t}
          </button>
        ))}
      </nav>
      <main id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "Overview" && <Overview onStart={() => setTab("Analyse")} />}
        {tab === "Analyse" && (
          <Analyse jobs={jobs} extraTiles={extraTiles} onShowResults={() => setTab("Results")} />
        )}
        {tab === "Results" && <Results jobs={jobs} photo={photo} />}
        {tab === "Photo" && (
          <PhotoPanel
            state={photo}
            setState={setPhoto}
            result={jobs.result}
            onUseTile={(t) => setExtraTiles((xs) => (xs.includes(t) ? xs : [...xs, t]))}
          />
        )}
        {tab === "Sources" && <Sources />}
        {tab === "Settings" && (
          <Settings
            readable={readable}
            setReadable={setReadable}
            onDeleteLocalData={() => {
              photo.photoUrl && URL.revokeObjectURL(photo.photoUrl);
              setPhoto(emptyPhotoState);
              setExtraTiles([]);
            }}
          />
        )}
      </main>
    </div>
  );
}
