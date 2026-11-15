// Thin client for the Planetary Analog Finder API. No scientific logic lives here.

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

// Production builds take the server address from VITE_PAF_API_BASE at build time (it must be
// https:// unless it is a local/private address). Development builds fall back to the local
// API. Users can override the address in Settings.
const ENV_BASE = ((import.meta.env.VITE_PAF_API_BASE as string | undefined) ?? "").replace(/\/+$/, "");
export const DEFAULT_BASE = ENV_BASE || (import.meta.env.DEV ? "http://127.0.0.1:8765" : "");
const KEY = "paf.apiBase";

export function getApiBase(): string {
  try {
    return localStorage.getItem(KEY) || DEFAULT_BASE;
  } catch {
    return DEFAULT_BASE;
  }
}

export function setApiBase(url: string): void {
  try {
    localStorage.setItem(KEY, url.trim().replace(/\/+$/, ""));
  } catch {
    /* storage unavailable: setting lasts for this session only */
  }
}

const PRIVATE_HOST = /^(localhost|127\.0\.0\.1|\[::1\]|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)$/;

/** Why an address cannot be used, or null. Plain HTTP is accepted only for local/private-network hosts. */
export function apiBaseProblem(base: string): string | null {
  if (!base) return "No analysis server is configured. Enter its address in Settings.";
  let u: URL;
  try {
    u = new URL(base);
  } catch {
    return "The server address is not a valid URL (example: https://analysis.example.org).";
  }
  if (u.protocol === "https:") return null;
  if (u.protocol === "http:" && PRIVATE_HOST.test(u.hostname)) return null;
  return "Use https:// for a server outside your local network; plain http:// is allowed only for local or private-network addresses.";
}

/** Why an address that is syntactically valid may still be unreachable from this device. */
export function connectionHint(base: string): string {
  let host = "";
  try {
    host = new URL(base).hostname;
  } catch {
    return "";
  }
  if (host === "10.0.2.2") {
    return "10.0.2.2 only works inside the Android emulator. On a real phone, enter your computer's Wi-Fi address " +
      "(for example http://192.168.1.105:8765) with the phone on the same Wi-Fi, or use http://127.0.0.1:8765 over a " +
      "USB cable after running 'adb reverse tcp:8765 tcp:8765' on the computer.";
  }
  if (host === "127.0.0.1" || host === "localhost" || host === "[::1]") {
    return "127.0.0.1 means this device itself. On a phone it works only over a USB cable after " +
      "'adb reverse tcp:8765 tcp:8765'; otherwise enter your computer's Wi-Fi address.";
  }
  if (PRIVATE_HOST.test(host)) {
    return "Check that the server is running with --host 0.0.0.0, that this device is on the same Wi-Fi " +
      "(not mobile data), and that the computer's firewall allows the port.";
  }
  return "Check that the server is running and reachable over HTTPS.";
}

export type ServerCheck = { ok: true; version: string; synthetic: boolean } | { ok: false; message: string };

/** Probe /v1/health at an address without saving it (Settings "Test connection"). */
export async function checkServer(base: string, timeoutMs = 8000): Promise<ServerCheck> {
  const clean = base.trim().replace(/\/+$/, "");
  const problem = apiBaseProblem(clean);
  if (problem) return { ok: false, message: problem };
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(`${clean}/v1/health`, { signal: ctl.signal });
    const body = (await res.json().catch(() => null)) as { status?: string; core_version?: string; synthetic_data?: boolean } | null;
    if (!res.ok || body?.status !== "ok") {
      return { ok: false, message: `The address answered, but not as a Planetary Analog Finder server (HTTP ${res.status}).` };
    }
    return { ok: true, version: body.core_version ?? "unknown", synthetic: !!body.synthetic_data };
  } catch {
    const lead = ctl.signal.aborted ? `No answer within ${timeoutMs / 1000} s.` : "Cannot connect.";
    return { ok: false, message: `${lead} ${connectionHint(clean)}` };
  } finally {
    clearTimeout(timer);
  }
}

const TRANSIENT = new Set([502, 503, 504]);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
export const RETRY = { attempts: 3, baseDelayMs: 500 };

/** Bounded retry with exponential backoff, for transient failures only (network, 502/503/504). */
export async function withRetry<T>(fn: () => Promise<T>, attempts = RETRY.attempts, baseDelayMs = RETRY.baseDelayMs): Promise<T> {
  for (let i = 0; ; i++) {
    try {
      return await fn();
    } catch (e) {
      const err = e as ApiError;
      const transient = err.code === "network_error" || TRANSIENT.has(err.status);
      if (!transient || i >= attempts - 1) throw e;
      await sleep(baseDelayMs * 2 ** i);
    }
  }
}

