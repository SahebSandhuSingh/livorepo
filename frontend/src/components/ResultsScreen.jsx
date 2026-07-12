import { useState, useRef, useEffect } from 'react';

export default function ResultsScreen({ result, audioBlob, onReset }) {
  const [activeWordIndex, setActiveWordIndex] = useState(null);
  const [playingWordIndex, setPlayingWordIndex] = useState(null);
  const audioRef = useRef(null);
  const popoverRef = useRef(null);

  // Close popover when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (popoverRef.current && !popoverRef.current.contains(event.target)) {
        setActiveWordIndex(null);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Track current playback time to highlight the spoken word
  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    const time = audioRef.current.currentTime;

    if (result.words && result.words.length > 0) {
      const index = result.words.findIndex(w => time >= w.start && time <= w.end);
      setPlayingWordIndex(index !== -1 ? index : null);
    }
  };

  const handleWordClick = (index, e) => {
    e.stopPropagation();
    setActiveWordIndex(activeWordIndex === index ? null : index);
  };

  const getScoreClass = (score) => {
    if (score >= 80) return 'score-good';
    if (score >= 60) return 'score-mid';
    return 'score-bad';
  };

  const getScoreLabel = (score) => {
    if (score >= 80) return 'good';
    if (score >= 60) return 'mid';
    return 'bad';
  };

  const [audioUrl, setAudioUrl] = useState('');

  useEffect(() => {
    if (!audioBlob) {
      setAudioUrl('');
      return;
    }
    const url = URL.createObjectURL(audioBlob);
    setAudioUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [audioBlob]);

  const showScoring = !result.scoring_unavailable;

  return (
    <div className="results-screen">
      {/* Azure failure fallback */}
      {result.scoring_unavailable && (
        <div className="info-banner">
          ℹ️ Pronunciation scoring is temporarily unavailable — showing transcript only.
          {result.scoring_error && (
            <div style={{ fontSize: '0.75rem', marginTop: '4px', opacity: 0.8 }}>
              Details: {result.scoring_error}
            </div>
          )}
        </div>
      )}

      {/* Score Header */}
      {showScoring && (
        <div className="score-header">
          <div className="overall-score">
            <span className="score-value">{Math.round(result.overall_score)}</span>
            <span className="score-max">/100</span>
          </div>
          <div className="score-label-text">Overall Accuracy</div>

          <div className="sub-scores">
            <div className="sub-score">
              <div className="sub-score-value">{Math.round(result.fluency)}</div>
              <div className="sub-score-label">Fluency</div>
            </div>
            <div className="sub-score">
              <div className="sub-score-value">{Math.round(result.completeness)}</div>
              <div className="sub-score-label">Completeness</div>
            </div>
            <div className="sub-score">
              <div className="sub-score-value">{Math.round(result.prosody)}</div>
              <div className="sub-score-label">Prosody</div>
            </div>
          </div>
        </div>
      )}

      {/* Coach Summary */}
      {result.summary && (
        <div className="summary-card">
          <div className="summary-card-label">Coach Feedback</div>
          <div className="summary-text">"{result.summary}"</div>
        </div>
      )}

      {/* Audio Player */}
      {audioUrl && (
        <div className="audio-player-section">
          <audio
            ref={audioRef}
            src={audioUrl}
            controls
            onTimeUpdate={handleTimeUpdate}
          />
        </div>
      )}

      {/* Transcript */}
      <div className="transcript-section">
        <div className="transcript-label">Transcript · Tap any word for details</div>
        <div className="transcript-words">
          {result.words && result.words.length > 0 ? (
            result.words.map((wordObj, index) => {
              const isPlaying = index === playingWordIndex;
              const isPopoverOpen = index === activeWordIndex;

              return (
                <span key={index} className="word-popover-anchor">
                  <span
                    className={`transcript-word ${showScoring ? getScoreClass(wordObj.score) : ''} ${isPlaying ? 'active' : ''}`}
                    onClick={(e) => handleWordClick(index, e)}
                  >
                    {wordObj.word}{' '}
                  </span>

                  {isPopoverOpen && (
                    <div ref={popoverRef} className="word-popover">
                      <div className="word-popover-header">
                        <span className="word-popover-word">{wordObj.word.trim()}</span>
                        {showScoring && (
                          <span className={`word-popover-score ${getScoreLabel(wordObj.score)}`}>
                            {Math.round(wordObj.score)}/100
                          </span>
                        )}
                      </div>

                      {showScoring && wordObj.issue && (
                        <div className="word-popover-issue">Issue: {wordObj.issue}</div>
                      )}

                      {showScoring && (wordObj.score < 60 || wordObj.issue) ? (
                        <div className="word-popover-feedback">
                          {wordObj.feedback || `Pronunciation issue: ${wordObj.issue || 'Low accuracy'} (Score: ${Math.round(wordObj.score)}/100).`}
                        </div>
                      ) : showScoring ? (
                        <div className="word-popover-feedback">
                          {wordObj.feedback || "Excellent pronunciation. No issues detected."}
                        </div>
                      ) : (
                        <div className="word-popover-feedback">Scoring details unavailable.</div>
                      )}
                    </div>
                  )}
                </span>
              );
            })
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-md)' }}>
              {result.transcript || 'No words detected.'}
            </p>
          )}
        </div>
      </div>

      {/* Start Over */}
      <button className="reset-btn" onClick={onReset}>
        ← Try Another Recording
      </button>
    </div>
  );
}
