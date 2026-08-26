/**
 * AIPI Normalized API Client
 * 
 * Intercepts network calls, parses uniform { error, detail } envelopes,
 * and delivers strictly-typed responses across all 12 backend endpoints.
 */

import {
  ErrorResponse,
  HeadlineResponse,
  HealthResponse,
  HeatmapResponse,
  LeadtimeCurveResponse,
  LeadtimeIndexResponse,
  MethodologyResponse,
  PipelineRunModel,
  RouteMetadataResponse,
  RouteResponse,
  RoutesResponse,
  ValidationResponse,
  VolatilityResponse
} from '../types/api.js';

export class ApiError extends Error {
  public readonly statusCode: number;
  public readonly errorCode: string;
  public readonly detail: string;

  constructor(statusCode: number, errorCode: string, detail: string) {
    super(`${statusCode} [${errorCode}]: ${detail}`);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.detail = detail;
  }
}

class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl = '') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
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
        const errorBody = (await response.json()) as ErrorResponse;
        errorCode = errorBody.error || errorCode;
        detail = errorBody.detail || detail;
      } catch {
        // Fall back to statusText if body is not JSON
      }

      throw new ApiError(response.status, errorCode, detail);
    }

    return (await response.json()) as T;
  }

  // --- Ops ---
  public async getHealth(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // --- Methodology & Provenance ---
  public async getMethodology(): Promise<MethodologyResponse> {
    return this.request<MethodologyResponse>('/api/v1/methodology');
  }

  public async getPipelineRun(): Promise<PipelineRunModel> {
    return this.request<PipelineRunModel>('/api/v1/pipeline-run');
  }

  // --- Reference ---
  public async getRouteMetadata(): Promise<RouteMetadataResponse> {
    return this.request<RouteMetadataResponse>('/api/v1/routes');
  }

  // --- Index & Series ---
  public async getHeadlineIndex(params?: {
    freq?: 'daily' | 'weekly' | 'monthly';
    dowAdjusted?: boolean;
    from?: string;
    to?: string;
  }): Promise<HeadlineResponse> {
    const query = new URLSearchParams();
    if (params?.freq) query.set('freq', params.freq);
    if (params?.dowAdjusted) query.set('dow_adjusted', 'true');
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request<HeadlineResponse>(`/api/v1/index${qs ? `?${qs}` : ''}`);
  }

  public async getRoutesSummary(): Promise<RoutesResponse> {
    return this.request<RoutesResponse>('/api/v1/index/routes');
  }

  public async getRouteSeries(routeCode: string): Promise<RouteResponse> {
    return this.request<RouteResponse>(`/api/v1/index/routes/${encodeURIComponent(routeCode)}`);
  }

  public async getRouteHeatmap(params?: { from?: string; to?: string }): Promise<HeatmapResponse> {
    const query = new URLSearchParams();
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request<HeatmapResponse>(`/api/v1/index/routes/heatmap${qs ? `?${qs}` : ''}`);
  }

  public async getLeadtimeIndex(): Promise<LeadtimeIndexResponse> {
    return this.request<LeadtimeIndexResponse>('/api/v1/index/leadtime');
  }

  public async getLeadtimeCurve(asOf?: string): Promise<LeadtimeCurveResponse> {
    const qs = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
    return this.request<LeadtimeCurveResponse>(`/api/v1/index/leadtime/curve${qs}`);
  }

  public async getVolatility(): Promise<VolatilityResponse> {
    return this.request<VolatilityResponse>('/api/v1/index/volatility');
  }

  // --- Validation ---
  public async getValidationDgca(): Promise<ValidationResponse> {
    return this.request<ValidationResponse>('/api/v1/validation/dgca');
  }
}

export const api = new ApiClient();
