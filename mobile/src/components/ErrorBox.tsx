import type { ApiError } from "../lib/api";

export function ErrorBox({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const details = Array.isArray(error.details) ? (error.details as { loc?: unknown[]; msg?: string; product_id?: string }[]) : [];
  return (
    <div className="banner" role="alert">
      <strong>Error:</strong> {error.message}
      {details.length > 0 && (
        <ul>
          {details.map((d, i) => (
            <li key={i}>
              {d.msg ? `${(d.loc ?? []).slice(1).join(" → ")}: ${d.msg}` : JSON.stringify(d)}
            </li>
          ))}
        </ul>
      )}
      {onRetry && <button onClick={onRetry}>Try again</button>}
    </div>
  );
}
