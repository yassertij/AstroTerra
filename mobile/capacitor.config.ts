import type { CapacitorConfig } from "@capacitor/cli";

// appId is a placeholder: choose the real reverse-DNS id before any store submission.
//
// Two modes, chosen when running `npx cap sync` (the config is copied into the native
// project at sync time):
//   development (default): the app is served as http://localhost so it can call a plain-HTTP
//     backend on the local network (e.g. http://192.168.1.20:8765 or http://10.0.2.2:8765).
//   release (PAF_RELEASE=1): the app is served as https://localhost and cleartext is off; the
//     API must be https:// (set VITE_PAF_API_BASE when building the web app). The Android
//     release build type also disables cleartext traffic (android/app/build.gradle).
const release = process.env.PAF_RELEASE === "1";

const config: CapacitorConfig = {
  appId: "dev.paf.planetaryanalog",
  appName: "AstroTerra",
  webDir: "dist",
  backgroundColor: "#040607",
  server: release
    ? { androidScheme: "https", cleartext: false }
    : { androidScheme: "http", cleartext: true },
};

export default config;
