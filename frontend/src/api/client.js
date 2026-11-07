// Centralized API client. Base URL comes from VITE_API_BASE_URL and
// defaults to the local Django dev server.
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, { status = 0, fields = {}, code = 'network_error' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields;
    this.code = code;
  }
}

export async function apiPost(path, body) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (networkError) {
    throw new ApiError(
      'Could not reach the routing service. Check that the backend is running.',
      { code: 'network_error' }
    );
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const error = payload?.error || {};
    throw new ApiError(error.message || `Request failed (HTTP ${response.status})`, {
      status: response.status,
      fields: error.fields || {},
      code: error.code || 'http_error',
    });
  }
  return payload;
}

export { API_BASE_URL };
