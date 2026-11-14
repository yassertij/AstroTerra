// Owner-validated palette. Every text/background pair used in the UI is listed in
// USED_PAIRS and checked against WCAG AA in src/test/contrast.test.ts.
export const PALETTE = {
  base: "#040607", // background of every screen
  text: "#E3D9FC", // primary text and icons on dark surfaces
  surface: "#5B2A62", // headers, panels, cards, table headers
  action: "#4928C2", // buttons, active tabs, selected items (with #E3D9FC text only)
  accent: "#BF40FA", // focus rings, markers, highest chart value, links
} as const;

export type Pair = { fg: string; bg: string; use: string; kind: "text" | "large-text" | "ui" };

export const USED_PAIRS: Pair[] = [
  { fg: PALETTE.text, bg: PALETTE.base, use: "body text on screen background", kind: "text" },
  { fg: PALETTE.text, bg: PALETTE.surface, use: "text on cards / table headers", kind: "text" },
  { fg: PALETTE.text, bg: PALETTE.action, use: "button and active-tab labels", kind: "text" },
  { fg: PALETTE.accent, bg: PALETTE.base, use: "links on screen background", kind: "text" },
  { fg: PALETTE.accent, bg: PALETTE.base, use: "focus ring (drawn outside the control, on background)", kind: "ui" },
  { fg: PALETTE.text, bg: PALETTE.base, use: "button border (gives buttons a 3:1 boundary)", kind: "ui" },
  { fg: PALETTE.text, bg: PALETTE.base, use: "chart bar outline", kind: "ui" },
  { fg: PALETTE.base, bg: PALETTE.accent, use: "Hyper Magenta button label", kind: "text" },
  { fg: PALETTE.accent, bg: PALETTE.base, use: "map markers and selected candidate outline", kind: "ui" },
];

/** Aurora button: owner gradient (#4928C2 0 %, #BF40FA 65 %, #E3D9FC 130 %) under a black veil. */
export const AURORA = { veil: 0.4, stops: [[0, PALETTE.action], [0.65, PALETTE.accent], [1.3, PALETTE.text]] as const };

function mix(a: string, b: string, t: number): number[] {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  return pa.map((x, i) => x + (pb[i] - x) * t);
}
const hex = (c: number[]) => "#" + c.map((x) => Math.round(x).toString(16).padStart(2, "0")).join("");

/** Effective background colour of the Aurora button at a position 0..1 along its gradient. */
export function auroraAt(p: number): string {
  const [[p0, c0], [p1, c1], [p2, c2]] = AURORA.stops;
  const base = p <= p1 ? mix(c0, c1, (p - p0) / (p1 - p0)) : mix(c1, c2, (p - p1) / (p2 - p1));
  return hex(mix(hex(base), PALETTE.base, AURORA.veil));
}

// Pairs deliberately NOT used because they fail; kept here so the test documents why.
export const AVOIDED_PAIRS: Pair[] = [
  { fg: PALETTE.action, bg: PALETTE.base, use: "button fill as its only boundary", kind: "ui" },
  { fg: PALETTE.accent, bg: PALETTE.action, use: "focus ring drawn on a button fill", kind: "ui" },
  { fg: PALETTE.accent, bg: PALETTE.surface, use: "links inside cards", kind: "text" },
];

// Sequential chart scale (low -> high), as specified by the owner.
export const SEQUENTIAL = [PALETTE.surface, PALETTE.action, PALETTE.accent, PALETTE.text];
