import { useState } from "react";
import { apiBaseProblem, checkServer, getApiBase, setApiBase, type ServerCheck } from "../lib/api";

export function Settings({ readable, setReadable, onDeleteLocalData }: {
  readable: boolean; setReadable: (v: boolean) => void; onDeleteLocalData: () => void;
}) {
  const [url, setUrl] = useState(getApiBase());
  const [saved, setSaved] = useState(false);
  const problem = url ? apiBaseProblem(url.trim()) : null;
  const [deleted, setDeleted] = useState(false);
  const [testing, setTesting] = useState(false);
  const [check, setCheck] = useState<ServerCheck | null>(null);
  const test = async () => {
    setTesting(true);
    setCheck(null);
    setCheck(await checkServer(url));
    setTesting(false);
  };
  return (
    <section aria-labelledby="set-h">
      <h2 id="set-h">Settings</h2>
      <div className="card">
        <label htmlFor="api">Analysis server address</label>
        <input id="api" type="url" inputMode="url" autoCapitalize="off" autoCorrect="off" value={url}
          onChange={(e) => { setUrl(e.target.value); setSaved(false); setCheck(null); }} />
        <ul className="hint">
          <li>Phone on the same Wi-Fi as the computer: http://&lt;computer's Wi-Fi IP&gt;:8765 (server started with --host 0.0.0.0)</li>
          <li>Phone on a USB cable: http://127.0.0.1:8765 after <code>adb reverse tcp:8765 tcp:8765</code></li>
          <li>Android emulator: http://10.0.2.2:8765 · hosted server: https://…</li>
        </ul>
        {problem && <p role="status" className="hint"><strong>Cannot use this address:</strong> {problem}</p>}
        <div className="row">
          <button disabled={!!problem || testing} onClick={test} aria-busy={testing || undefined}>{testing ? "Testing…" : "Test connection"}</button>
          <button disabled={!!problem} onClick={() => { setApiBase(url); setSaved(true); }}>Save address</button>
        </div>
        {saved && <p role="status">Saved. Open any page to reload data from this server.</p>}
        {check?.ok && <p role="status"><strong>Connected.</strong> Server version {check.version}{check.synthetic ? " — using SYNTHETIC test data" : ""}.</p>}
        {check && !check.ok && <p role="alert"><strong>Connection failed.</strong> {check.message}</p>}
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
