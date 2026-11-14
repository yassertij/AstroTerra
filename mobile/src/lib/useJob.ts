// Polls a backend job. The job id is remembered so the user can leave and come back;
// network loss is retried with backoff instead of losing the job.
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, type AnalysisResult, type Job } from "./api";

const KEY = "paf.currentJob";

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

export function useJob(pollMs = 1000) {
  const [jobId, setJobId] = useState<string | null>(load);
  const [job, setJob] = useState<Job | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const delay = useRef(pollMs);

  const start = useCallback((id: string) => {
    save(id);
    setResult(null);
    setError(null);
    setJob(null);
    setJobId(id);
  }, []);

  const clear = useCallback(() => {
    save(null);
    setJobId(null);
    setJob(null);
    setResult(null);
    setError(null);
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
    const tick = async () => {
      try {
        const j = await api.job(jobId);
        if (stop) return;
        setJob(j);
        setConnectionLost(false);
        delay.current = pollMs;
        if (j.status === "succeeded") {
          setResult(await api.result(jobId));
          return;
        }
        if (j.status === "failed" || j.status === "cancelled") return;
      } catch (e) {
        if (stop) return;
        const err = e as ApiError;
        if (err.code === "network_error") {
          setConnectionLost(true);
          delay.current = Math.min(delay.current * 2, 15000);
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
  }, [jobId, pollMs]);

  return { jobId, job, result, connectionLost, error, start, cancel, clear };
}
