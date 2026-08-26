/**
 * AIPI Normalized API Client (ES Module)
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
  async getHealth() {
    return this.request('/health');
  }

  // --- Methodology & Provenance ---
  async getMethodology() {
    return this.request('/api/v1/methodology');
  }

  async getPipelineRun() {
    return this.request('/api/v1/pipeline-run');
  }

  // --- Reference ---
  async getRouteMetadata() {
    return this.request('/api/v1/routes');
  }

  // --- Index & Series ---
  async getHeadlineIndex(params) {
    const query = new URLSearchParams();
    if (params?.freq) query.set('freq', params.freq);
    if (params?.dowAdjusted) query.set('dow_adjusted', 'true');
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request(`/api/v1/index${qs ? `?${qs}` : ''}`);
  }

  async getRoutesSummary() {
    return this.request('/api/v1/index/routes');
  }

  async getRouteSeries(routeCode) {
    return this.request(`/api/v1/index/routes/${encodeURIComponent(routeCode)}`);
  }

  async getRouteHeatmap(params) {
    const query = new URLSearchParams();
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request(`/api/v1/index/routes/heatmap${qs ? `?${qs}` : ''}`);
  }

  async getLeadtimeIndex() {
    return this.request('/api/v1/index/leadtime');
  }

  async getLeadtimeCurve(asOf) {
    const qs = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
    return this.request(`/api/v1/index/leadtime/curve${qs}`);
  }

  async getVolatility() {
    return this.request('/api/v1/index/volatility');
  }

  // --- Validation ---
  async getValidationDgca() {
    return this.request('/api/v1/validation/dgca');
  }
}

export const api = new ApiClient();
