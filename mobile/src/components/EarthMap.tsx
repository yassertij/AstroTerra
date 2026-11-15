// Interactive Earth map. Basemap: NASA GIBS Blue Marble (NASA-distributed imagery).
// Only data the app really has is drawn: SRTM coverage limits, tiles on the server,
// and candidate patches from the latest analysis. Photo/device positions are never
// shown here, so no map-tile request ever reveals the user's location.
import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { CandidateResult } from "../lib/api";
import { SRTM_NORTH, SRTM_SOUTH } from "../lib/coverage";

const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg";

export type MapTile = { tile: string; lat: number; lon: number };

export function tileBounds(name: string): MapTile | null {
  const m = /^([NS])(\d{2})([EW])(\d{3})$/.exec(name);
  if (!m) return null;
  return { tile: name, lat: (m[1] === "N" ? 1 : -1) * Number(m[2]), lon: (m[3] === "E" ? 1 : -1) * Number(m[4]) };
}

export function EarthMap({ tiles, candidates, selected, onSelect }: {
  tiles: MapTile[]; candidates: CandidateResult[]; selected: string | null; onSelect: (id: string) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const [tileError, setTileError] = useState(false);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { center: [25, -20], zoom: 2, minZoom: 1, maxZoom: 8, worldCopyJump: true, attributionControl: true });
    L.tileLayer(GIBS, {
      maxNativeZoom: 8, maxZoom: 8, noWrap: false,
      attribution: 'Imagery: <a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noreferrer">NASA GIBS</a> Blue Marble',
    }).on("tileerror", () => setTileError(true)).on("tileload", () => setTileError(false)).addTo(m);
    const shade = { color: "#5B2A62", weight: 1, fillColor: "#040607", fillOpacity: 0.55, interactive: true };
    L.rectangle([[SRTM_NORTH, -540], [85, 540]], shade).bindTooltip("Outside SRTM coverage (north of 60° N)").addTo(m);
    L.rectangle([[-85, -540], [SRTM_SOUTH, 540]], shade).bindTooltip("Outside SRTM coverage (south of 56° S)").addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current, g = layer.current;
    if (!m || !g) return;
    g.clearLayers();
    const all = L.latLngBounds([]);
    for (const t of tiles) {
      const b: L.LatLngBoundsLiteral = [[t.lat, t.lon], [t.lat + 1, t.lon + 1]];
      L.rectangle(b, { color: "#4928C2", weight: 2, fillOpacity: 0.08, dashArray: "4 4" })
        .bindTooltip(`SRTM tile ${t.tile} (downloaded)`).addTo(g);
      all.extend(b);
    }
    for (const c of candidates) {
      if (!c.region) continue;
      const r = c.region;
      const b: L.LatLngBoundsLiteral = [[r.lat_min, r.lon_min], [r.lat_max, r.lon_max]];
      const isSel = c.candidate_id === selected;
      const top = c.rank != null && c.rank <= 3;
      L.rectangle(b, {
        color: isSel ? "#E3D9FC" : top ? "#BF40FA" : "#E3D9FC",
        weight: isSel ? 3 : top ? 2 : 1,
        opacity: isSel ? 1 : top ? 0.95 : 0.45,
        fillColor: top ? "#BF40FA" : "#4928C2",
        fillOpacity: isSel ? 0.35 : top ? 0.18 : 0.06,
        dashArray: c.excluded ? "3 5" : undefined,
      })
        .bindTooltip(c.excluded ? `${c.candidate_id} — excluded` : `#${c.rank} ${c.candidate_id} · distance ${c.distance?.toFixed(2)}`)
        .on("click", () => onSelect(c.candidate_id))
        .addTo(g);
      if (isSel) m.flyToBounds(b, { maxZoom: 8, duration: 0.6, padding: [40, 40] });
      all.extend(b);
    }
    if (!selected && all.isValid()) m.fitBounds(all.pad(0.4), { maxZoom: 7 });
  }, [tiles, candidates, selected, onSelect]);

  return (
    <div>
      <div ref={el} className="map" role="region" aria-label="Map of SRTM coverage, downloaded tiles and candidate patches" />
      <p className="hint">
        Legend: shaded bands = outside SRTM coverage · dashed blue = SRTM tile on the server · magenta = top-3 candidates ·
        light outline = other candidates · dotted = excluded. Click a patch for details.
      </p>
      <p className="hint">
        The background is NASA GIBS Blue Marble <strong>imagery for orientation only</strong>; no value in the analysis comes from it.
        All elevations and terrain metrics come from SRTM GL1 v3 tiles processed on the server.
      </p>
      {tileError && <p role="status" className="hint"><strong>Basemap unavailable</strong> (offline or NASA GIBS unreachable). Tiles and candidates are still drawn.</p>}
    </div>
  );
}
