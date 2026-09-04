/**
 * Typed API client boundary for the Receivables Resolution Agent frontend.
 *
 * This client communicates with the backend HTTP API. It does not contain
 * business rules, policy calculations, or financial state mutations.
 */

export interface HealthResponse {
  status: string;
}

export interface HealthCheckResult {
  connected: boolean;
  data?: HealthResponse;
  error?: string;
}

/**
 * Resolve backend API base URL from environment configuration.
 * Defaults to http://localhost:8000 for local development.
 */
export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

/**
 * Fetch health status from backend GET /v1/health.
 *
 * Handles network failures, timeouts, and unexpected response schemas safely.
 */
export async function fetchHealthStatus(): Promise<HealthCheckResult> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/v1/health`;

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal: controller.signal,
      cache: 'no-store',
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return {
        connected: false,
        error: `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    const json = await response.json();

    // Validate structured response shape
    if (
      typeof json === 'object' &&
      json !== null &&
      typeof json.status === 'string' &&
      json.status === 'ok'
    ) {
      return {
        connected: true,
        data: json as HealthResponse,
      };
    }

    return {
      connected: false,
      error: 'Unexpected response schema from backend',
    };
  } catch (err: unknown) {
    if (err instanceof Error && err.name === 'AbortError') {
      return {
        connected: false,
        error: 'Connection timed out after 5 seconds',
      };
    }

    const message =
      err instanceof Error ? err.message : 'Network error connecting to backend';
    return {
      connected: false,
      error: message,
    };
  }
}
