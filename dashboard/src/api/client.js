/**
 * AIPI Normalized API Client (ES Module)
 *
 * Every accessor accepts an optional trailing AbortSignal so callers can
 * cancel in-flight requests (e.g. a page re-fetching after a filter change)
 * without letting a stale response overwrite newer state.
 */

export class ApiError extends Error {
  constructor(statusCode, errorCode, detail) {
    super(`${statusCode} [${errorCode}]: ${detail}`);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.detail = detail;
  }
}

class ApiClient {
  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
  }

  async request(path, options = {}) {
    const url = `${this.baseUrl}${path}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        Accept: 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      let errorCode = 'network_error';
      let detail = response.statusText;

      try {
        const errorBody = await response.json();
        errorCode = errorBody.error || errorCode;
        detail = errorBody.detail || detail;
      } catch {
        // Fall back to statusText if body is not JSON
      }

      throw new ApiError(response.status, errorCode, detail);
    }

    return await response.json();
  }

  // --- Ops ---
  async getHealth(signal) {
    return this.request('/health', { signal });
  }

  async getOpenApiSpec(signal) {
    return this.request('/openapi.json', { signal });
  }

  // --- Methodology & Provenance ---
  async getMethodology(signal) {
    return this.request('/api/v1/methodology', { signal });
  }

  async getPipelineRun(signal) {
    return this.request('/api/v1/pipeline-run', { signal });
  }

  // --- Reference ---
  async getRouteMetadata(signal) {
    return this.request('/api/v1/routes', { signal });
  }

  // --- Index & Series ---
  async getHeadlineIndex(params, signal) {
    const query = new URLSearchParams();
    if (params?.freq) query.set('freq', params.freq);
    if (params?.dowAdjusted) query.set('dow_adjusted', 'true');
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request(`/api/v1/index${qs ? `?${qs}` : ''}`, { signal });
  }

  async getRoutesSummary(signal) {
    return this.request('/api/v1/index/routes', { signal });
  }

  async getRouteSeries(routeCode, signal) {
    return this.request(`/api/v1/index/routes/${encodeURIComponent(routeCode)}`, { signal });
  }

  async getRouteHeatmap(params, signal) {
    const query = new URLSearchParams();
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request(`/api/v1/index/routes/heatmap${qs ? `?${qs}` : ''}`, { signal });
  }

  async getLeadtimeIndex(signal) {
    return this.request('/api/v1/index/leadtime', { signal });
  }

  async getLeadtimeCurve(asOf, signal) {
    const qs = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
    return this.request(`/api/v1/index/leadtime/curve${qs}`, { signal });
  }

  async getVolatility(signal) {
    return this.request('/api/v1/index/volatility', { signal });
  }

  // --- Validation ---
  async getValidationDgca(signal) {
    return this.request('/api/v1/validation/dgca', { signal });
  }
}

export const api = new ApiClient();
