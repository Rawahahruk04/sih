/**
 * AIPI Screen 2: Route Analytics & Sector Intelligence
 * 
 * Primary sectoral workspace consuming:
 * - GET /api/v1/routes
 * - GET /api/v1/index/routes
 * - GET /api/v1/index/routes/heatmap
 */

import { api, ApiError } from '../api/client.js';
import { EnterpriseTable, TableColumn } from '../components/EnterpriseTable.js';
import { SectorHeatmap } from '../components/SectorHeatmap.js';
import { StatCard } from '../components/StatCard.js';
import { Icons } from '../icons/index.js';
import { HeatmapResponse, RouteMetadataResponse, RoutesResponse, RouteSummary } from '../types/api.js';
import { htmlToElement } from '../utils/dom.js';
import { fmt } from '../utils/formatters.js';

export interface RouteAnalyticsCallbacks {
  onNavigateToRoute?: (routeCode: string) => void;
  onNotify?: (type: 'success' | 'warning' | 'error' | 'info', title: string, message?: string) => void;
}

export class RouteAnalyticsPage {
  private container: HTMLElement | null = null;
  private callbacks: RouteAnalyticsCallbacks;

  // Filter States
  private selectedRoute = '';
  private searchQuery = '';
  private dateFrom = '';
  private dateTo = '';

  // Data States
  private routeMeta: RouteMetadataResponse | null = null;
  private routesSummary: RoutesResponse | null = null;
  private heatmapData: HeatmapResponse | null = null;
  private loading = false;
  private error: ApiError | null = null;

  private tableInstance = new EnterpriseTable<RouteSummary>();

  constructor(callbacks: RouteAnalyticsCallbacks = {}) {
    this.callbacks = callbacks;
  }

  public render(container: HTMLElement): void {
    this.container = container;
    this.fetchData();
  }

  public async fetchData(): Promise<void> {
    this.loading = true;
    this.error = null;
    this.renderLoading();

    try {
      const [meta, summary, heatmap] = await Promise.all([
        api.getRouteMetadata(),
        api.getRoutesSummary(),
        api.getRouteHeatmap({
          from: this.dateFrom || undefined,
          to: this.dateTo || undefined
        })
      ]);

      this.routeMeta = meta;
      this.routesSummary = summary;
      this.heatmapData = heatmap;
      this.loading = false;

      this.renderContent();
    } catch (err) {
      this.loading = false;
      this.error = err instanceof ApiError ? err : new ApiError(500, 'network_error', String(err));
      this.renderError();
    }
  }

