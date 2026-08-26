/**
 * AIPI Screen 7: Live API Explorer & Contract Inspector
 *
 * Internal technical inspection console for verified read-only backend endpoints.
 */

import { api, ApiError } from '../api/client.js';
import { EnterpriseTable, TableColumn } from '../components/EnterpriseTable.js';
import { HealthResponse, OpenApiSpec, RouteMetadataResponse } from '../types/api.js';
import { htmlToElement } from '../utils/dom.js';

type ParamLocation = 'query' | 'path';

interface ContractParameter {
  name: string;
  location: ParamLocation;
  required: boolean;
  type: string;
  defaultValue?: string;
  description?: string;
  allowedValues?: string[];
}

interface ContractEndpoint {
  id: string;
  method: 'GET';
  path: string;
  category: 'ops' | 'index' | 'reference' | 'methodology' | 'validation';
  summary: string;
  description: string;
  purpose: string;
  parameters: ContractParameter[];
  requestSchema: string;
  responseSchema: string;
  responseFields: string[];
  errorResponses: Array<{ status: number; envelope: string; detail: string }>;
  authentication: string;
  validationRules: string[];
  notes?: string[];
  defaultPathParams?: Record<string, string>;
}

interface ExplorerRow {
  id: string;
  method: string;
  path: string;
  category: string;
  description: string;
  status: string;
}

interface InspectorResponse {
  status: number | null;
  latencyMs: number | null;
  headers: Record<string, string>;
  sizeBytes: number;
  json: unknown;
  url: string;
  ok: boolean;
}

export interface ApiExplorerCallbacks {
  onNotify?: (type: 'success' | 'warning' | 'error' | 'info', title: string, message?: string) => void;
}

const ERROR_ENVELOPE = `{
  "error": "...",
  "detail": "..."
}`;

