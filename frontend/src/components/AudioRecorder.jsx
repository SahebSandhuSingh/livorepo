import { useState, useRef, useEffect, useCallback } from 'react';

export default function AudioRecorder({ disabled, onRecordingComplete }) {
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);
  const streamRef = useRef(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, []);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Prefer webm, fall back to whatever is available
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : ''; // let browser pick

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        onRecordingComplete(blob);
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      };

      recorder.start(1000); // collect data every second
      setRecording(true);
      setElapsed(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setElapsed((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error('Microphone access denied:', err);
      alert('Microphone access is required to record audio. Please allow microphone access in your browser settings.');
    }
  }, [onRecordingComplete]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setRecording(false);
  }, []);

  const formatTimer = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Visual cue for recording duration
  const isInRange = elapsed >= 30 && elapsed <= 45;
  const isTooLong = elapsed > 45;

  return (
    <div className={`recorder ${disabled ? 'disabled' : ''}`}>
      <div className="record-timer" style={{
        color: isTooLong ? 'var(--color-error)' : isInRange ? 'var(--word-good)' : 'var(--text-primary)'
      }}>
        {formatTimer(elapsed)}
      </div>

      <button
        className={`record-btn ${recording ? 'recording' : ''}`}
        onClick={recording ? stopRecording : startRecording}
        disabled={disabled}
        title={recording ? 'Stop recording' : 'Start recording'}
      >
        <div className="record-btn-inner" />
      </button>

      <div className="record-label">
        {!recording && elapsed === 0 && 'Tap to start recording'}
        {recording && !isInRange && !isTooLong && `Recording… (need at least 30s)`}
        {recording && isInRange && '✓ Good length! You can stop now.'}
        {recording && isTooLong && '⚠ Over 45 seconds — please stop'}
        {!recording && elapsed > 0 && 'Recording saved'}
      </div>
    </div>
  );
}
