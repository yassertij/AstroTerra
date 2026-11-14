import { useState } from "react";
import { getApiBase, setApiBase } from "../lib/api";

export function Settings({ readable, setReadable, onDeleteLocalData }: {
  readable: boolean; setReadable: (v: boolean) => void; onDeleteLocalData: () => void;
}) {
  const [url, setUrl] = useState(getApiBase());
  const [saved, setSaved] = useState(false);
  const [deleted, setDeleted] = useState(false);
  return (
    <section aria-labelledby="set-h">
      <h2 id="set-h">Settings</h2>
      <div className="card">
        <label htmlFor="api">Analysis server address</label>
        <input id="api" type="url" value={url} onChange={(e) => { setUrl(e.target.value); setSaved(false); }} />
        <p className="hint">Android emulator: http://10.0.2.2:8765 · same computer: http://127.0.0.1:8765</p>
        <button onClick={() => { setApiBase(url); setSaved(true); }}>Save address</button>
        {saved && <span role="status"> Saved.</span>}
      </div>
      <div className="card">
        <label className="check">
          <input type="checkbox" checked={readable} onChange={(e) => setReadable(e.target.checked)} />
          Larger, more readable text
        </label>
      </div>
      <div className="card">
        <h3>Privacy</h3>
        <p>Photos and locations are kept in memory for this session only and never leave the device.</p>
        <button onClick={() => { onDeleteLocalData(); setDeleted(true); }}>Delete all photos and location data</button>
        {deleted && <p role="status">All photos and location data were deleted.</p>}
      </div>
    </section>
  );
}
