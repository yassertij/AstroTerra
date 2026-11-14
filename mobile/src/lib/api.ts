// Thin client for the Planetary Analog Finder API. No scientific logic lives here.

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details?: unknown) {
    super(message);
  }
}

const DEFAULT_BASE = "http://127.0.0.1:8765";
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
    localStorage.setItem(KEY, url.replace(/\/+$/, ""));
  } catch {
    /* storage unavailable: setting lasts for this session only */
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${getApiBase()}/v1${path}`, { ...init, signal: ctl.signal });
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the analysis server. Check the connection and the server address in Settings.");
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

export type AnalysisRequest = {
  target: { lat: number; lon_east: number; patch_km: number };
  earth_tiles: string[];
  stride_km: number;
  weights?: Record<string, number> | null;
};

export const api = {
  health: () => request<{ status: string; synthetic_data: boolean; disclaimer: string; core_version: string }>("/health"),
  sources: () => request<{ approved: Source[]; excluded: Record<string, string> }>("/sources"),
  datasets: () => request<Datasets>("/datasets"),
  submit: (body: AnalysisRequest) =>
    request<Job>("/analyses", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  job: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}`),
  cancel: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  result: (id: string) => request<AnalysisResult>(`/jobs/${encodeURIComponent(id)}/result`, undefined, 60000),
  exportUrl: (id: string, format: "json" | "csv", includeCoordinates: boolean) =>
    `${getApiBase()}/v1/jobs/${encodeURIComponent(id)}/export?format=${format}&include_coordinates=${includeCoordinates}`,
};

export type Source = {
  key: string; data_set_id: string; final_product_version: string; doi: string; body: string;
  mission: string; instrument: string; archive: string; access_url: string; vertical_reference: string;
  citation: string; verified_from: string[]; notes: string;
};

export type Datasets = {
  synthetic_data: boolean;
  mars_megdr: { product_id: string; data_set_id: string; version: string; lat: [number, number]; lon_east: [number, number]; quality_flags: string[] }[];
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
  target: { body: string; patch_km: number; center_lat?: number; center_lon_east?: number;
    bounds?: { lat_min: number; lat_max: number; lon_min: number; lon_max: number } };
  target_metrics: { slope: { median: number; p90?: number }; flags: string[]; elevation_mean_m?: number; elevation_std_m?: number; valid_fraction?: number };
  target_record: DatasetRecord; earth_records: Record<string, DatasetRecord>;
  settings: Record<string, unknown>;
  coverage: { selection_method: string; tiles_requested: string[]; tiles_examined: string[]; tiles_failed: Record<string, string>; tiles_unavailable: Record<string, string>; tiles_outside_coverage: string[]; note: string };
  ranking: { score_meaning: string; features_used: string[]; features_dropped: Record<string, string>; weights: Record<string, number>; target_features: Record<string, number>; results: CandidateResult[]; flags: string[]; exclusion_rules: Record<string, number> };
  limitations: string[];
};
