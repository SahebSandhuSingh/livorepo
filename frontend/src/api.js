/**
 * API service — handles communication with the pronunciation assessment backend.
 *
 * All calls use a 60-second client-side timeout. Errors are parsed and
 * surfaced as structured objects, never unhandled promise rejections.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 90_000; // 90s — generous since Whisper + Azure + Claude run sequentially

/**
 * Submit an audio file for pronunciation assessment.
 *
 * @param {File|Blob} audioFile - The audio file to assess
 * @param {Object} options
 * @param {number} [options.threshold] - Optional score threshold override
 * @returns {Promise<Object>} Assessment result
 * @throws {ApiError} On validation, network, or server errors
 */
export async function assessPronunciation(audioFile, { threshold } = {}) {
  const formData = new FormData();
  formData.append('file', audioFile);

  let url = `${API_BASE}/api/assess`;
  if (threshold != null) {
    url += `?threshold=${encodeURIComponent(threshold)}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const data = await response.json();

    if (!response.ok) {
      // Backend returns structured error JSON
      const detail = data?.detail;
      if (typeof detail === 'object' && detail !== null) {
        throw new ApiError(
          detail.detail || detail.error || 'Request failed',
          response.status,
          detail.error
        );
      }
      // SlowAPI rate limit or other text errors
      throw new ApiError(
        typeof detail === 'string' ? detail : `Request failed (${response.status})`,
        response.status,
        'request_failed'
      );
    }

    return data;
  } catch (err) {
    clearTimeout(timeoutId);

    if (err instanceof ApiError) {
      throw err;
    }

    if (err.name === 'AbortError') {
      throw new ApiError(
        'The request timed out. The server may be under heavy load — please try again.',
        0,
        'timeout'
      );
    }

    // Network error (CORS, server down, etc.)
    throw new ApiError(
      'Could not reach the server. Please check your connection and try again.',
      0,
      'network_error'
    );
  }
}

/**
 * Check if the backend is healthy.
 */
export async function healthCheck() {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { signal: AbortSignal.timeout(5000) });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * Structured API error.
 */
export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}
