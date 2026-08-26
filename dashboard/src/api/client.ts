/**
 * AIPI Normalized API Client
 *
 * Intercepts network calls, parses uniform { error, detail } envelopes,
 * and delivers strictly-typed responses across all 12 backend endpoints.
 *
 * Every accessor accepts an optional trailing AbortSignal so callers can
 * cancel in-flight requests without letting a stale response overwrite
 * newer state.
 */

import {
  ErrorResponse,
  HeadlineResponse,
  HealthResponse,
  HeatmapResponse,
  LeadtimeCurveResponse,
  LeadtimeIndexResponse,
  MethodologyResponse,
  OpenApiSpec,
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
  public async getHealth(signal?: AbortSignal): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health', { signal });
  }

  //: FastAPI auto-serves this from the live app's route table — the actual
  //: OpenAPI/backend version and endpoint count, not a value baked into the
  //: frontend build.
  public async getOpenApiSpec(signal?: AbortSignal): Promise<OpenApiSpec> {
    return this.request<OpenApiSpec>('/openapi.json', { signal });
  }

  // --- Methodology & Provenance ---
  public async getMethodology(signal?: AbortSignal): Promise<MethodologyResponse> {
    return this.request<MethodologyResponse>('/api/v1/methodology', { signal });
  }

  public async getPipelineRun(signal?: AbortSignal): Promise<PipelineRunModel> {
    return this.request<PipelineRunModel>('/api/v1/pipeline-run', { signal });
  }

  // --- Reference ---
  public async getRouteMetadata(signal?: AbortSignal): Promise<RouteMetadataResponse> {
    return this.request<RouteMetadataResponse>('/api/v1/routes', { signal });
  }

  // --- Index & Series ---
  public async getHeadlineIndex(
    params?: {
      freq?: 'daily' | 'weekly' | 'monthly';
      dowAdjusted?: boolean;
      from?: string;
      to?: string;
    },
    signal?: AbortSignal
  ): Promise<HeadlineResponse> {
    const query = new URLSearchParams();
    if (params?.freq) query.set('freq', params.freq);
    if (params?.dowAdjusted) query.set('dow_adjusted', 'true');
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request<HeadlineResponse>(`/api/v1/index${qs ? `?${qs}` : ''}`, { signal });
  }

  public async getRoutesSummary(signal?: AbortSignal): Promise<RoutesResponse> {
    return this.request<RoutesResponse>('/api/v1/index/routes', { signal });
  }

  public async getRouteSeries(routeCode: string, signal?: AbortSignal): Promise<RouteResponse> {
    return this.request<RouteResponse>(`/api/v1/index/routes/${encodeURIComponent(routeCode)}`, { signal });
  }

  public async getRouteHeatmap(params?: { from?: string; to?: string }, signal?: AbortSignal): Promise<HeatmapResponse> {
    const query = new URLSearchParams();
    if (params?.from) query.set('from', params.from);
    if (params?.to) query.set('to', params.to);

    const qs = query.toString();
    return this.request<HeatmapResponse>(`/api/v1/index/routes/heatmap${qs ? `?${qs}` : ''}`, { signal });
  }

  public async getLeadtimeIndex(signal?: AbortSignal): Promise<LeadtimeIndexResponse> {
    return this.request<LeadtimeIndexResponse>('/api/v1/index/leadtime', { signal });
  }

  public async getLeadtimeCurve(asOf?: string, signal?: AbortSignal): Promise<LeadtimeCurveResponse> {
    const qs = asOf ? `?as_of=${encodeURIComponent(asOf)}` : '';
    return this.request<LeadtimeCurveResponse>(`/api/v1/index/leadtime/curve${qs}`, { signal });
  }

  public async getVolatility(signal?: AbortSignal): Promise<VolatilityResponse> {
    return this.request<VolatilityResponse>('/api/v1/index/volatility', { signal });
  }

  // --- Validation ---
  public async getValidationDgca(signal?: AbortSignal): Promise<ValidationResponse> {
    return this.request<ValidationResponse>('/api/v1/validation/dgca', { signal });
  }
}

export const api = new ApiClient();
