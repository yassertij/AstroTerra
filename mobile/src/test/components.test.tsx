import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { jpegWithGps, jpegWithoutExif } from "./jpeg";

vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => false } }));
vi.mock("@capacitor/camera", () => ({ Camera: {}, CameraResultType: {}, CameraSource: {} }));
vi.mock("@capacitor/geolocation", () => ({ Geolocation: { getCurrentPosition: vi.fn(), requestPermissions: vi.fn() } }));

import { PhotoPanel, emptyPhotoState, type PhotoState } from "../components/PhotoPanel";
import { Results } from "../components/Results";
import { JobStatus } from "../components/JobStatus";
import { useJob } from "../lib/useJob";
import { RESULT } from "./fixtures";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  URL.createObjectURL = vi.fn(() => "blob:photo");
  URL.revokeObjectURL = vi.fn();
  localStorage.clear();
});

function ok(body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
}

function PhotoHarness({ onUseTile = () => {} }: { onUseTile?: (t: string) => void }) {
  const [s, setS] = useState<PhotoState>(emptyPhotoState);
  return <PhotoPanel state={s} setState={setS} result={null} onUseTile={onUseTile} />;
}

async function importPhoto(blob: Blob) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File([blob], "field.jpg", { type: "image/jpeg" });
  await act(async () => { fireEvent.change(input, { target: { files: [file] } }); });
}

describe("PhotoPanel", () => {
  it("inside coverage offers the tile and never sends coordinates", async () => {
    fetchMock.mockImplementation(() => ok({ synthetic_data: false, mars_megdr: [], earth_srtm: [{ tile: "N38W111", num_file: true }] }));
    const used: string[] = [];
    render(<PhotoHarness onUseTile={(t) => used.push(t)} />);
    await importPhoto(jpegWithGps(38.4321, -110.7654, 8));
    await screen.findByText(/Photo position \(from the photo's EXIF\)/);
    expect(screen.getByText(/about 8 m/)).toBeTruthy();
    fireEvent.click(screen.getByText("Add N38W111 to Earth candidates"));
    expect(used).toEqual(["N38W111"]);
    for (const call of fetchMock.mock.calls) {
      const text = JSON.stringify(call);
      expect(text).not.toMatch(/38\.43|110\.76/);
    }
  });

  it("outside coverage is reported and no analysis is offered", async () => {
    fetchMock.mockImplementation(() => ok({ synthetic_data: false, mars_megdr: [], earth_srtm: [] }));
    render(<PhotoHarness />);
    await importPhoto(jpegWithGps(75.4, -89.8));
    await screen.findByText(/Outside coverage\./);
    expect(screen.queryByText(/Add .* to Earth candidates/)).toBeNull();
  });

  it("photo without GPS explains why and offers device location", async () => {
    fetchMock.mockImplementation(() => ok({ synthetic_data: false, mars_megdr: [], earth_srtm: [] }));
    render(<PhotoHarness />);
    await importPhoto(jpegWithoutExif());
    await screen.findByText(/has no GPS location/);
    expect(screen.getByText("Use device location")).toBeTruthy();
  });
});

describe("Results", () => {
  it("shows synthetic label, explanation, exclusions, coverage, provenance and private-by-default exports", async () => {
    localStorage.setItem("paf.currentJob", "job123");
    fetchMock.mockImplementation((url: string) =>
      url.endsWith("/result") ? ok(RESULT) : ok({ id: "job123", status: "succeeded", progress: 1, message: "Done", error: null, created: "", updated: "" }));
    function H() { const jobs = useJob(10); return <Results jobs={jobs} photo={emptyPhotoState} />; }
    render(<H />);
    await screen.findByText(/#1 — N38W111_r154_c88/);
    expect(screen.getAllByText(/Synthetic demo data/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/driven mostly by local relief, 20 km windows \(66 %/)).toBeTruthy();
    expect(screen.getByText(/non-SRTM fill fraction 0.200 > 0.05/)).toBeTruthy();
    expect(screen.getByText(/Outside SRTM coverage: N75W090/)).toBeTruthy();
    expect(screen.getByText(/MGS-M-MOLA-5-MEGDR-L3-V1.0 v2.0/)).toBeTruthy();
    const json = screen.getByText("Download JSON") as HTMLAnchorElement;
    expect(json.href).toContain("include_coordinates=false");
    fireEvent.click(screen.getByLabelText(/Include region coordinates/));
    expect((screen.getByText("Download CSV") as HTMLAnchorElement).href).toContain("include_coordinates=true");
  });
});

describe("JobStatus recovery", () => {
  it("shows connection loss, keeps the job, and recovers", async () => {
    localStorage.setItem("paf.currentJob", "jobX");
    let n = 0;
    fetchMock.mockImplementation(() => {
      n += 1;
      if (n <= 2) return Promise.reject(new TypeError("Failed to fetch"));
      return ok({ id: "jobX", status: "running", progress: 0.5, message: "Tile 1/1", error: null, created: "", updated: "" });
    });
    function H() { const jobs = useJob(5); return <JobStatus jobs={jobs} />; }
    render(<H />);
    await screen.findByText(/Connection lost\./);
    await waitFor(() => expect(screen.getByText(/Tile 1\/1/)).toBeTruthy(), { timeout: 3000 });
    expect(screen.queryByText(/Connection lost\./)).toBeNull();
    expect(localStorage.getItem("paf.currentJob")).toBe("jobX");
    expect(screen.getByText("Cancel analysis")).toBeTruthy();
  });
});
