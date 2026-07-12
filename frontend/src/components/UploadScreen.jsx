import { useState, useCallback, useRef } from 'react';
import AudioRecorder from './AudioRecorder';
import { getAudioDuration, validateDuration, formatTime } from '../audioUtils';

export default function UploadScreen({ onSubmit }) {
  const [mode, setMode] = useState('upload'); // 'upload' | 'record'
  const [file, setFile] = useState(null);
  const [duration, setDuration] = useState(null);
  const [durationError, setDurationError] = useState('');
  const [consent, setConsent] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef(null);

  const processFile = useCallback(async (audioFile) => {
    setDurationError('');
    setFile(audioFile);

    try {
      const dur = await getAudioDuration(audioFile);
      setDuration(dur);

      const validation = validateDuration(dur);
      if (!validation.valid) {
        setDurationError(validation.message);
      }
    } catch {
      setDuration(null);
      setDurationError('Could not read audio duration. The file may be corrupted.');
    }
  }, []);

  const handleFilePick = useCallback((e) => {
    const selected = e.target.files?.[0];
    if (selected) processFile(selected);
  }, [processFile]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) processFile(dropped);
  }, [processFile]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragging(false);
  }, []);

  const handleRecordingComplete = useCallback((blob) => {
    const audioFile = new File([blob], 'recording.webm', { type: blob.type });
    processFile(audioFile);
  }, [processFile]);

  const handleRemoveFile = useCallback(() => {
    setFile(null);
    setDuration(null);
    setDurationError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  const canSubmit = file && consent && duration && !durationError;

  const handleSubmit = () => {
    if (canSubmit) onSubmit(file);
  };

  return (
    <div className="upload-screen">
      {/* Mode Tabs */}
      <div className="mode-tabs">
        <button
          className={`mode-tab ${mode === 'upload' ? 'active' : ''}`}
          onClick={() => { setMode('upload'); handleRemoveFile(); }}
        >
          Upload File
        </button>
        <button
          className={`mode-tab ${mode === 'record' ? 'active' : ''}`}
          onClick={() => { setMode('record'); handleRemoveFile(); }}
        >
          Record
        </button>
      </div>

      {/* Consent Gate */}
      <div className="consent">
        <input
          type="checkbox"
          id="consent-check"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        <label htmlFor="consent-check">
          I understand that my audio will be sent to a server for pronunciation analysis only.
          The audio is <strong>not stored</strong> after processing and is <strong>deleted immediately</strong> after
          analysis is complete.
        </label>
      </div>

      {/* Upload Mode */}
      {mode === 'upload' && !file && (
        <div
          className={`drop-zone ${dragging ? 'dragging' : ''} ${!consent ? 'disabled' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => consent && fileInputRef.current?.click()}
        >
          <div className="drop-zone-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5, color: 'var(--primary)' }}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <p className="drop-zone-text">
            <strong>Drop your audio file here</strong> or click to browse
          </p>
          <p className="drop-zone-text" style={{ marginTop: '8px', fontSize: '0.75rem' }}>
            WAV, MP3, M4A, OGG, FLAC, WebM · 30–45 seconds · max 20 MB
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFilePick}
            style={{ display: 'none' }}
          />
        </div>
      )}

      {/* Record Mode */}
      {mode === 'record' && !file && (
        <AudioRecorder
          disabled={!consent}
          onRecordingComplete={handleRecordingComplete}
        />
      )}

      {/* File Info (shown after file selected or recording done) */}
      {file && (
        <div className="file-info">
          <span style={{ fontSize: '1.5rem' }}>🎵</span>
          <div className="file-info-details">
            <div className="file-info-name">{file.name}</div>
            <div className="file-info-meta">
              {duration ? formatTime(duration) : 'Reading duration…'}
              {' · '}
              {(file.size / (1024 * 1024)).toFixed(1)} MB
            </div>
          </div>
          <button className="file-remove" onClick={handleRemoveFile} title="Remove file">
            ✕
          </button>
        </div>
      )}

      {/* Duration Error */}
      {durationError && (
        <div className="inline-error">
          ⚠️ {durationError}
        </div>
      )}

      {/* Submit */}
      <button
        className="submit-btn"
        disabled={!canSubmit}
        onClick={handleSubmit}
      >
        Analyze Pronunciation
      </button>
    </div>
  );
}
