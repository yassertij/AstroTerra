// Small inline stroke icons (no icon dependency). Decorative: always aria-hidden.
const PATHS: Record<string, string> = {
  overview: "M3 12l9-8 9 8M5 10v10h14V10",
  earth: "M12 3a9 9 0 100 18 9 9 0 000-18zM3.6 9h16.8M3.6 15h16.8M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z",
  moon: "M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z",
  mars: "M12 3a9 9 0 100 18 9 9 0 000-18zM7 9.5c2 .5 3 1.8 3.5 3.5M14 7c.5 1.5 2 2.5 3.5 2.5M9 16.5c1.5-1 3.5-1 5 .5",
  compare: "M8 3v18M16 3v18M3 8h5M16 16h5M3 16h5M16 8h5",
  analysis: "M4 19V5M4 19h16M8 15l3-4 3 2 5-7",
  method: "M5 4h10l4 4v12H5zM15 4v4h4M8 12h8M8 16h6",
  settings: "M12 9a3 3 0 100 6 3 3 0 000-6zM19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-2.7 1.1V21a2 2 0 01-4 0v-.1A1.6 1.6 0 009 19.4a1.6 1.6 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.6 1.6 0 00-1.1-2.7H3a2 2 0 010-4h.1A1.6 1.6 0 004.6 9a1.6 1.6 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.6 1.6 0 001.8.3H9a1.6 1.6 0 001-1.5V3a2 2 0 014 0v.1a1.6 1.6 0 001 1.5 1.6 1.6 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 00-.3 1.8V9a1.6 1.6 0 001.5 1H21a2 2 0 010 4h-.1a1.6 1.6 0 00-1.5 1z",
  arrow: "M5 12h14M13 6l6 6-6 6",
  photo: "M4 7h3l2-2h6l2 2h3v12H4zM12 10a3.5 3.5 0 100 7 3.5 3.5 0 000-7z",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  search: "M11 4a7 7 0 100 14 7 7 0 000-14zM20 20l-4-4",
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18 }: { name: IconName | string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[name] ?? ""} />
    </svg>
  );
}
