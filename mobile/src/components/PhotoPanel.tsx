import { useEffect, useState } from "react";
import { Capacitor } from "@capacitor/core";
import { Camera, CameraResultType, CameraSource } from "@capacitor/camera";
import { api, type AnalysisResult } from "../lib/api";
import { checkCoverage } from "../lib/coverage";
import { getDeviceLocation, readPhotoLocation, type Position } from "../lib/photo";

export type PhotoState = {
  photoUrl: string | null;
  photoPosition: Position | null;
  devicePosition: Position | null;
  note: string | null;
  attachedTo: string | null;
};
export const emptyPhotoState: PhotoState = { photoUrl: null, photoPosition: null, devicePosition: null, note: null, attachedTo: null };

function PositionView({ p, title }: { p: Position; title: string }) {
  const cov = checkCoverage(p.lat, p.lon);
  return (
    <div className="card">
      <h3>{title}</h3>
      <p>
        {p.lat.toFixed(4)}°, {p.lon.toFixed(4)}° — accuracy radius:{" "}
        {p.accuracyM == null ? "not reported" : `about ${Math.round(p.accuracyM)} m`}
      </p>
      {cov.status === "outside_coverage" && (
        <p role="status"><strong>Outside coverage.</strong> SRTM covers 60° N to 56° S only; no analysis is offered for this position.</p>
      )}
      {cov.status === "inside" && <p>Inside SRTM coverage — tile <strong>{cov.tile}</strong>.</p>}
    </div>
  );
}

export function PhotoPanel({ state, setState, result, onUseTile }: {
  state: PhotoState;
  setState: (f: (s: PhotoState) => PhotoState) => void;
  result: AnalysisResult | null;
  onUseTile: (tile: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [serverTiles, setServerTiles] = useState<string[] | null>(null);

  // Ask the server which tiles it has (no coordinates are sent).
  useEffect(() => {
    api.datasets().then((d) => setServerTiles(d.earth_srtm.map((t) => t.tile))).catch(() => setServerTiles(null));
  }, []);

  const handleBlob = async (blob: Blob) => {
    setBusy(true);
    const url = URL.createObjectURL(blob);
    const exif = await readPhotoLocation(blob);
    setState((s) => {
      if (s.photoUrl) URL.revokeObjectURL(s.photoUrl);
      return {
        ...s, photoUrl: url, attachedTo: null,
        photoPosition: exif.kind === "gps" ? exif.position : null,
        note: exif.kind === "gps" ? null
          : exif.kind === "no_gps" ? "This photo has no GPS location (often removed by privacy settings, social networks or screenshots). You can use the device location instead, or continue without a location."
          : `${exif.reason} You can use the device location instead, or continue without a location.`,
      };
    });
    setBusy(false);
  };

  const pickNative = async () => {
    try {
      const perm = await Camera.requestPermissions({ permissions: ["photos"] });
      if (perm.photos === "denied") {
        setState((s) => ({ ...s, note: "Photo access was declined. You can allow it later in system settings; the app works without photos." }));
        return;
      }
      const ph = await Camera.getPhoto({ source: CameraSource.Prompt, resultType: CameraResultType.Uri, quality: 90, correctOrientation: false });
      if (ph.webPath) await handleBlob(await (await fetch(ph.webPath)).blob());
    } catch {
      /* user closed the picker */
    }
  };

  const useDevice = async () => {
    setBusy(true);
    const out = await getDeviceLocation();
    setBusy(false);
    if (out.kind === "ok") setState((s) => ({ ...s, devicePosition: out.position }));
    else setState((s) => ({ ...s, note: out.kind === "denied"
      ? "Location access was declined. The app continues without a location."
      : out.reason }));
  };

  const positions = [state.photoPosition, state.devicePosition].filter(Boolean) as Position[];
  const tiles = Array.from(new Set(positions.map((p) => checkCoverage(p.lat, p.lon)).filter((c) => c.status === "inside").map((c) => c.tile!)));
  const ranked = result?.ranking.results.filter((r) => !r.excluded) ?? [];

  return (
    <section aria-labelledby="ph-h">
      <h2 id="ph-h">Field photo</h2>
      <p>
        A photo can (1) give an Earth location to pick a candidate tile and (2) be attached to a candidate as a
        <strong> photo observation</strong> — a visual reference, never a measurement. A location on Earth can only
        choose an Earth candidate; it never changes the Mars target. The photo position is where the picture was taken,
        not necessarily the area analysed.
      </p>
      <p className="hint">
        Privacy: the photo and its metadata are read on this device and kept in memory for this session only. They are
        never sent to any service; only a tile name (e.g. N38W111) is used. Delete everything from Settings at any time.
      </p>

      <div className="row">
        {Capacitor.isNativePlatform() ? (
          <button className="primary" onClick={pickNative} disabled={busy}>Import or take a photo</button>
        ) : (
          <label className="button primary" style={{ display: "inline-flex", alignItems: "center", margin: 0 }}>
            Import a photo
            <input type="file" accept="image/*" className="sr-only" onChange={(e) => e.target.files?.[0] && handleBlob(e.target.files[0])} />
          </label>
        )}
        <button onClick={useDevice} disabled={busy}>Use device location</button>
      </div>
      <p className="hint">Device location is requested only when you tap the button; the system asks for your permission.</p>

      {state.note && <p role="status">{state.note}</p>}
      {state.photoUrl && <img src={state.photoUrl} alt="Imported field photo" style={{ maxWidth: "100%", maxHeight: 280, borderRadius: 8, marginTop: 12 }} />}
      {state.photoPosition && <PositionView p={state.photoPosition} title="Photo position (from the photo's EXIF)" />}
      {state.devicePosition && <PositionView p={state.devicePosition} title="Device position (current location)" />}

      {tiles.map((t) => (
        <div key={t} className="row">
          <button onClick={() => onUseTile(t)}>Add {t} to Earth candidates</button>
          {serverTiles && !serverTiles.includes(t) && <span className="hint">Not downloaded on the server yet: it will be listed as unavailable.</span>}
        </div>
      ))}

      {state.photoUrl && ranked.length > 0 && (
        <div className="card">
          <label htmlFor="attach">Attach the photo as an observation to a candidate</label>
          <select id="attach" value={state.attachedTo ?? ""} onChange={(e) => setState((s) => ({ ...s, attachedTo: e.target.value || null }))}>
            <option value="">— none —</option>
            {ranked.map((r) => <option key={r.candidate_id} value={r.candidate_id}>#{r.rank} {r.candidate_id}</option>)}
          </select>
          <p className="hint">It appears next to that candidate on the Results tab, labelled "photo observation".</p>
        </div>
      )}
    </section>
  );
}
