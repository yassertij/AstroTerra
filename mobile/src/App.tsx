import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { api, type Datasets } from "./lib/api";
import { useJob } from "./lib/useJob";
import { Icon } from "./components/ui/Icon";
import { Overview } from "./components/Overview";
import { Analyse } from "./components/Analyse";
// The map library is only needed on the Earth page: load it on demand.
const EarthPage = lazy(() => import("./components/EarthPage").then((m) => ({ default: m.EarthPage })));
import { MoonPage } from "./components/MoonPage";
import { MarsPage } from "./components/MarsPage";
import { ComparePage } from "./components/ComparePage";
import { MethodPage } from "./components/MethodPage";
import { emptyPhotoState, type PhotoState } from "./components/PhotoPanel";
import { Settings } from "./components/Settings";

export const ROUTES = [
  { id: "overview", label: "Overview", long: "", icon: "overview" },
  { id: "earth", label: "Earth", long: " Locations", icon: "earth" },
  { id: "moon", label: "Moon", long: " Analogues", icon: "moon" },
  { id: "mars", label: "Mars", long: " Analogues", icon: "mars" },
  { id: "compare", label: "Compare", long: "", icon: "compare" },
  { id: "analysis", label: "Analysis", long: "", icon: "analysis" },
  { id: "method", label: "Method", long: "ology", icon: "method" },
  { id: "settings", label: "Settings", long: "", icon: "settings" },
] as const;
export type Route = (typeof ROUTES)[number]["id"];

function readRoute(): Route {
  const id = window.location.hash.replace(/^#\/?/, "");
  return (ROUTES.find((r) => r.id === id)?.id ?? "overview") as Route;
}

export default function App() {
  const [route, setRoute] = useState<Route>(readRoute);
  const [synthetic, setSynthetic] = useState<boolean | null>(null);
  const [datasets, setDatasets] = useState<Datasets | null>(null);
  const [dsError, setDsError] = useState<string | null>(null);
  const [readable, setReadable] = useState(false);
  const [extraTiles, setExtraTiles] = useState<string[]>([]);
  const [photo, setPhoto] = useState<PhotoState>(emptyPhotoState);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const jobs = useJob();

  useEffect(() => {
    const onHash = () => { setRoute(readRoute()); window.scrollTo({ top: 0 }); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    // On narrow screens the nav scrolls sideways: keep the active link visible.
    document.querySelector<HTMLElement>('.navlink[aria-current="page"]')?.scrollIntoView?.({ inline: "center", block: "nearest" });
  }, [route]);

  const loadDatasets = useCallback(() => {
    setDsError(null);
    api.health().then((h) => setSynthetic(h.synthetic_data)).catch(() => setSynthetic(null));
    api.datasets().then(setDatasets).catch((e) => setDsError(e.message));
  }, []);
  // Refresh the server dataset list on every page change (one small request), so data added on
  // the server after the app started (e.g. a newly downloaded LOLA product) is not missed.
  useEffect(() => {
    loadDatasets();
  }, [route, loadDatasets]);

  const go = (r: Route) => { window.location.hash = `/${r}`; };
  const useTile = (t: string) => setExtraTiles((xs) => (xs.includes(t) ? xs : [...xs, t]));

  return (
    <div className={readable ? "readable" : undefined}>
      <div className="aurora" aria-hidden="true">
        <span className="a-blue" /><span className="a-magenta" /><span className="a-velvet" /><span className="a-peri" />
      </div>
      <div className="app-shell">
        <a href="#main" className="sr-only">Skip to content</a>
        <nav className="topnav" aria-label="Main">
          <a className="brand" href="#/overview"><span className="brand-mark" aria-hidden="true" />Planetary Analog Finder</a>
          <div className="navlist">
            {ROUTES.map((r) => (
              <a key={r.id} className="navlink" href={`#/${r.id}`} aria-current={route === r.id ? "page" : undefined}>
                <Icon name={r.icon} />{r.label}<span className="label-long">{r.long}</span>
              </a>
            ))}
          </div>
        </nav>
        {synthetic && (
          <div className="banner" role="alert" style={{ maxWidth: 1180, margin: "12px auto" }}>
            <strong>Synthetic demo data.</strong> The server is using test data. No result shown is a real finding.
          </div>
        )}
        <main id="main" key={route} className="fade-in">
          {route === "overview" && <Overview go={go} datasets={datasets} result={jobs.result} />}
          {route === "earth" && (
            <Suspense fallback={<p role="status"><span className="spinner" aria-hidden="true" /> Loading the map…</p>}>
              <EarthPage datasets={datasets} dsError={dsError} onRetry={loadDatasets} result={jobs.result}
                photo={photo} setPhoto={setPhoto} onUseTile={useTile} go={go}
                compareIds={compareIds} setCompareIds={setCompareIds} />
            </Suspense>
          )}
          {route === "moon" && <MoonPage datasets={datasets} go={go} jobs={jobs} photo={photo} />}
          {route === "mars" && <MarsPage jobs={jobs} photo={photo} datasets={datasets} go={go} />}
          {route === "compare" && <ComparePage result={jobs.result} selected={compareIds} setSelected={setCompareIds} go={go} />}
          {route === "analysis" && <Analyse jobs={jobs} extraTiles={extraTiles} onShowResults={() => go(jobs.result?.target.body === "MOON" ? "moon" : "mars")} />}
          {route === "method" && <MethodPage />}
          {route === "settings" && (
            <Settings readable={readable} setReadable={setReadable} onDeleteLocalData={() => {
              if (photo.photoUrl) URL.revokeObjectURL(photo.photoUrl);
              setPhoto(emptyPhotoState);
              setExtraTiles([]);
            }} />
          )}
        </main>
      </div>
    </div>
  );
}
