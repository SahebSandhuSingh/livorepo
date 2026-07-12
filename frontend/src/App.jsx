import { useState, useCallback } from 'react';
import UploadScreen from './components/UploadScreen';
import ResultsScreen from './components/ResultsScreen';
import LoadingScreen from './components/LoadingScreen';
import ErrorBanner from './components/ErrorBanner';
import { assessPronunciation, ApiError } from './api';

const SCREENS = {
  UPLOAD: 'upload',
  LOADING: 'loading',
  RESULTS: 'results',
  ERROR: 'error',
};

export default function App() {
  const [screen, setScreen] = useState(SCREENS.UPLOAD);
  const [result, setResult] = useState(null);
  const [audioBlob, setAudioBlob] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = useCallback(async (file) => {
    setAudioBlob(file);
    setScreen(SCREENS.LOADING);
    setError(null);

    try {
      const data = await assessPronunciation(file);
      setResult(data);
      setScreen(SCREENS.RESULTS);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setError({
          message: err.message,
          detail: `Error code: ${err.code}`,
          canRetry: false,
        });
        setScreen(SCREENS.ERROR);
      } else {
        setError({
          message: err.message || 'Something went wrong.',
          detail: err instanceof ApiError ? `Error code: ${err.code}` : '',
          canRetry: true,
        });
        setScreen(SCREENS.ERROR);
      }
    }
  }, []);

  const handleRetry = useCallback(() => {
    if (audioBlob && error?.canRetry) {
      handleSubmit(audioBlob);
    } else {
      handleReset();
    }
  }, [audioBlob, error, handleSubmit]);

  const handleReset = useCallback(() => {
    setScreen(SCREENS.UPLOAD);
    setResult(null);
    setAudioBlob(null);
    setError(null);
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="badge">✦ AI Pronunciation Coach</div>
        <h1>
          Speak clearly,{' '}
          <span className="highlight">score confidently</span>
        </h1>
        <p>
          Upload or record a 30–45 second English clip. Get word-by-word
          scores, highlighted mistakes, and plain-English coaching — instantly.
        </p>
      </header>

      {screen === SCREENS.UPLOAD && (
        <UploadScreen onSubmit={handleSubmit} />
      )}

      {screen === SCREENS.LOADING && (
        <LoadingScreen />
      )}

      {screen === SCREENS.ERROR && error && (
        <ErrorBanner
          message={error.message}
          detail={error.detail}
          canRetry={error.canRetry}
          onRetry={handleRetry}
          onReset={handleReset}
        />
      )}

      {screen === SCREENS.RESULTS && result && (
        <ResultsScreen
          result={result}
          audioBlob={audioBlob}
          onReset={handleReset}
        />
      )}
    </div>
  );
}
