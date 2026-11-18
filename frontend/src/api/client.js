/**
 * Single API client module.
 * - Access token is kept strictly in memory (never in localStorage/sessionStorage).
 * - Automatically attempts a single-flight POST /auth/refresh (httpOnly cookie) on 401.
 * - Maps the backend `{error: {code, message, details, request_id}}` envelope to `ApiError`.
 * - Never contains an LLM key and never calls an LLM provider directly.
 */

const DEFAULT_BASE_URL = 'http://localhost:8000/api/v1';

export const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || DEFAULT_BASE_URL).replace(
  /\/+$/,
  '',
);

let accessToken = null;
let refreshPromise = null;

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token) {
  accessToken = token || null;
}

export function clearAccessToken() {
  accessToken = null;
}

export class ApiError extends Error {
  constructor(message, { status = 500, code = 'error', details = null, requestId = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

async function parseError(response) {
  try {
    const payload = await response.json();
    if (payload && payload.error) {
      return new ApiError(payload.error.message || 'Request failed', {
        status: response.status,
        code: payload.error.code || 'error',
        details: payload.error.details ?? null,
        requestId: payload.error.request_id ?? null,
      });
    }
  } catch {
    // Non-JSON response fallback
  }
  return new ApiError(`Request failed (${response.status})`, { status: response.status });
}

export async function refreshSession() {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) {
        clearAccessToken();
        return null;
      }
      const data = await response.json();
      setAccessToken(data.access_token);
      return data;
    } catch {
      clearAccessToken();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export async function apiRequest(
  path,
  { method = 'GET', body, headers = {}, signal, skipAuthRefresh = false } = {},
) {
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData;
  const reqHeaders = { Accept: 'application/json', ...headers };

  if (accessToken) {
    reqHeaders.Authorization = `Bearer ${accessToken}`;
  }
  if (body !== undefined && !isFormData) {
    reqHeaders['Content-Type'] = 'application/json';
  }

  const doFetch = () =>
    fetch(`${API_BASE_URL}${path}`, {
      method,
      credentials: 'include',
      headers: reqHeaders,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
      signal,
    });

  let response = await doFetch();

  if (
    response.status === 401 &&
    !skipAuthRefresh &&
    !path.startsWith('/auth/login') &&
    !path.startsWith('/auth/register') &&
    !path.startsWith('/auth/refresh')
  ) {
    const refreshed = await refreshSession();
    if (refreshed?.access_token) {
      reqHeaders.Authorization = `Bearer ${refreshed.access_token}`;
      response = await doFetch();
    }
  }

  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export async function apiDownloadBlob(path) {
  const headers = {};
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  let response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    credentials: 'include',
    headers,
  });
  if (response.status === 401) {
    const refreshed = await refreshSession();
    if (refreshed?.access_token) {
      headers.Authorization = `Bearer ${refreshed.access_token}`;
      response = await fetch(`${API_BASE_URL}${path}`, {
        method: 'GET',
        credentials: 'include',
        headers,
      });
    }
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return response.blob();
}