  private renderLoading(): void {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="route-analytics-loading">
        <!-- 1. KPI Grid Skeletons -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
        </div>

        <!-- 2. Heatmap Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 420px; margin-bottom: var(--space-20);"></div>

        <!-- 3. Table Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 300px;"></div>
      </div>
    `;
  }

  private renderError(): void {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="card-container" style="border-left: 4px solid var(--color-status-danger); padding: 32px 24px; text-align: center;">
        <div style="color: var(--color-status-danger); margin-bottom: 12px;">${Icons.danger()}</div>
        <h2 class="text-h2" style="margin-bottom: 8px;">Failed to Load Sector Analytics</h2>
        <p class="text-body-muted" style="max-width: 480px; margin: 0 auto 16px;">
          ${this.error?.detail || 'An unexpected error occurred while communicating with the route index service.'}
        </p>
        <button class="empty-state-action-btn" id="retry-btn">Retry Connection</button>
      </div>
    `;

    const retryBtn = this.container.querySelector('#retry-btn');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => this.fetchData());
    }
  }

  private renderContent(): void {
    if (!this.container || !this.routesSummary || !this.heatmapData) return;

    const routes = this.routesSummary.routes || [];

    // Calculate Executive Insights
    let highestRoute: RouteSummary | null = null;
    let lowestRoute: RouteSummary | null = null;

    routes.forEach((r) => {
      if (highestRoute == null || r.latest_value > highestRoute.latest_value) {
        highestRoute = r;
      }
      if (lowestRoute == null || r.latest_value < lowestRoute.latest_value) {
        lowestRoute = r;
      }
    });

    const spread =
      highestRoute && lowestRoute ? (highestRoute.latest_value - lowestRoute.latest_value).toFixed(2) : '—';

    const page = htmlToElement(`
      <div class="route-analytics-root">
        
        <!-- 1. Executive Insights KPI Grid -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3" id="sector-kpi-1"></div>
          <div class="col-3" id="sector-kpi-2"></div>
          <div class="col-3" id="sector-kpi-3"></div>
          <div class="col-3" id="sector-kpi-4"></div>
        </div>

        <!-- 2. Sector Filter & Control Toolbar -->
        <div class="card-container" style="margin-bottom: var(--space-20); padding: var(--space-12) var(--space-16);">
          <div class="chart-controls-bar" style="margin-bottom: 0; padding-bottom: 0; border-bottom: none;">
            <div class="controls-left">
              <div class="filter-input-group">
                <label for="route-search-input">Search Sectors:</label>
                <input type="text" id="route-search-input" class="filter-input" placeholder="e.g. DEL-BOM or Mumbai" value="${this.searchQuery}" style="width: 200px;" />
              </div>
            </div>

            <div class="controls-right">
              <div class="filter-input-group">
                <label for="date-from-input">From:</label>
                <input type="date" id="date-from-input" class="filter-input" value="${this.dateFrom}" />
              </div>
              <div class="filter-input-group">
                <label for="date-to-input">To:</label>
                <input type="date" id="date-to-input" class="filter-input" value="${this.dateTo}" />
              </div>
              <button class="empty-state-action-btn" id="apply-filter-btn" style="padding: 4px 10px; font-size: 12px;">Apply Range</button>
              ${this.dateFrom || this.dateTo ? '<button class="breadcrumb-link" id="reset-filter-btn" style="font-size: 12px;">Reset</button>' : ''}
            </div>
          </div>
        </div>

        <!-- 3. Primary 2D Sector Heatmap Panel -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Sector Inflation Heatmap Matrix</h3>
              <p class="card-subtitle">2D sector-date matrix tracking price movement relative to baseline (=100.0). Click any row to inspect trajectory.</p>
            </div>
            <div style="display: flex; gap: 12px; align-items: center;">
              <!-- Heatmap Legend -->
              <div style="display: flex; align-items: center; gap: 14px; font-size: 11px; color: var(--color-text-secondary);">
                <div style="display: flex; align-items: center; gap: 4px;">
                  <span style="width: 12px; height: 12px; background-color: #356C7B; border-radius: 2px;"></span>
                  <span>Below Base (&lt;100)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 4px;">
                  <span style="width: 12px; height: 12px; background-color: #F2EFD9; border: 1px solid var(--color-border-subtle); border-radius: 2px;"></span>
                  <span>Baseline (100.0)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 4px;">
                  <span style="width: 12px; height: 12px; background-color: #B54848; border-radius: 2px;"></span>
                  <span>Inflation Spike (&gt;100)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 4px;">
                  <span style="width: 12px; height: 12px; background: repeating-linear-gradient(45deg, #D9DFE2, #D9DFE2 2px, #FCFCFA 2px, #FCFCFA 4px); border: 1px solid var(--color-border-subtle); border-radius: 2px;"></span>
                  <span>No Data (null)</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Heatmap Render Canvas -->
          <div id="sector-heatmap-canvas"></div>
        </div>

        <!-- 4. Route Summary Enterprise Table Panel -->
        <div class="card-container">
          <div class="card-header">
            <div>
              <h3 class="card-title">Domestic Route Basket Master</h3>
              <p class="card-subtitle">All 12 tracked city pairs weighted by DGCA base expenditure share (passengers × base fare). Click any row to view sector trajectory.</p>
            </div>
            <span class="badge badge-neutral">${routes.length} Sectors Active</span>
          </div>

          <!-- Table Mount Point -->
          <div id="route-table-mount-point"></div>
        </div>

      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);

    // 5. Mount StatCards
    const kpi1 = page.querySelector('#sector-kpi-1');
    const kpi2 = page.querySelector('#sector-kpi-2');
    const kpi3 = page.querySelector('#sector-kpi-3');
    const kpi4 = page.querySelector('#sector-kpi-4');

    if (kpi1 && highestRoute) {
      const hr = highestRoute as RouteSummary;
      kpi1.appendChild(
        StatCard.render({
          label: 'HIGHEST INFLATION SECTOR',
          value: fmt.index(hr.latest_value, 2),
          unit: 'pts',
          delta: { value: hr.latest_value - 100.0, isPercent: true, label: 'vs Base' },
          hint: `${hr.display_name} (${hr.route_code})`,
          status: 'danger'
        })
      );
    }

    if (kpi2 && lowestRoute) {
      const lr = lowestRoute as RouteSummary;
      kpi2.appendChild(
        StatCard.render({
          label: 'LOWEST INFLATION SECTOR',
          value: fmt.index(lr.latest_value, 2),
          unit: 'pts',
          delta: { value: lr.latest_value - 100.0, isPercent: true, label: 'vs Base' },
          hint: `${lr.display_name} (${lr.route_code})`,
          status: lr.latest_value < 100 ? 'success' : 'neutral'
        })
      );
    }

    if (kpi3) {
      kpi3.appendChild(
        StatCard.render({
          label: 'CROSS-SECTOR SPREAD',
          value: spread,
          unit: 'pts',
          hint: 'Max vs Min sector divergence',
          status: 'neutral'
        })
      );
    }

    if (kpi4) {
      kpi4.appendChild(
        StatCard.render({
          label: 'TRACKED BASKET COVERAGE',
          value: `${routes.length} / 12`,
          unit: 'sectors',
          hint: '100% directional pair representation',
          status: 'success'
        })
      );
    }

    // 6. Mount Sector Heatmap
    const heatmapCanvas = page.querySelector<HTMLElement>('#sector-heatmap-canvas');
    if (heatmapCanvas && this.heatmapData) {
      SectorHeatmap.render(heatmapCanvas, {
        routes: this.heatmapData.routes,
        routeNames: this.heatmapData.route_names,
        dates: this.heatmapData.dates,
        matrix: this.heatmapData.matrix,
        valueMin: this.heatmapData.value_min,
        valueMax: this.heatmapData.value_max,
        baseline: this.heatmapData.baseline,
        onSelectRoute: (rCode) => this.handleSelectRoute(rCode)
      });
    }

    // 7. Mount Enterprise Table
    const tableMount = page.querySelector<HTMLElement>('#route-table-mount-point');
    if (tableMount) {
      const columns: TableColumn<RouteSummary>[] = [
        {
          key: 'route_code',
          label: 'Route Code',
          width: '140px',
          render: (row) => `<span class="code-badge" style="font-weight: 600;">${row.route_code}</span>`
        },
        {
          key: 'display_name',
          label: 'Sector Name',
          render: (row) => `<span style="font-weight: 500; color: var(--color-text-primary);">${row.display_name}</span>`
        },
        {
          key: 'weight',
          label: 'Basket Weight',
          align: 'right',
          width: '180px',
          render: (row) => {
            const pct = (row.weight * 100).toFixed(2);
            return `
              <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                <div style="width: 60px; height: 6px; background-color: var(--color-bg-surface-subtle); border-radius: 3px; overflow: hidden;">
                  <div style="width: ${Math.min(100, row.weight * 350)}%; height: 100%; background-color: var(--color-brand-secondary);"></div>
                </div>
                <span class="metric-tabular" style="font-weight: 600;">${pct}%</span>
              </div>
            `;
          }
        },
        {
          key: 'latest_date',
          label: 'Latest Date',
          align: 'center',
          width: '120px',
          render: (row) => `<span style="color: var(--color-text-secondary);">${row.latest_date}</span>`
        },
        {
          key: 'latest_value',
          label: 'Latest Index',
          align: 'right',
          width: '140px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 700; font-size: 14px;">${fmt.index(row.latest_value, 2)} pts</span>`
        },
        {
          key: 'delta',
          label: 'vs Base (100.0)',
          align: 'right',
          width: '140px',
          render: (row) => {
            const delta = row.latest_value - 100.0;
            const deltaClass = delta >= 0 ? 'delta-positive' : 'delta-negative';
            return `<span class="stat-delta ${deltaClass}">${fmt.signedDelta(delta, '%', 2)}</span>`;
          }
        }
      ];

      this.tableInstance.render(tableMount, {
        columns,
        data: routes,
        keyField: 'route_code',
        searchQuery: this.searchQuery,
        searchFields: ['route_code', 'display_name'],
        onRowClick: (row) => this.handleSelectRoute(row.route_code),
        emptyMessage: 'No domestic routes matching search criteria.'
      });
    }

    // 8. Attach Filter Listeners
    this.attachFilterListeners(page);
  }

  private handleSelectRoute(routeCode: string): void {
    if (this.callbacks.onNotify) {
      this.callbacks.onNotify(
        'info',
        `Sector Selected: ${routeCode}`,
        'Route deep-dive trajectory inspection view is scheduled for the next milestone.'
      );
    }
    if (this.callbacks.onNavigateToRoute) {
      this.callbacks.onNavigateToRoute(routeCode);
    }
  }

  private attachFilterListeners(page: HTMLElement): void {
    const searchInput = page.querySelector<HTMLInputElement>('#route-search-input');
    const fromInput = page.querySelector<HTMLInputElement>('#date-from-input');
    const toInput = page.querySelector<HTMLInputElement>('#date-to-input');
    const applyBtn = page.querySelector('#apply-filter-btn');
    const resetBtn = page.querySelector('#reset-filter-btn');

    if (searchInput) {
      searchInput.addEventListener('input', () => {
        this.searchQuery = searchInput.value;
        const tableMount = page.querySelector<HTMLElement>('#route-table-mount-point');
        if (tableMount && this.routesSummary) {
          this.tableInstance.render(tableMount, {
            columns: [
              {
                key: 'route_code',
                label: 'Route Code',
                width: '140px',
                render: (row) => `<span class="code-badge" style="font-weight: 600;">${row.route_code}</span>`
              },
              {
                key: 'display_name',
                label: 'Sector Name',
                render: (row) => `<span style="font-weight: 500; color: var(--color-text-primary);">${row.display_name}</span>`
              },
              {
                key: 'weight',
                label: 'Basket Weight',
                align: 'right',
                width: '180px',
                render: (row) => {
                  const pct = (row.weight * 100).toFixed(2);
                  return `
                    <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                      <div style="width: 60px; height: 6px; background-color: var(--color-bg-surface-subtle); border-radius: 3px; overflow: hidden;">
                        <div style="width: ${Math.min(100, row.weight * 350)}%; height: 100%; background-color: var(--color-brand-secondary);"></div>
                      </div>
                      <span class="metric-tabular" style="font-weight: 600;">${pct}%</span>
                    </div>
                  `;
                }
              },
              {
                key: 'latest_date',
                label: 'Latest Date',
                align: 'center',
                width: '120px',
                render: (row) => `<span style="color: var(--color-text-secondary);">${row.latest_date}</span>`
              },
              {
                key: 'latest_value',
                label: 'Latest Index',
                align: 'right',
                width: '140px',
                render: (row) => `<span class="metric-tabular" style="font-weight: 700; font-size: 14px;">${fmt.index(row.latest_value, 2)} pts</span>`
              },
              {
                key: 'delta',
                label: 'vs Base (100.0)',
                align: 'right',
                width: '140px',
                render: (row) => {
                  const delta = row.latest_value - 100.0;
                  const deltaClass = delta >= 0 ? 'delta-positive' : 'delta-negative';
                  return `<span class="stat-delta ${deltaClass}">${fmt.signedDelta(delta, '%', 2)}</span>`;
                }
              }
            ],
            data: this.routesSummary.routes,
            keyField: 'route_code',
            searchQuery: this.searchQuery,
            searchFields: ['route_code', 'display_name'],
            onRowClick: (row) => this.handleSelectRoute(row.route_code),
            emptyMessage: 'No domestic routes matching search criteria.'
          });
        }
      });
    }

    if (applyBtn) {
      applyBtn.addEventListener('click', () => {
        this.dateFrom = fromInput?.value || '';
        this.dateTo = toInput?.value || '';
        this.fetchData();
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.dateFrom = '';
        this.dateTo = '';
        this.fetchData();
      });
    }
  }
}