function newIdempotencyKey(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c?.randomUUID) return c.randomUUID();
  return `k${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const problem = apiBaseProblem(getApiBase());
  if (problem) throw new ApiError(0, "config_error", problem);
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${getApiBase()}/v1${path}`, { ...init, signal: ctl.signal });
  } catch {
    throw new ApiError(0, "network_error", ctl.signal.aborted
      ? `The analysis server did not answer within ${timeoutMs / 1000} s. Check the connection and the server address in Settings.`
      : `Cannot reach the analysis server at ${getApiBase()}. ${connectionHint(getApiBase())} You can change the address in Settings.`);
  } finally {
    clearTimeout(timer);
  }
  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) {
    const e = (body as { error?: { code: string; message: string; details?: unknown } } | null)?.error;
    throw new ApiError(res.status, e?.code ?? "http_error", e?.message ?? `Server returned ${res.status}`, e?.details);
  }
  return body as T;
}

function safeJson(t: string): unknown {
  try {
    return JSON.parse(t);
  } catch {
    return t;
  }
}

export type Job = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  message: string;
  error: { code: string; message: string } | null;
  created: string;
  updated: string;
};

export type Body = "MARS" | "MOON";
export type AnalysisRequest = {
  target: { body?: Body; lat: number; lon_east: number; patch_km: number };
  earth_tiles: string[];
  stride_km: number;
  weights?: Record<string, number> | null;
};

const get = <T,>(path: string, timeoutMs?: number) => withRetry(() => request<T>(path, undefined, timeoutMs));

export const api = {
  health: () => get<{ status: string; synthetic_data: boolean; disclaimer: string; core_version: string }>("/health"),
  sources: () => get<{ approved: Source[]; excluded: Record<string, string> }>("/sources"),
  datasets: () => get<Datasets>("/datasets"),
  /** One idempotency key per submission, reused on retries, so a retry never queues a second job. */
  submit: (body: AnalysisRequest) => {
    const headers = { "Content-Type": "application/json", "Idempotency-Key": newIdempotencyKey() };
    return withRetry(() => request<Job>("/analyses", { method: "POST", headers, body: JSON.stringify(body) }));
  },
  job: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}`),
  cancel: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  /** Returns unvalidated JSON: callers must run validateResult() before showing it. */
  result: (id: string) => get<unknown>(`/jobs/${encodeURIComponent(id)}/result`, 60000),
  exportUrl: (id: string, format: "json" | "csv", includeCoordinates: boolean) =>
    `${getApiBase()}/v1/jobs/${encodeURIComponent(id)}/export?format=${format}&include_coordinates=${includeCoordinates}`,
};

export type Source = {
  key: string; data_set_id: string; final_product_version: string; doi: string; body: string;
  mission: string; instrument: string; archive: string; access_url: string; vertical_reference: string;
  citation: string; verified_from: string[]; notes: string;
};

export type TargetProduct = {
  product_id: string; data_set_id: string; version: string; lat: [number, number]; lon_east: [number, number];
  quality_flags: string[]; spacing_m?: number;
};

export type Datasets = {
  synthetic_data: boolean;
  mars_megdr: TargetProduct[];
  moon_lola?: TargetProduct[];
  earth_srtm: { tile: string; num_file: boolean }[];
};

export type Step = { operation: string; parameters: Record<string, unknown>; note: string; timestamp: string };
export type DatasetRecord = {
  product_id: string; data_set_id: string; product_version: string; doi: string; mission: string; instrument: string;
  archive: string; body: string; projection: string; horizontal_reference: string; vertical_reference: string;
  units: string; fill_value: string; citation: string; quality_flags: string[]; processing_history: Step[];
};
export type Region = { tile: string; lat_min: number; lat_max: number; lon_min: number; lon_max: number };
export type Elevation = { mean: number; std: number; min: number; max: number };
export type CandidateResult = {
  candidate_id: string; tile: string; rank: number | null; distance: number | null;
  region?: Region; elevation_m?: Elevation | null;
  feature_differences: Record<string, number>; normalized_differences: Record<string, number>;
  contributions: Record<string, number>; valid_fraction: number; fill_fraction: number | null;
  native_spacing_m: number; analysis_spacing_m: number; excluded: boolean; exclusion_reasons: string[];
  sensitivity: Record<string, number | null>; flags: string[];
};
export type AnalysisResult = {
  disclaimer: string; is_synthetic: boolean; software_version: string;
  target: { body: Body; patch_km: number; center_lat?: number; center_lon_east?: number;
    bounds?: { lat_min: number; lat_max: number; lon_min: number; lon_max: number } };
  target_metrics: { slope: { median: number; p90?: number }; flags: string[]; elevation_mean_m?: number; elevation_std_m?: number; valid_fraction?: number };
  target_record: DatasetRecord; earth_records: Record<string, DatasetRecord>;
  settings: Record<string, unknown>;
  coverage: { selection_method: string; tiles_requested: string[]; tiles_examined: string[]; tiles_failed: Record<string, string>; tiles_unavailable: Record<string, string>; tiles_outside_coverage: string[]; note: string };
  ranking: { score_meaning: string; features_used: string[]; features_dropped: Record<string, string>; weights: Record<string, number>; target_features: Record<string, number>; results: CandidateResult[]; flags: string[]; exclusion_rules: Record<string, number> };
  limitations: string[];
};
