// Builds minimal SYNTHETIC JPEG byte streams with (or without) EXIF GPS tags for tests.

function rational(deg: number): number[] {
  const d = Math.floor(deg);
  const mFull = (deg - d) * 60;
  const m = Math.floor(mFull);
  const s = Math.round((mFull - m) * 60 * 1000);
  return [d, 1, m, 1, s, 1000];
}

/** Big-endian TIFF/EXIF block with IFD0 -> GPS IFD. */
function exifSegment(lat: number, lon: number, hErr?: number): Uint8Array<ArrayBuffer> {
  const entries: { tag: number; type: number; count: number; value: number[] | string }[] = [
    { tag: 0x0001, type: 2, count: 2, value: lat >= 0 ? "N" : "S" },
    { tag: 0x0002, type: 5, count: 3, value: rational(Math.abs(lat)) },
    { tag: 0x0003, type: 2, count: 2, value: lon >= 0 ? "E" : "W" },
    { tag: 0x0004, type: 5, count: 3, value: rational(Math.abs(lon)) },
  ];
  if (hErr !== undefined) entries.push({ tag: 0x001f, type: 5, count: 1, value: [Math.round(hErr * 10), 10] });

  const tiff: number[] = [];
  const u16 = (v: number) => tiff.push((v >> 8) & 255, v & 255);
  const u32 = (v: number) => tiff.push((v >>> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255);
  // Header
  tiff.push(0x4d, 0x4d); u16(42); u32(8);
  // IFD0 at 8: one entry (GPS pointer), next IFD = 0
  const gpsOffset = 8 + 2 + 12 + 4;
  u16(1); u16(0x8825); u16(4); u32(1); u32(gpsOffset); u32(0);
  // GPS IFD
  const n = entries.length;
  let dataOffset = gpsOffset + 2 + n * 12 + 4;
  const data: number[] = [];
  u16(n);
  for (const e of entries) {
    u16(e.tag); u16(e.type); u32(e.count);
    if (typeof e.value === "string") {
      tiff.push(e.value.charCodeAt(0), 0, 0, 0);
    } else {
      u32(dataOffset);
      for (const x of e.value) {
        data.push((x >>> 24) & 255, (x >> 16) & 255, (x >> 8) & 255, x & 255);
      }
      dataOffset += e.value.length * 4;
    }
  }
  u32(0);
  tiff.push(...data);
  const payload = [0x45, 0x78, 0x69, 0x66, 0, 0, ...tiff]; // "Exif\0\0"
  const len = payload.length + 2;
  return new Uint8Array([0xff, 0xe1, (len >> 8) & 255, len & 255, ...payload]);
}

export function jpegWithGps(lat: number, lon: number, hErr?: number): Blob {
  const seg = exifSegment(lat, lon, hErr);
  return new Blob([new Uint8Array([0xff, 0xd8]), seg, new Uint8Array([0xff, 0xd9])], { type: "image/jpeg" });
}

export function jpegWithoutExif(): Blob {
  return new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], { type: "image/jpeg" });
}

export function malformedJpeg(): Blob {
  // Exif marker with a length pointing far beyond the data.
  return new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe1, 0xff, 0xf0, 0x45, 0x78, 0x69, 0x66, 0, 0, 0x4d, 0x4d, 0, 42])], { type: "image/jpeg" });
}