const ENDPOINTS: ContractEndpoint[] = [
  {
    id: 'health',
    method: 'GET',
    path: '/health',
    category: 'ops',
    summary: 'Health',
    description: 'Backend health, data availability, version, latest index age, and data mode.',
    purpose: 'Confirms API reachability and reports whether the warmed index store has data.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'HealthResponse',
    responseFields: ['status', 'data_available', 'latest_index_date', 'code_version', 'data_mode?', 'hours_since_latest_index?'],
    errorResponses: [],
    authentication: 'None',
    validationRules: ['No request parameters are accepted.']
  },
  {
    id: 'methodology',
    method: 'GET',
    path: '/api/v1/methodology',
    category: 'methodology',
    summary: 'Methodology',
    description: 'Basket, formulae, methodology fingerprint, cleaning row accounting, diagnostics, and notes.',
    purpose: 'Publishes the statistical methodology dossier that explains how the index is constructed.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'object',
    responseFields: ['title', 'disclaimer', 'index_number', 'fingerprint', 'base_period', 'diagnostics', 'route_weights', 'cleaning', 'notes'],
    errorResponses: [{ status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }],
    authentication: 'None',
    validationRules: ['Requires available index data.']
  },
  {
    id: 'pipeline-run',
    method: 'GET',
    path: '/api/v1/pipeline-run',
    category: 'methodology',
    summary: 'Pipeline Run',
    description: 'Active run provenance stamp.',
    purpose: 'Returns reproducibility metadata for the current pipeline run.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'PipelineRunModel',
    responseFields: ['run_id', 'code_version', 'git_sha', 'config_hash', 'input_row_count', 'index_eligible_rows', 'created_at'],
    errorResponses: [{ status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }],
    authentication: 'None',
    validationRules: ['Requires available index data.']
  },
  {
    id: 'headline',
    method: 'GET',
    path: '/api/v1/index',
    category: 'index',
    summary: 'Headline',
    description: 'National headline index series with optional frequency, date range, and day-of-week adjustment.',
    purpose: 'Returns the composite AIPI time series and supporting provenance.',
    parameters: [
      { name: 'dow_adjusted', location: 'query', required: false, type: 'boolean', defaultValue: 'false', description: 'Return the day-of-week-adjusted series.' },
      { name: 'freq', location: 'query', required: false, type: 'string', defaultValue: 'daily', description: 'daily | weekly | monthly', allowedValues: ['daily', 'weekly', 'monthly'] },
      { name: 'from', location: 'query', required: false, type: 'date string | null', description: 'Inclusive start date.' },
      { name: 'to', location: 'query', required: false, type: 'date string | null', description: 'Inclusive end date.' }
    ],
    requestSchema: 'None',
    responseSchema: 'HeadlineResponse',
    responseFields: ['series', 'freq', 'dow_adjusted', 'base_period', 'pipeline_run', 'data_mode', 'count', 'points[]'],
    errorResponses: [
      { status: 422, envelope: ERROR_ENVELOPE, detail: 'Invalid freq or incompatible dow_adjusted/freq combination.' },
      { status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }
    ],
    authentication: 'None',
    validationRules: ['freq must be one of daily, weekly, monthly.', 'dow_adjusted applies only to freq=daily.', 'from and to must parse as dates when provided.']
  },
  {
    id: 'route-metadata',
    method: 'GET',
    path: '/api/v1/routes',
    category: 'reference',
    summary: 'Route Metadata',
    description: 'Route dimension for dropdowns and filters. Identity only, no series.',
    purpose: 'Lists route metadata for UI selectors and reference lookup.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'RouteMetadataResponse',
    responseFields: ['count', 'routes[]'],
    errorResponses: [{ status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }],
    authentication: 'None',
    validationRules: ['Requires available index data.']
  },
  {
    id: 'routes-summary',
    method: 'GET',
    path: '/api/v1/index/routes',
    category: 'index',
    summary: 'Routes',
    description: 'Latest route-level index summaries.',
    purpose: 'Returns all route summary rows used by the route analytics directory.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'RoutesResponse',
    responseFields: ['pipeline_run', 'count', 'routes[]'],
    errorResponses: [{ status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }],
    authentication: 'None',
    validationRules: ['Requires available index data.']
  },
  {
    id: 'route-heatmap',
    method: 'GET',
    path: '/api/v1/index/routes/heatmap',
    category: 'index',
    summary: 'Route Heatmap',
    description: 'Route x date matrix for the sector-wise heatmap.',
    purpose: 'Returns a pre-shaped route/date matrix for heatmap rendering.',
    parameters: [
      { name: 'from', location: 'query', required: false, type: 'date string | null' },
      { name: 'to', location: 'query', required: false, type: 'date string | null' }
    ],
    requestSchema: 'None',
    responseSchema: 'HeatmapResponse',
    responseFields: ['routes[]', 'route_names[]', 'dates[]', 'matrix[][]', 'value_min', 'value_max', 'baseline', 'note', 'data_mode'],
    errorResponses: [
      { status: 422, envelope: ERROR_ENVELOPE, detail: 'Date parsing validation error.' },
      { status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }
    ],
    authentication: 'None',
    validationRules: ['from and to must parse as dates when provided.', 'matrix[i][j] maps routes[i] to dates[j]; null means no index value.']
  },
  {
    id: 'route-series',
    method: 'GET',
    path: '/api/v1/index/routes/{route_code}',
    category: 'index',
    summary: 'Route',
    description: 'Single route-level index series.',
    purpose: 'Returns one route trajectory and its latest route metadata.',
    parameters: [
      { name: 'route_code', location: 'path', required: true, type: 'string' }
    ],
    requestSchema: 'None',
    responseSchema: 'RouteResponse',
    responseFields: ['route_code', 'display_name', 'weight', 'pipeline_run', 'count', 'points[]'],
    errorResponses: [
      { status: 404, envelope: ERROR_ENVELOPE, detail: 'Unknown route: {route_code}' },
      { status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }
    ],
    authentication: 'None',
    validationRules: ['route_code is required in the path.'],
    defaultPathParams: { route_code: 'DEL-BOM' }
  },
  {
    id: 'leadtime',
    method: 'GET',
    path: '/api/v1/index/leadtime',
    category: 'index',
    summary: 'Leadtime',
    description: 'Index by advance-purchase window. This is not the fare-level curve.',
    purpose: 'Shows how fast each advance purchase window is inflating.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'LeadtimeIndexResponse',
    responseFields: ['note', 'pipeline_run', 'windows[]'],
    errorResponses: [{ status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }],
    authentication: 'None',
    validationRules: ['Requires available index data.']
  },
  {
    id: 'leadtime-curve',
    method: 'GET',
    path: '/api/v1/index/leadtime/curve',
    category: 'index',
    summary: 'Leadtime Curve',
    description: 'Relative fare level by advance window. 14-day window equals 100.',
    purpose: 'Shows the level premium or discount across booking lead times.',
    parameters: [
      { name: 'as_of', location: 'query', required: false, type: 'date string | null', description: 'Curve as at this date; latest if omitted.' }
    ],
    requestSchema: 'None',
    responseSchema: 'LeadtimeCurveResponse',
    responseFields: ['as_of', 'reference_window', 'note?', 'curve[]'],
    errorResponses: [
      { status: 422, envelope: ERROR_ENVELOPE, detail: 'Date parsing validation error.' },
      { status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }
    ],
    authentication: 'None',
    validationRules: ['as_of must parse as a date when provided.']
  },
  {
    id: 'volatility',
    method: 'GET',
    path: '/api/v1/index/volatility',
    category: 'index',
    summary: 'Volatility',
    description: 'Daily and intraday fare volatility plus sparse-sampling measurement-error analysis.',
    purpose: 'Publishes volatility and sparse collection error diagnostics.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'object',
    responseFields: ['daily', 'intraday', 'sampling_error?'],
    errorResponses: [{ status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }],
    authentication: 'None',
    validationRules: ['Requires available index data.']
  },
  {
    id: 'validation-dgca',
    method: 'GET',
    path: '/api/v1/validation/dgca',
    category: 'validation',
    summary: 'Validation Dgca',
    description: 'Back-test against the reference series with lineage stated up front.',
    purpose: 'Returns validation diagnostics against the DGCA benchmark state.',
    parameters: [],
    requestSchema: 'None',
    responseSchema: 'object',
    responseFields: ['available flag is returned by store validation payload when applicable', 'backend returns object'],
    errorResponses: [{ status: 503, envelope: ERROR_ENVELOPE, detail: 'No index data available yet.' }],
    authentication: 'None',
    validationRules: ['Requires available index data.']
  }
];

