// Polls a backend job. The job id is remembered so the user can leave and come back;
// network loss is retried with backoff instead of losing the job. Polling always ends:
// at a final state, on a non-transient error, or when the job makes no progress for
// STALL_STOP_MS. A result is shown only after validateResult() accepts it.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type AnalysisResult, type Job } from "./api";
import { validateResult } from "./validate";

const KEY = "paf.currentJob";
export const STALL_WARN_MS = 10 * 60_000; // no change in progress/message for 10 min -> warn
export const STALL_STOP_MS = 60 * 60_000; // no change for 1 h -> stop polling and say so
const MAX_BACKOFF_MS = 15_000;

function load(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
function save(id: string | null): void {
  try {
    if (id) localStorage.setItem(KEY, id);
    else localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export function useJob(pollMs = 1000, stall = { warnMs: STALL_WARN_MS, stopMs: STALL_STOP_MS }) {
  const [jobId, setJobId] = useState<string | null>(load);
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [stalled, setStalled] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [generation, setGeneration] = useState(0); // bump to restart polling ("Check again")
  const delay = useRef(pollMs);

  const start = useCallback((id: string) => {
    save(id);
    setResult(null);
    setError(null);
    setStalled(false);
    setJob(null);
    setJobId(id);
  }, []);

  const clear = useCallback(() => {
    save(null);
    setJobId(null);
    setJob(null);
    setResult(null);
    setError(null);
    setStalled(false);
  }, []);

  const retry = useCallback(() => {
    setError(null);
    setStalled(false);
    setGeneration((g) => g + 1);
  }, []);

  const cancel = useCallback(async () => {
    if (!jobId) return;
    try {
      setJob(await api.cancel(jobId));
    } catch (e) {
      setError(e as ApiError);
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    let lastSig = "";
    let lastChange = Date.now();
    delay.current = pollMs;
    const tick = async () => {
      try {
        const j = await api.job(jobId);
        if (stop) return;
        setJob(j);
        setConnectionLost(false);
        delay.current = pollMs;
        if (j.status === "succeeded") {
          const raw = await api.result(jobId);
          if (stop) return;
          const v = validateResult(raw);
          if (v.ok) setResult(v.result);
          else setError(new ApiError(0, "invalid_result",
            `The server returned a result that failed validation, so it is not shown: ${v.problems.slice(0, 5).join("; ")}.`, v.problems));
          return;
        }
        if (j.status === "failed" || j.status === "cancelled") return;
        const sig = `${j.status}|${j.progress}|${j.message}`;
        if (sig !== lastSig) {
          lastSig = sig;
          lastChange = Date.now();
          setStalled(false);
        } else {
          const idle = Date.now() - lastChange;
          if (idle >= stall.stopMs) {
            setError(new ApiError(0, "job_stalled",
              `The job has not progressed for ${Math.round(idle / 60_000)} min, so checking stopped. It may be stuck on the server. Check again, cancel it, or start a new analysis.`));
            return;
          }
          if (idle >= stall.warnMs) setStalled(true);
        }
      } catch (e) {
        if (stop) return;
        const err = e as ApiError;
        if (err.code === "network_error" || [502, 503, 504].includes(err.status)) {
          setConnectionLost(true);
          delay.current = Math.min(delay.current * 2, MAX_BACKOFF_MS);
        } else if (err.status === 404) {
          setError(new ApiError(404, "job_not_found", "This job is no longer known to the server. Start a new analysis."));
          save(null);
          return;
        } else {
          setError(err);
          return;
        }
      }
      timer = setTimeout(tick, delay.current);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [jobId, pollMs, generation, stall.warnMs, stall.stopMs]);

  return { jobId, job, result, connectionLost, stalled, error, start, cancel, clear, retry };
}
