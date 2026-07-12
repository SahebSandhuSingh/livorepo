export default function LoadingScreen() {
  return (
    <div className="loading-screen">
      <div className="spinner" />
      <div className="loading-text">Analyzing pronunciation…</div>
      <div className="loading-subtext">
        This typically takes 15–30 seconds. Your audio is being transcribed,
        scored, and analyzed for detailed feedback.
      </div>
    </div>
  );
}
