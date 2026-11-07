export function LoadingState({ message = 'Contacting routing and weather services…' }) {
  return (
    <div className="state state-loading" role="status">
      <div className="spinner" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <p className="state-title">Something went wrong</p>
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="secondary-button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState() {
  return (
    <div className="state state-empty">
      <p className="state-title">No routes yet</p>
      <p>
        Enter an origin and destination, then choose <strong>Generate Routes</strong> to compare
        up to three routes with live weather risk at every checkpoint.
      </p>
    </div>
  );
}