export class ApiExplorerPage {
  private container: HTMLElement | null = null;
  private callbacks: ApiExplorerCallbacks;
  private selectedEndpoint = ENDPOINTS[0];
  private searchQuery = '';
  private categoryFilter = 'all';
  private health: HealthResponse | null = null;
  private lastHealthLatency: number | null = null;
  private lastHealthUpdated: string | null = null;
  //: Fetched live from GET /openapi.json (FastAPI's auto-generated spec). Not
  //: hardcoded — null means the live spec has not been reached yet.
  private openapiSpec: OpenApiSpec | null = null;
  private routeFallback = 'DEL-BOM';
  private inspector: InspectorResponse | null = null;
  private table = new EnterpriseTable<ExplorerRow>();

  constructor(callbacks: ApiExplorerCallbacks = {}) {
    this.callbacks = callbacks;
  }

  public render(container: HTMLElement): void {
    this.container = container;
    this.renderContent();
    this.refreshHealth();
    this.loadRouteFallback();
    this.loadOpenApiSpec();
  }

  private async loadOpenApiSpec(): Promise<void> {
    try {
      this.openapiSpec = await api.getOpenApiSpec();
      this.renderContent();
    } catch {
      // Live spec unreachable; status card falls back to an honest "unverified" state.
      this.openapiSpec = null;
    }
  }

  public async refreshHealth(): Promise<void> {
    const start = performance.now();
    try {
      this.health = await api.getHealth();
      this.lastHealthLatency = Math.round(performance.now() - start);
      this.lastHealthUpdated = new Date().toLocaleString();
      this.renderContent();
    } catch (err) {
      this.health = null;
      this.lastHealthLatency = Math.round(performance.now() - start);
      this.lastHealthUpdated = new Date().toLocaleString();
      this.callbacks.onNotify?.('error', 'Health Check Failed', err instanceof ApiError ? err.detail : String(err));
      this.renderContent();
    }
  }

