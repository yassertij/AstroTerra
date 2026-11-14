// Photo location (EXIF GPS) and device location. Everything stays on the device and
// in memory for this session only. Nothing here sends data anywhere.
import exifr from "exifr";
import { Capacitor } from "@capacitor/core";
import { Geolocation } from "@capacitor/geolocation";

export type Position = {
  source: "photo" | "device";
  lat: number;
  lon: number;
  accuracyM: number | null; // null = accuracy not reported
};

export type ExifOutcome =
  | { kind: "gps"; position: Position }
  | { kind: "no_gps" }
  | { kind: "unreadable"; reason: string };

/** Read GPS from image EXIF. Image metadata is parsed as data only. */
export async function readPhotoLocation(file: Blob): Promise<ExifOutcome> {
  let tags: Record<string, unknown> | undefined;
  try {
    // Do not use `pick` here: it drops the raw GPS tags that exifr needs to compute latitude/longitude.
    tags = await exifr.parse(file, { gps: true, exif: false, iptc: false, xmp: false, icc: false, jfif: false, ihdr: false });
  } catch (e) {
    return { kind: "unreadable", reason: "The photo's metadata could not be read." };
  }
  const lat = tags?.latitude;
  const lon = tags?.longitude;
  if (typeof lat !== "number" || typeof lon !== "number" || !Number.isFinite(lat) || !Number.isFinite(lon)) {
    return { kind: "no_gps" };
  }
  if (Math.abs(lat) > 90 || Math.abs(lon) > 180) return { kind: "unreadable", reason: "The photo's GPS values are out of range." };
  const err = tags?.GPSHPositioningError;
  return {
    kind: "gps",
    position: { source: "photo", lat, lon, accuracyM: typeof err === "number" && err >= 0 ? err : null },
  };
}

export type DeviceOutcome =
  | { kind: "ok"; position: Position }
  | { kind: "denied" }
  | { kind: "unavailable"; reason: string };

/** Ask for device location through the native permission prompt (only when the user taps). */
export async function getDeviceLocation(): Promise<DeviceOutcome> {
  try {
    if (Capacitor.isNativePlatform()) {
      const perm = await Geolocation.requestPermissions({ permissions: ["coarseLocation"] });
      if (perm.coarseLocation === "denied" && perm.location === "denied") return { kind: "denied" };
    }
    const p = await Geolocation.getCurrentPosition({ enableHighAccuracy: false, timeout: 15000 });
    return {
      kind: "ok",
      position: { source: "device", lat: p.coords.latitude, lon: p.coords.longitude, accuracyM: p.coords.accuracy ?? null },
    };
  } catch (e) {
    const msg = String((e as Error)?.message ?? e);
    if (/denied|permission/i.test(msg)) return { kind: "denied" };
    return { kind: "unavailable", reason: "Device location is unavailable right now." };
  }
}
