import type { CapacitorConfig } from "@capacitor/cli";

// appId is a placeholder: choose the real reverse-DNS id before any store submission.
const config: CapacitorConfig = {
  appId: "dev.paf.planetaryanalog",
  appName: "Planetary Analog Finder",
  webDir: "dist",
  backgroundColor: "#040607",
  server: {
    // The MVP backend is plain HTTP on the local network (e.g. http://192.168.1.20:8765).
    // An https:// app origin would block those requests as mixed content, so the app is
    // served as http://localhost and cleartext traffic is allowed. Revisit when the
    // backend gets TLS (see docs/roadmap.md, "Hosting decision").
    androidScheme: "http",
    cleartext: true,
  },
};

export default config;