  public async executeSelected(): Promise<void> {
    const endpoint = this.selectedEndpoint;
    const form = this.container?.querySelector<HTMLFormElement>('#api-request-form');
    const formData = form ? new FormData(form) : new FormData();
    const path = this.resolvePath(endpoint, formData);
    const url = this.buildUrl(path, endpoint, formData);
    const start = performance.now();

    try {
      const response = await fetch(url, { headers: { Accept: 'application/json' } });
      const text = await response.text();
      const latency = Math.round(performance.now() - start);
      let json: unknown = text;
      try {
        json = text ? JSON.parse(text) : null;
      } catch {
        json = text;
      }

      this.inspector = {
        status: response.status,
        latencyMs: latency,
        headers: this.safeHeaders(response.headers),
        sizeBytes: new Blob([text]).size,
        json,
        url,
        ok: response.ok
      };
      this.callbacks.onNotify?.(response.ok ? 'success' : 'warning', `GET ${response.status}`, `${endpoint.path} completed in ${latency}ms`);
      this.renderContent();
    } catch (err) {
      this.inspector = {
        status: null,
        latencyMs: Math.round(performance.now() - start),
        headers: {},
        sizeBytes: 0,
        json: { error: 'network_error', detail: String(err) },
        url,
        ok: false
      };
      this.callbacks.onNotify?.('error', 'Request Failed', String(err));
      this.renderContent();
    }
  }

  private async loadRouteFallback(): Promise<void> {
    try {
      const meta: RouteMetadataResponse = await api.getRouteMetadata();
      const first = meta.routes?.[0]?.route_code;
      if (first) {
        this.routeFallback = first;
        if (this.selectedEndpoint.id === 'route-series') this.renderContent();
      }
    } catch {
      // The verified static fallback remains usable for contract inspection.
    }
  }

