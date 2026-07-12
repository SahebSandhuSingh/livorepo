/**
 * Audio utility functions — client-side duration reading and validation.
 */

/**
 * Read the duration of an audio file using an HTML Audio element.
 * Returns a Promise that resolves with the duration in seconds.
 *
 * @param {File|Blob} file
 * @returns {Promise<number>} Duration in seconds
 */
export function getAudioDuration(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const audio = new Audio();

    const cleanup = () => {
      URL.revokeObjectURL(url);
      audio.removeEventListener('loadedmetadata', onLoaded);
      audio.removeEventListener('error', onError);
    };

    const onLoaded = () => {
      cleanup();
      if (isFinite(audio.duration)) {
        resolve(audio.duration);
      } else {
        // Some formats (e.g. WebM) may not report duration in metadata
        // Fall back to loading the full audio
        const url2 = URL.createObjectURL(file);
        const audio2 = new Audio();
        audio2.addEventListener('durationchange', function handler() {
          if (isFinite(audio2.duration)) {
            audio2.removeEventListener('durationchange', handler);
            URL.revokeObjectURL(url2);
            resolve(audio2.duration);
          }
        });
        audio2.addEventListener('error', () => {
          URL.revokeObjectURL(url2);
          reject(new Error('Could not determine audio duration'));
        });
        audio2.src = url2;
      }
    };

    const onError = () => {
      cleanup();
      reject(new Error('Could not load audio file'));
    };

    audio.addEventListener('loadedmetadata', onLoaded);
    audio.addEventListener('error', onError);
    audio.src = url;
  });
}

/**
 * Validate audio duration is within allowed range.
 *
 * @param {number} duration - Duration in seconds
 * @param {number} min - Minimum duration (default 30)
 * @param {number} max - Maximum duration (default 45)
 * @returns {{ valid: boolean, message: string }}
 */
export function validateDuration(duration, min = 30, max = 45) {
  if (duration < min) {
    return {
      valid: false,
      message: `Audio is too short (${duration.toFixed(1)}s). Minimum is ${min} seconds.`,
    };
  }
  if (duration > max) {
    return {
      valid: false,
      message: `Audio is too long (${duration.toFixed(1)}s). Maximum is ${max} seconds.`,
    };
  }
  return { valid: true, message: '' };
}

/**
 * Format seconds as M:SS display.
 */
export function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
