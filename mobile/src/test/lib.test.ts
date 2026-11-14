import { describe, expect, it, vi, beforeEach } from "vitest";
import { AA, contrastRatio } from "../lib/contrast";
import { AVOIDED_PAIRS, PALETTE, USED_PAIRS, auroraAt } from "../lib/palette";
import { checkCoverage, roundCoord, srtmTileName } from "../lib/coverage";
import { explain } from "../lib/labels";
import { jpegWithGps, jpegWithoutExif, malformedJpeg } from "./jpeg";

vi.mock("@capacitor/geolocation", () => ({
  Geolocation: { getCurrentPosition: vi.fn(), requestPermissions: vi.fn() },
}));
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: vi.fn(() => false) } }));

import { Geolocation } from "@capacitor/geolocation";
import { Capacitor } from "@capacitor/core";
import { getDeviceLocation, readPhotoLocation } from "../lib/photo";

describe("palette contrast (WCAG AA)", () => {
  it("every pair used in the UI passes", () => {
    for (const p of USED_PAIRS) {
      const r = contrastRatio(p.fg, p.bg);
      expect(r, `${p.use}: ${p.fg} on ${p.bg} = ${r.toFixed(2)}`).toBeGreaterThanOrEqual(AA[p.kind]);
    }
  });
  it("documents the pairs avoided because they fail", () => {
    for (const p of AVOIDED_PAIRS) expect(contrastRatio(p.fg, p.bg)).toBeLessThan(AA[p.kind]);
  });
  it("Aurora button label keeps 4.5:1 where text sits (15 %–85 % of the width)", () => {
    for (let p = 0.15; p <= 0.85001; p += 0.05) {
      const bg = auroraAt(p);
      expect(contrastRatio(PALETTE.text, bg), `at ${p.toFixed(2)} on ${bg}`).toBeGreaterThanOrEqual(4.5);
    }
  });
  it("matches known reference values", () => {
    expect(contrastRatio("#000000", "#FFFFFF")).toBeCloseTo(21, 5);
    expect(contrastRatio(PALETTE.text, PALETTE.base)).toBeGreaterThan(15);
  });
});

describe("SRTM coverage on device", () => {
  it.each([
    [38.4, -110.8, "inside", "N38W111"], [60, 10, "inside", "N60E010"], [-56, -68.5, "inside", "S56W069"],
    [-0.5, 0.5, "inside", "S01E000"], [75.4, -89.8, "outside_coverage", null], [-56.01, -68, "outside_coverage", null],
    [NaN, 0, "invalid", null], [91, 0, "invalid", null],
  ])("%s, %s -> %s", (lat, lon, status, tile) => {
    expect(checkCoverage(lat as number, lon as number)).toEqual({ status, tile });
  });
  it("names tiles and rounds to ~1 km", () => {
    expect(srtmTileName(-33.9, 18.4)).toBe("S34E018");
    expect(roundCoord(38.45678)).toBe(38.46);
  });
});

describe("photo EXIF location", () => {
  it("reads GPS and accuracy", async () => {
    const out = await readPhotoLocation(jpegWithGps(38.4321, -110.7654, 12.5));
    expect(out.kind).toBe("gps");
    if (out.kind === "gps") {
      expect(out.position.source).toBe("photo");
      expect(out.position.lat).toBeCloseTo(38.4321, 3);
      expect(out.position.lon).toBeCloseTo(-110.7654, 3);
      expect(out.position.accuracyM).toBeCloseTo(12.5, 1);
    }
  });
  it("handles a photo without GPS", async () => {
    expect((await readPhotoLocation(jpegWithoutExif())).kind).toBe("no_gps");
  });
  it("handles malformed metadata without throwing", async () => {
    const out = await readPhotoLocation(malformedJpeg());
    expect(["no_gps", "unreadable"]).toContain(out.kind);
  });
  it("handles non-image bytes", async () => {
    const out = await readPhotoLocation(new Blob(["not an image"]));
    expect(["no_gps", "unreadable"]).toContain(out.kind);
  });
});

describe("device location permission", () => {
  beforeEach(() => vi.mocked(Capacitor.isNativePlatform).mockReturnValue(true));
  it("granted", async () => {
    vi.mocked(Geolocation.requestPermissions).mockResolvedValue({ location: "granted", coarseLocation: "granted" });
    vi.mocked(Geolocation.getCurrentPosition).mockResolvedValue({ timestamp: 0, coords: { latitude: 1, longitude: 2, accuracy: 30 } } as never);
    const out = await getDeviceLocation();
    expect(out).toEqual({ kind: "ok", position: { source: "device", lat: 1, lon: 2, accuracyM: 30 } });
  });
  it("declined", async () => {
    vi.mocked(Geolocation.requestPermissions).mockResolvedValue({ location: "denied", coarseLocation: "denied" });
    expect((await getDeviceLocation()).kind).toBe("denied");
    expect(Geolocation.getCurrentPosition).not.toHaveBeenCalledTimes(2);
  });
  it("declined via error on web", async () => {
    vi.mocked(Capacitor.isNativePlatform).mockReturnValue(false);
    vi.mocked(Geolocation.getCurrentPosition).mockRejectedValue(new Error("User denied Geolocation"));
    expect((await getDeviceLocation()).kind).toBe("denied");
  });
});

describe("score explanation", () => {
  it("names the top contributors with direction and units", () => {
    const s = explain({ relief_20km_m: 0.66, slope_median_deg: 0.1, roughness_5km_m: 0.24 },
      { relief_20km_m: 2607.7, slope_median_deg: 0.6, roughness_5km_m: -25.3 });
    expect(s).toContain("local relief, 20 km windows (66 %");
    expect(s).toContain("higher on the Mars target by 2607.7 m");
    expect(s).toContain("lower on the Mars target by 25.3 m");
  });
});