  private renderContent(): void {
    if (!this.container) return;

    const page = htmlToElement(`
      <div class="api-explorer-page">
        <section class="api-status-grid" aria-label="API contract summary">
          ${this.renderStatusCard('Backend Version', this.health?.code_version || 'unreachable', this.health ? 'Live from GET /health' : 'Awaiting health response')}
          ${this.renderStatusCard('OpenAPI Version', this.openapiSpec?.openapi || 'unreachable', this.openapiSpec ? 'Live from GET /openapi.json' : 'Awaiting live spec response')}
          ${this.renderStatusCard('API Status', this.health?.status || 'unreachable', this.health ? 'Health endpoint returned JSON' : 'Awaiting health response')}
          ${this.renderStatusCard('Verified Endpoints', String(ENDPOINTS.length), this.endpointCountHint())}
        </section>

        <section class="card-container" aria-labelledby="health-heading">
          <div class="card-header">
            <div>
              <h2 class="card-title" id="health-heading">Backend Health</h2>
              <p class="card-subtitle">Live status consumed from GET /health.</p>
            </div>
            <button class="empty-state-action-btn" id="api-health-refresh-btn" type="button">Refresh Health</button>
          </div>
          <div class="api-health-grid">
            ${this.renderHealthMetric('Backend Status', this.health?.status || 'unreachable')}
            ${this.renderHealthMetric('API Reachability', this.health ? 'reachable' : 'unreachable')}
            ${this.renderHealthMetric('Response Time', this.lastHealthLatency != null ? `${this.lastHealthLatency}ms` : 'pending')}
            ${this.renderHealthMetric('Last Updated', this.lastHealthUpdated || 'pending')}
            ${this.renderHealthMetric('Data Mode', this.health?.data_mode ? (this.health.data_mode.is_demo_data ? 'demo data' : 'measured data') : 'unavailable')}
          </div>
        </section>

        <div class="api-explorer-layout">
          <aside class="api-directory-pane" aria-labelledby="directory-heading">
            <section class="card-container api-sticky-panel">
              <div class="card-header">
                <div>
                  <h2 class="card-title" id="directory-heading">Endpoint Directory</h2>
                  <p class="card-subtitle">Searchable verified backend routes.</p>
                </div>
              </div>
              <div class="api-filter-row">
                <label class="filter-input-group" for="api-search-input">
                  <span>Search</span>
                  <input class="filter-input api-search-input" id="api-search-input" type="search" value="${this.escapeAttr(this.searchQuery)}" />
                </label>
                <label class="filter-input-group" for="api-category-filter">
                  <span>Category</span>
                  <select class="filter-input" id="api-category-filter">
                    ${['all', 'ops', 'index', 'reference', 'methodology', 'validation'].map((cat) => `<option value="${cat}" ${this.categoryFilter === cat ? 'selected' : ''}>${cat}</option>`).join('')}
                  </select>
                </label>
              </div>
              <div id="api-directory-table"></div>
            </section>
          </aside>

          <div class="api-detail-stack">
            ${this.renderDetailPanel()}
            ${this.renderLiveConsole()}
            ${this.renderSchemaViewer()}
            ${this.renderResponseInspector()}
            ${this.renderErrorDemo()}
            ${this.renderDeveloperNotes()}
          </div>
        </div>
      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);
    this.attachListeners(page);
    this.renderDirectoryTable(page);
  }

  //: Cross-checks the curated ENDPOINTS directory against the live spec's path
  //: count so a drift between the two is visible rather than silently claimed
  //: as "verified".
  private endpointCountHint(): string {
    if (!this.openapiSpec) return 'GET-only public API surface (curated directory; live spec unverified)';
    const livePathCount = Object.keys(this.openapiSpec.paths || {}).length;
    return livePathCount === ENDPOINTS.length
      ? `Matches live /openapi.json path count (${livePathCount})`
      : `Live /openapi.json reports ${livePathCount} paths; curated directory has ${ENDPOINTS.length}`;
  }

  private renderStatusCard(label: string, value: string, hint: string): string {
    return `
      <div class="stat-card">
        <span class="text-label">${label}</span>
        <span class="metric-medium">${value}</span>
        <span class="text-small" style="color: var(--color-text-tertiary);">${hint}</span>
      </div>
    `;
  }

  private renderHealthMetric(label: string, value: string): string {
    return `
      <div class="quality-metric-row">
        <span class="quality-label">${label}</span>
        <span class="quality-value">${value}</span>
      </div>
    `;
  }

  private renderDetailPanel(): string {
    const endpoint = this.selectedEndpoint;
    const queryParams = endpoint.parameters.filter((p) => p.location === 'query');
    const pathParams = endpoint.parameters.filter((p) => p.location === 'path');
    return `
      <section class="card-container" aria-labelledby="endpoint-detail-heading">
        <div class="card-header">
          <div>
            <h2 class="card-title" id="endpoint-detail-heading">Endpoint Detail Panel</h2>
            <p class="card-subtitle">${endpoint.summary} contract details from backend implementation.</p>
          </div>
          <button class="empty-state-action-btn" id="copy-endpoint-btn" type="button">Copy Endpoint</button>
        </div>
        <div class="api-endpoint-title">
          <span class="api-method-badge">${endpoint.method}</span>
          <code>${endpoint.path}</code>
          <span class="badge badge-neutral">${endpoint.category}</span>
        </div>
        <div class="api-contract-grid">
          ${this.renderContractBlock('Purpose', [endpoint.purpose])}
          ${this.renderContractBlock('Query Parameters', queryParams.length ? queryParams.map((p) => this.formatParam(p)) : ['None'])}
          ${this.renderContractBlock('Path Parameters', pathParams.length ? pathParams.map((p) => this.formatParam(p)) : ['None'])}
          ${this.renderContractBlock('Request Schema', [endpoint.requestSchema])}
          ${this.renderContractBlock('Response Structure', [`${endpoint.responseSchema}: ${endpoint.responseFields.join(', ')}`])}
          ${this.renderContractBlock('Error Envelope', endpoint.errorResponses.length ? endpoint.errorResponses.map((e) => `${e.status}: ${e.envelope} ${e.detail}`) : ['No route-specific error response declared.'])}
          ${this.renderContractBlock('Authentication', [endpoint.authentication])}
          ${this.renderContractBlock('Validation Rules', endpoint.validationRules)}
        </div>
      </section>
    `;
  }

  private renderContractBlock(title: string, values: string[]): string {
    return `
      <div class="api-contract-block">
        <div class="text-label">${title}</div>
        <ul>
          ${values.map((v) => `<li>${this.escapeHtml(v)}</li>`).join('')}
        </ul>
      </div>
    `;
  }

  private renderLiveConsole(): string {
    const endpoint = this.selectedEndpoint;
    return `
      <section class="card-container" aria-labelledby="live-console-heading">
        <div class="card-header">
          <div>
            <h2 class="card-title" id="live-console-heading">Live Request Console</h2>
            <p class="card-subtitle">GET requests only. This console cannot edit backend state.</p>
          </div>
          <button class="empty-state-action-btn" id="execute-api-btn" type="button">Execute GET</button>
        </div>
        <form id="api-request-form" class="api-request-form">
          ${endpoint.parameters.length ? endpoint.parameters.map((p) => this.renderParameterControl(p, endpoint)).join('') : '<p class="text-body-muted">This endpoint accepts no parameters.</p>'}
        </form>
        <div class="api-url-preview" aria-live="polite">
          <span class="text-label">Request URL</span>
          <code>${this.escapeHtml(this.previewUrl(endpoint))}</code>
        </div>
      </section>
    `;
  }

  private renderParameterControl(param: ContractParameter, endpoint: ContractEndpoint): string {
    const current = endpoint.defaultPathParams?.[param.name] || (param.name === 'route_code' ? this.routeFallback : param.defaultValue || '');
    const label = `${param.location}: ${param.name}`;
    if (param.allowedValues) {
      return `
        <label class="filter-input-group api-param-control">
          <span>${label}</span>
          <select class="filter-input" name="${param.name}" aria-label="${label}">
            ${param.allowedValues.map((v) => `<option value="${v}" ${v === current ? 'selected' : ''}>${v}</option>`).join('')}
          </select>
        </label>
      `;
    }
    if (param.type === 'boolean') {
      return `
        <label class="toggle-label api-param-control">
          <input type="checkbox" name="${param.name}" ${current === 'true' ? 'checked' : ''} />
          <span>${label}</span>
        </label>
      `;
    }
    const inputType = param.type.includes('date') ? 'date' : 'text';
    return `
      <label class="filter-input-group api-param-control">
        <span>${label}</span>
        <input class="filter-input" type="${inputType}" name="${param.name}" value="${this.escapeAttr(current)}" aria-label="${label}" />
      </label>
    `;
  }

  private renderSchemaViewer(): string {
    const endpoint = this.selectedEndpoint;
    const schema = {
      method: endpoint.method,
      path: endpoint.path,
      request_schema: endpoint.requestSchema,
      response_schema: endpoint.responseSchema,
      response_fields: endpoint.responseFields,
      parameters: endpoint.parameters,
      error_responses: endpoint.errorResponses,
      authentication: endpoint.authentication
    };
    return `
      <section class="card-container" aria-labelledby="schema-heading">
        <div class="card-header">
          <div>
            <h2 class="card-title" id="schema-heading">Schema Viewer</h2>
            <p class="card-subtitle">Collapsible contract tree for the selected endpoint.</p>
          </div>
          <button class="empty-state-action-btn" id="copy-schema-btn" type="button">Copy JSON</button>
        </div>
        <details class="api-schema-tree" open>
          <summary>${endpoint.responseSchema}</summary>
          <pre id="schema-json">${this.escapeHtml(JSON.stringify(schema, null, 2))}</pre>
        </details>
      </section>
    `;
  }

  private renderResponseInspector(): string {
    const result = this.inspector;
    return `
      <section class="card-container" aria-labelledby="response-heading">
        <div class="card-header">
          <div>
            <h2 class="card-title" id="response-heading">Response Inspector</h2>
            <p class="card-subtitle">HTTP status, safe headers, byte size, latency, and formatted JSON.</p>
          </div>
          <button class="empty-state-action-btn" id="copy-response-btn" type="button" ${result ? '' : 'disabled'}>Copy JSON</button>
        </div>
        <div class="api-response-meta">
          ${this.renderHealthMetric('HTTP Status', result?.status != null ? String(result.status) : 'not executed')}
          ${this.renderHealthMetric('Latency', result?.latencyMs != null ? `${result.latencyMs}ms` : 'not executed')}
          ${this.renderHealthMetric('Response Size', result ? `${result.sizeBytes} bytes` : 'not executed')}
          ${this.renderHealthMetric('Request URL', result?.url || 'not executed')}
        </div>
        <details class="api-schema-tree" open>
          <summary>Safe Headers</summary>
          <pre>${this.escapeHtml(JSON.stringify(result?.headers || {}, null, 2))}</pre>
        </details>
        <details class="api-schema-tree" open>
          <summary>Formatted JSON</summary>
          <pre id="response-json">${this.escapeHtml(JSON.stringify(result?.json || { status: 'awaiting_request' }, null, 2))}</pre>
        </details>
      </section>
    `;
  }

  private renderErrorDemo(): string {
    return `
      <section class="card-container" aria-labelledby="error-demo-heading">
        <div class="card-header">
          <div>
            <h2 class="card-title" id="error-demo-heading">Error Demonstration</h2>
            <p class="card-subtitle">Uniform backend error envelope used by API client parsing.</p>
          </div>
          <button class="empty-state-action-btn" id="run-error-demo-btn" type="button">Run 422 Demo</button>
        </div>
        <pre class="api-error-envelope">${ERROR_ENVELOPE}</pre>
      </section>
    `;
  }

  private renderDeveloperNotes(): string {
    const notes = this.selectedEndpoint.notes || [];
    if (!notes.length) return '';
    return `
      <section class="card-container" aria-labelledby="dev-notes-heading">
        <div class="card-header">
          <div>
            <h2 class="card-title" id="dev-notes-heading">Developer Notes</h2>
            <p class="card-subtitle">Backend notes available for this endpoint.</p>
          </div>
        </div>
        <ul class="api-notes-list">${notes.map((n) => `<li>${this.escapeHtml(n)}</li>`).join('')}</ul>
      </section>
    `;
  }

  private renderDirectoryTable(root: HTMLElement): void {
    const mount = root.querySelector<HTMLElement>('#api-directory-table');
    if (!mount) return;
    const rows = this.filteredEndpoints().map((e) => ({
      id: e.id,
      method: e.method,
      path: e.path,
      category: e.category,
      description: e.description,
      status: 'verified'
    }));
    const cols: TableColumn<ExplorerRow>[] = [
      { key: 'method', label: 'Method', width: '80px', render: (row) => `<span class="api-method-badge">${row.method}</span>` },
      { key: 'path', label: 'Endpoint', width: '220px', render: (row) => `<code>${row.path}</code>` },
      { key: 'category', label: 'Category', width: '120px' },
      { key: 'description', label: 'Description' },
      { key: 'status', label: 'Status', width: '100px', render: (row) => `<span class="badge badge-success">${row.status}</span>` }
    ];
    this.table.render(mount, {
      columns: cols,
      data: rows,
      keyField: 'id',
      searchQuery: this.searchQuery,
      searchFields: ['path', 'category', 'description'],
      onRowClick: (row) => {
        const endpoint = ENDPOINTS.find((e) => e.id === row.id);
        if (endpoint) {
          this.selectedEndpoint = endpoint;
          this.inspector = null;
          this.renderContent();
        }
      },
      emptyMessage: 'No verified endpoint matches the current filters.'
    });
  }

  private attachListeners(root: HTMLElement): void {
    root.querySelector('#api-health-refresh-btn')?.addEventListener('click', () => this.refreshHealth());
    root.querySelector('#execute-api-btn')?.addEventListener('click', () => this.executeSelected());
    root.querySelector('#run-error-demo-btn')?.addEventListener('click', () => {
      this.selectedEndpoint = ENDPOINTS.find((e) => e.id === 'headline') || this.selectedEndpoint;
      this.renderContent();
      const freq = this.container?.querySelector<HTMLSelectElement>('select[name="freq"]');
      const dow = this.container?.querySelector<HTMLInputElement>('input[name="dow_adjusted"]');
      if (freq) freq.value = 'weekly';
      if (dow) dow.checked = true;
      this.executeSelected();
    });
    root.querySelector('#copy-endpoint-btn')?.addEventListener('click', () => this.copyText(this.selectedEndpoint.path, 'Endpoint copied'));
    root.querySelector('#copy-schema-btn')?.addEventListener('click', () => this.copyElementText('#schema-json', 'Schema JSON copied'));
    root.querySelector('#copy-response-btn')?.addEventListener('click', () => this.copyElementText('#response-json', 'Response JSON copied'));
    root.querySelector('#api-search-input')?.addEventListener('input', (event) => {
      this.searchQuery = (event.target as HTMLInputElement).value;
      this.renderDirectoryTable(root);
    });
    root.querySelector('#api-category-filter')?.addEventListener('change', (event) => {
      this.categoryFilter = (event.target as HTMLSelectElement).value;
      this.renderDirectoryTable(root);
    });
  }

  private filteredEndpoints(): ContractEndpoint[] {
    return ENDPOINTS.filter((e) => this.categoryFilter === 'all' || e.category === this.categoryFilter);
  }

  private previewUrl(endpoint: ContractEndpoint): string {
    let path = endpoint.path;
    if (endpoint.defaultPathParams?.route_code || endpoint.path.includes('{route_code}')) {
      path = path.replace('{route_code}', endpoint.defaultPathParams?.route_code || this.routeFallback);
    }
    return path;
  }

  private resolvePath(endpoint: ContractEndpoint, formData: FormData): string {
    let path = endpoint.path;
    endpoint.parameters.filter((p) => p.location === 'path').forEach((param) => {
      const value = String(formData.get(param.name) || endpoint.defaultPathParams?.[param.name] || this.routeFallback);
      path = path.replace(`{${param.name}}`, encodeURIComponent(value));
    });
    return path;
  }

  private buildUrl(path: string, endpoint: ContractEndpoint, formData: FormData): string {
    const query = new URLSearchParams();
    endpoint.parameters.filter((p) => p.location === 'query').forEach((param) => {
      const value = formData.get(param.name);
      if (value === null || value === '') return;
      if (param.type === 'boolean') {
        query.set(param.name, 'true');
      } else {
        query.set(param.name, String(value));
      }
    });
    const qs = query.toString();
    return `${path}${qs ? `?${qs}` : ''}`;
  }

  private safeHeaders(headers: Headers): Record<string, string> {
    const safe = ['content-type', 'content-length', 'date', 'server', 'cache-control', 'etag'];
    const result: Record<string, string> = {};
    headers.forEach((value, key) => {
      if (safe.includes(key.toLowerCase())) result[key] = value;
    });
    return result;
  }

  private formatParam(param: ContractParameter): string {
    const required = param.required ? 'required' : 'optional';
    const allowed = param.allowedValues ? ` allowed: ${param.allowedValues.join(', ')}` : '';
    const def = param.defaultValue ? ` default: ${param.defaultValue}` : '';
    const desc = param.description ? ` ${param.description}` : '';
    return `${param.name} (${param.location}, ${param.type}, ${required})${def}.${allowed}${desc}`;
  }

  private async copyElementText(selector: string, message: string): Promise<void> {
    const text = this.container?.querySelector(selector)?.textContent || '';
    await this.copyText(text, message);
  }

  private async copyText(text: string, message: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      this.callbacks.onNotify?.('success', message);
    } catch {
      this.callbacks.onNotify?.('warning', 'Copy unavailable', 'Clipboard access was not granted by the browser.');
    }
  }

  private escapeHtml(value: string): string {
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  private escapeAttr(value: string): string {
    return this.escapeHtml(value);
  }
}
