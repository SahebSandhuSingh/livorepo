export default function ErrorBanner({ message, detail, canRetry, onRetry, onReset }) {
  return (
    <div className="error-banner">
      <div className="error-banner-message">⚠️ {message}</div>
      {detail && <div className="error-banner-detail">{detail}</div>}
      <div className="error-banner-actions">
        {canRetry && (
          <button className="error-retry-btn" onClick={onRetry}>
            Try Again
          </button>
        )}
        <button className="error-retry-btn" onClick={onReset}>
          ← Start Over
        </button>
      </div>
    </div>
  );
}
