import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => false } }));
vi.mock("@capacitor/camera", () => ({ Camera: {}, CameraResultType: {}, CameraSource: {} }));
vi.mock("@capacitor/geolocation", () => ({ Geolocation: { getCurrentPosition: vi.fn(), requestPermissions: vi.fn() } }));

import { api, apiBaseProblem, setApiBase, withRetry, ApiError } from "../lib/api";
import { validateResult } from "../lib/validate";
import { useJob } from "../lib/useJob";
import { JobStatus } from "../components/JobStatus";
import { MoonPage } from "../components/MoonPage";
import { Analyse } from "../components/Analyse";
import { RESULT } from "./fixtures";

const fetchMock = vi.fn();
const ok = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  localStorage.clear();
  setApiBase("http://127.0.0.1:8765");
});

describe("API base configuration", () => {
  it("accepts https anywhere and http only on local or private addresses", () => {
    expect(apiBaseProblem("https://analysis.example.org")).toBeNull();
    expect(apiBaseProblem("http://127.0.0.1:8765")).toBeNull();
    expect(apiBaseProblem("http://192.168.1.20:8765")).toBeNull();
    expect(apiBaseProblem("http://10.0.2.2:8765")).toBeNull(); // Android emulator host
    expect(apiBaseProblem("http://analysis.example.org")).toMatch(/https/);
    expect(apiBaseProblem("http://8.8.8.8")).toMatch(/https/);
    expect(apiBaseProblem("")).toMatch(/No analysis server/);
    expect(apiBaseProblem("not a url")).toMatch(/not a valid URL/);
  });

  it("refuses to send requests to an insecure public address", async () => {
    setApiBase("http://analysis.example.org");
    await expect(api.datasets()).rejects.toMatchObject({ code: "config_error" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("retries", () => {
  it("retries transient failures a bounded number of times", async () => {
    const fn = vi.fn().mockRejectedValue(new ApiError(0, "network_error", "x"));
    await expect(withRetry(fn, 3, 1)).rejects.toMatchObject({ code: "network_error" });
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("does not retry client errors", async () => {
    const fn = vi.fn().mockRejectedValue(new ApiError(422, "validation_error", "x"));
    await expect(withRetry(fn, 3, 1)).rejects.toMatchObject({ status: 422 });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("submit reuses one idempotency key across retries", async () => {
    fetchMock.mockImplementationOnce(() => Promise.reject(new TypeError("Failed to fetch")))
      .mockImplementationOnce(() => ok({ id: "j1", status: "queued" }, 202));
    const j = await api.submit({ target: { lat: 1, lon_east: 2, patch_km: 40 }, earth_tiles: ["N38W111"], stride_km: 10 });
    expect(j.id).toBe("j1");
    const keys = fetchMock.mock.calls.map((c) => (c[1].headers as Record<string, string>)["Idempotency-Key"]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBeTruthy();
    expect(keys[0]).toBe(keys[1]);
  });
});

describe("result validation", () => {
  it("accepts a consistent result", () => {
    expect(validateResult(RESULT).ok).toBe(true);
  });

  it.each([
    ["non-finite distance", (r: any) => { r.ranking.results[0].distance = null; }, /distance/],
    ["duplicate ids", (r: any) => { r.ranking.results[1].candidate_id = r.ranking.results[0].candidate_id; }, /duplicate/],
    ["rank gap", (r: any) => { r.ranking.results[0].rank = 2; }, /1\.\.n/],
    ["excluded with a score", (r: any) => { r.ranking.results[1].distance = 0.1; }, /excluded/],
    ["unknown body", (r: any) => { r.target.body = "VENUS"; }, /body/],
    ["record/body mismatch", (r: any) => { r.target.body = "MOON"; }, /does not match/],
    ["missing target feature", (r: any) => { delete r.ranking.target_features.relief_20km_m; }, /target feature/],
  ])("rejects %s", (_n, mutate, msg) => {
    const r = structuredClone(RESULT);
    mutate(r);
    const v = validateResult(r);
    expect(v.ok).toBe(false);
    if (!v.ok) expect(v.problems.join(" ")).toMatch(msg);
  });

  it("never shows an invalid result as completed", async () => {
    localStorage.setItem("paf.currentJob", "jobV");
    const bad = structuredClone(RESULT) as any;
    bad.ranking.results[0].distance = "NaN";
    fetchMock.mockImplementation((url: string) => url.endsWith("/result") ? ok(bad)
      : ok({ id: "jobV", status: "succeeded", progress: 1, message: "Done", error: null, created: "", updated: "" }));
    let seen: ReturnType<typeof useJob> | null = null;
    function H() { const jobs = useJob(5); seen = jobs; return <JobStatus jobs={jobs} />; }
    render(<H />);
    await screen.findByText(/failed validation/);
    expect(seen!.result).toBeNull();
  });
});

describe("polling ends", () => {
  it("warns and then stops polling a job that makes no progress", async () => {
    localStorage.setItem("paf.currentJob", "jobS");
    fetchMock.mockImplementation(() => ok({ id: "jobS", status: "running", progress: 0.3, message: "Tile 1/1", error: null, created: "", updated: "" }));
    function H() { const jobs = useJob(5, { warnMs: 20, stopMs: 80 }); return <JobStatus jobs={jobs} />; }
    render(<H />);
    await screen.findByText(/has not progressed/, undefined, { timeout: 3000 });
    const calls = fetchMock.mock.calls.length;
    await new Promise((r) => setTimeout(r, 60));
    expect(fetchMock.mock.calls.length).toBe(calls); // polling stopped
    fireEvent.click(screen.getByText("Check again"));
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(calls));
  });
});

const MOON_DS = {
  synthetic_data: false, mars_megdr: [], earth_srtm: [{ tile: "N38W111", num_file: true }],
  moon_lola: [{ product_id: "LDEM_64", data_set_id: "LRO-L-LOLA-4-GDR-V1.0", version: "V3.1", lat: [-90, 90] as [number, number],
    lon_east: [0, 360] as [number, number], spacing_m: 473.8, quality_flags: ["interpolated_cells_not_identified: x"] }],
};

describe("Moon", () => {
  it("shows real server coverage when a validated product exists, and no measurements before an analysis", () => {
    render(<MoonPage datasets={MOON_DS} go={() => {}} />);
    expect(screen.getByText("LDEM_64 V3.1 (LRO-L-LOLA-4-GDR-V1.0)")).toBeTruthy();
    expect(screen.queryByText(/vV3/)).toBeNull();
    expect(screen.getByText(/473.8 m/)).toBeTruthy();
    expect(screen.getByText(/No Moon analysis in this session yet/)).toBeTruthy();
  });

  it("the analysis form offers Moon only when available and submits body MOON", async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/datasets")) return ok(MOON_DS);
      if (url.endsWith("/analyses")) return ok({ id: "m1", status: "queued", progress: 0, message: "", error: null, created: "", updated: "" }, 202);
      return ok({ id: "m1", status: "queued", progress: 0, message: "", error: null, created: "", updated: "" });
    });
    const start = vi.fn();
    const jobs = { jobId: null, job: null, result: null, connectionLost: false, stalled: false, error: null,
      start, cancel: vi.fn(), clear: vi.fn(), retry: vi.fn() } as any;
    render(<Analyse jobs={jobs} extraTiles={[]} onShowResults={() => {}} />);
    const moon = await screen.findByLabelText(/Moon \(LOLA LDEM_64\)/);
    await waitFor(() => expect((moon as HTMLInputElement).disabled).toBe(false));
    fireEvent.click(moon);
    expect((screen.getByLabelText(/Centre latitude/) as HTMLInputElement).value).toBe("20.19");
    fireEvent.click(screen.getByRole("button", { name: /Run analysis/ }));
    await waitFor(() => expect(start).toHaveBeenCalledWith("m1"));
    const sent = JSON.parse(fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/analyses"))![1].body);
    expect(sent.target).toEqual({ body: "MOON", lat: 20.19, lon_east: 30.77, patch_km: 40 });
  });

  it("blocks an invalid longitude before submission", async () => {
    fetchMock.mockImplementation(() => ok({ ...MOON_DS, moon_lola: [] }));
    const jobs = { jobId: null, job: null, result: null, start: vi.fn() } as any;
    render(<Analyse jobs={jobs} extraTiles={[]} onShowResults={() => {}} />);
    await screen.findByText(/N38W111/);
    expect((screen.getByLabelText(/Moon \(LOLA LDEM_64\)/) as HTMLInputElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Centre longitude/), { target: { value: "-110" } });
    expect(screen.getByText(/east longitude from 0/)).toBeTruthy();
    expect((screen.getByRole("button", { name: /Run analysis/ }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("server failures never crash or fake success", () => {
  it("times out a request that never answers, with a clear message", async () => {
    vi.useFakeTimers();
    try {
      fetchMock.mockImplementation((_u: string, init: RequestInit) => new Promise((_res, rej) => {
        init.signal?.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")));
      }));
      const p = api.job("j1");
      const assertion = expect(p).rejects.toMatchObject({ code: "network_error", message: expect.stringMatching(/did not answer within 15 s/) });
      await vi.advanceTimersByTimeAsync(15_001);
      await assertion;
    } finally {
      vi.useRealTimers();
    }
  });

  it("turns an HTML 500 page into a structured error", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(new Response("<html>Internal Server Error</html>", { status: 500 })));
    await expect(api.job("j1")).rejects.toMatchObject({ status: 500, code: "http_error", message: "Server returned 500" });
  });

  it("rejects a non-JSON 200 result instead of showing it", () => {
    const v = validateResult("<html>proxy login page</html>");
    expect(v.ok).toBe(false);
  });

  it("shows the failure, not results, when the job failed on the server", async () => {
    localStorage.setItem("paf.currentJob", "jobF");
    fetchMock.mockImplementation(() => ok({ id: "jobF", status: "failed", progress: 0.4, message: "",
      error: { code: "MetricError", message: "Only 2 eligible candidates (minimum 3)" }, created: "", updated: "" }));
    let seen: ReturnType<typeof useJob> | null = null;
    function H() { const jobs = useJob(5); seen = jobs; return <JobStatus jobs={jobs} />; }
    render(<H />);
    await screen.findByText(/Only 2 eligible candidates/);
    expect(seen!.result).toBeNull();
    expect(screen.queryByText("Show results")).toBeNull();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/result"))).toBe(false);
  });
});

describe("connection diagnostics for real phones", () => {
  it("explains that 10.0.2.2 only works in the emulator and names the address tried", async () => {
    setApiBase("http://10.0.2.2:8765");
    fetchMock.mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    await expect(api.job("j1")).rejects.toMatchObject({
      code: "network_error",
      message: expect.stringMatching(/at http:\/\/10\.0\.2\.2:8765\..*only works inside the Android emulator/),
    });
  });

  it("Settings test connection reports success and failure without saving", async () => {
    const { Settings } = await import("../components/Settings");
    setApiBase("http://10.0.2.2:8765");
    render(<Settings readable={false} setReadable={() => {}} onDeleteLocalData={() => {}} />);
    const input = screen.getByLabelText(/Analysis server address/);
    fireEvent.change(input, { target: { value: "http://192.168.1.105:8765" } });
    fetchMock.mockImplementationOnce(() => Promise.reject(new TypeError("Failed to fetch")));
    fireEvent.click(screen.getByText("Test connection"));
    await screen.findByText(/Connection failed\./);
    expect(screen.getByRole("alert").textContent).toMatch(/same Wi-Fi \(not mobile data\)/);
    fetchMock.mockImplementationOnce(() => ok({ status: "ok", core_version: "0.2.0", synthetic_data: false }));
    fireEvent.click(screen.getByText("Test connection"));
    await screen.findByText(/Server version 0.2.0/);
    expect(String(fetchMock.mock.calls.at(-1)![0])).toBe("http://192.168.1.105:8765/v1/health");
    expect(localStorage.getItem("paf.apiBase")).toBe("http://10.0.2.2:8765"); // not saved by testing
  });
});
