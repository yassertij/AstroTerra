// SRTM GL1 coverage check, done ON THE DEVICE so coordinates never leave it.
export const SRTM_NORTH = 60;
export const SRTM_SOUTH = -56;

export type Coverage = { status: "inside" | "outside_coverage" | "invalid"; tile: string | null };

export function srtmTileName(lat: number, lon: number): string {
  const la = Math.floor(lat);
  const lo = Math.floor(lon);
  const ns = la >= 0 ? "N" : "S";
  const ew = lo >= 0 ? "E" : "W";
  return `${ns}${String(Math.abs(la)).padStart(2, "0")}${ew}${String(Math.abs(lo)).padStart(3, "0")}`;
}

export function checkCoverage(lat: number, lon: number): Coverage {
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    return { status: "invalid", tile: null };
  }
  if (lat > SRTM_NORTH || lat < SRTM_SOUTH) return { status: "outside_coverage", tile: null };
  return { status: "inside", tile: srtmTileName(lat, lon) };
}

/** Round to 0.01 degree (about 1 km), used only if the user opts in to sharing coordinates. */
export function roundCoord(x: number): number {
  return Math.round(x * 100) / 100;
}
