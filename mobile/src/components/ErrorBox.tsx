import type { ApiError } from "../lib/api";

export function ErrorBox({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const details = Array.isArray(error.details) ? (error.details as ({ loc?: unknown[]; msg?: string; product_id?: string } | string)[]) : [];
  return (
    <div className="banner" role="alert">
      <strong>Error:</strong> {error.message}
      {details.length > 0 && (
        <ul>
          {details.map((d, i) => (
            <li key={i}>
              {typeof d === "string" ? d : d.msg ? `${(d.loc ?? []).slice(1).join(" → ")}: ${d.msg}` : JSON.stringify(d)}
            </li>
          ))}
        </ul>
      )}
      {onRetry && <button onClick={onRetry}>Try again</button>}
      {(error.code === "network_error" || error.code === "config_error") && <a className="button" href="#/settings">Open Settings</a>}
    </div>
  );
}
