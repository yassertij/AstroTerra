import type { useJob } from "../lib/useJob";
import { ErrorBox } from "./ErrorBox";

export function JobStatus({ jobs, onShowResults }: { jobs: ReturnType<typeof useJob>; onShowResults?: () => void }) {
  const { job, connectionLost, stalled, error } = jobs;
  const active = job && (job.status === "queued" || job.status === "running");
  return (
    <div className="card" aria-live="polite">
      <h3>Processing status</h3>
      {!job && !error && <p>Contacting the server…</p>}
      {job && (
        <>
          <p>
            Status: <strong>{job.status}</strong>
            {job.message ? ` — ${job.message}` : ""}
          </p>
          <progress max={1} value={job.progress} aria-label="Analysis progress" />
          <p className="hint">{Math.round(job.progress * 100)} %. You can leave this screen; the analysis keeps running on the server.</p>
        </>
      )}
      {connectionLost && <p role="status"><strong>Connection lost.</strong> Retrying automatically…</p>}
      {stalled && !error && <p role="status"><strong>No progress for over 10 minutes.</strong> The server may be busy or the job may be stuck. You can keep waiting or cancel it.</p>}
      {job?.status === "failed" && job.error && (
        <div className="banner" role="alert"><strong>Failed:</strong> {job.error.message}</div>
      )}
      {job?.status === "cancelled" && <p>The analysis was cancelled.</p>}
      {error && <ErrorBox error={error} />}
      {error?.code === "job_stalled" && <button onClick={jobs.retry}>Check again</button>}
      <div className="row">
        {active && <button onClick={jobs.cancel}>Cancel analysis</button>}
        {job?.status === "succeeded" && onShowResults && <button className="primary" onClick={onShowResults}>Show results</button>}
        {!active && <button onClick={jobs.clear}>Dismiss</button>}
      </div>
    </div>
  );
}
