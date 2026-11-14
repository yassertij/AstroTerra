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
];

// Pairs deliberately NOT used because they fail; kept here so the test documents why.
export const AVOIDED_PAIRS: Pair[] = [
  { fg: PALETTE.action, bg: PALETTE.base, use: "button fill as its only boundary", kind: "ui" },
  { fg: PALETTE.accent, bg: PALETTE.action, use: "focus ring drawn on a button fill", kind: "ui" },
  { fg: PALETTE.accent, bg: PALETTE.surface, use: "links inside cards", kind: "text" },
];

// Sequential chart scale (low -> high), as specified by the owner.
export const SEQUENTIAL = [PALETTE.surface, PALETTE.action, PALETTE.accent, PALETTE.text];
