/**
 * AIPI Screen 3: Route Detail Inspector (ES Module)
 */

import { api, ApiError } from '../api/client.js';
import { EnterpriseTable } from '../components/EnterpriseTable.js';
import { ErrorState } from '../components/ErrorState.js';
import { StatCard } from '../components/StatCard.js';
import { TimeSeriesChart } from '../components/TimeSeriesChart.js';
import { htmlToElement } from '../utils/dom.js';
import { fmt } from '../utils/formatters.js';

export class RouteDetailPage {
  constructor(routeCode, callbacks = {}) {
    this.routeCode = routeCode;
    this.callbacks = callbacks;
    this.container = null;

    this.routeData = null;
    this.loading = false;
    this.error = null;

    this.tableInstance = new EnterpriseTable();
    this.abortController = null;
  }

  setRouteCode(code) {
    this.routeCode = code;
    this.fetchData();
  }

  render(container) {
    this.container = container;
    this.fetchData();
  }

  async fetchData() {
    this.abortController?.abort();
    const controller = new AbortController();
    this.abortController = controller;
    const { signal } = controller;

    this.loading = true;
    this.error = null;
    this.renderLoading();

    try {
      const data = await api.getRouteSeries(this.routeCode, signal);
      if (signal.aborted) return;
      this.routeData = data;
      this.loading = false;
      this.renderContent();
    } catch (err) {
      if (signal.aborted || err?.name === 'AbortError') return;
      this.loading = false;
      this.error = err instanceof ApiError ? err : new ApiError(500, 'network_error', String(err));
      this.renderError();
    }
  }

  renderLoading() {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="route-detail-loading">
        <!-- 1. Executive Summary Skeleton -->
        <div class="stat-card skeleton-shimmer stat-large" style="height: 120px; margin-bottom: var(--space-20);"></div>

        <!-- 2. Primary KPI Grid Skeletons -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
        </div>

        <!-- 3. Chart Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 380px; margin-bottom: var(--space-20);"></div>

        <!-- 4. Table Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 280px;"></div>
      </div>
    `;
  }

  renderError() {
    const isNotFound = this.error?.statusCode === 404;

    ErrorState.render(this.container, {
      title: isNotFound ? `Unknown Sector: ${this.routeCode}` : 'Failed to Load Sector Trajectory',
      message: isNotFound
        ? `The sector code "${this.routeCode}" is not included in the active 12-route domestic index basket.`
        : this.error?.detail || 'An unexpected error occurred while loading single-route observations.',
      secondaryLabel: '← Back to Route Analytics',
      onSecondary: () => this.callbacks.onBackToRoutes(),
      retryLabel: 'Retry',
      onRetry: isNotFound ? undefined : () => this.fetchData()
    });
  }

  renderContent() {
    if (!this.container || !this.routeData) return;

    const points = this.routeData.points || [];
    const latestPoint = points.length > 0 ? points[points.length - 1] : null;
    const priorPoint = points.length > 1 ? points[points.length - 2] : null;

    const latestValue = latestPoint ? latestPoint.value : null;
    const deltaFromBase = latestValue != null ? latestValue - 100.0 : null;
    const deltaFromPrior = latestValue != null && priorPoint != null ? latestValue - priorPoint.value : null;
    const weightPct = (this.routeData.weight * 100).toFixed(2);

    const page = htmlToElement(`
      <div class="route-detail-root">
        
        <!-- 1. Header Navigation Bar -->
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-16);">
          <button class="breadcrumb-link" id="back-to-routes-action" style="font-size: 13px; font-weight: 500; display: inline-flex; align-items: center; gap: 4px;">
            <span>← Back to Route Analytics</span>
          </button>
          <span class="badge badge-neutral" style="font-family: var(--font-family-mono);">
            DGCA EXPENDITURE WEIGHT: ${weightPct}%
          </span>
        </div>

        <!-- 2. Executive Summary Headline Banner -->
        <div class="card-container" style="margin-bottom: var(--space-20); background: linear-gradient(180deg, var(--color-bg-surface) 0%, var(--color-bg-surface-subtle) 100%); border-left: 4px solid var(--color-brand-secondary);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
            <div>
              <div class="text-label" style="color: var(--color-text-secondary); margin-bottom: 4px;">
                SECTOR PRICE INDEX (AIPI)
              </div>
              <h2 class="text-h1" style="color: var(--color-text-primary); margin-bottom: 8px;">
                ${this.routeData.display_name} <span class="code-badge" style="font-size: 14px; margin-left: 6px;">${this.routeData.route_code}</span>
              </h2>
              <div style="display: flex; align-items: baseline; gap: 12px;">
                <span class="metric-large" style="font-size: 32px; color: var(--color-brand-secondary);">
                  ${fmt.index(latestValue, 2)}
                </span>
                <span class="text-h3" style="color: var(--color-text-secondary);">points</span>
                <span class="stat-delta ${deltaFromBase != null && deltaFromBase >= 0 ? 'delta-positive' : 'delta-negative'}" style="font-size: 13px;">
                  ${fmt.signedDelta(deltaFromBase, '%', 2)} vs Base Window
                </span>
              </div>
            </div>
            
            <div style="text-align: right;">
              <div class="text-small" style="color: var(--color-text-secondary);">
                Total Historical Series: <b>${this.routeData.count} days</b>
              </div>
              <div class="text-small" style="color: var(--color-text-tertiary); margin-top: 4px;">
                Latest quote date: <b>${latestPoint ? latestPoint.date : '—'}</b>
              </div>
            </div>
          </div>
        </div>

        <!-- 3. Primary KPI Grid -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3" id="detail-kpi-1"></div>
          <div class="col-3" id="detail-kpi-2"></div>
          <div class="col-3" id="detail-kpi-3"></div>
          <div class="col-3" id="detail-kpi-4"></div>
        </div>

        <!-- 4. Historical Trajectory Time-Series Chart Panel -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">${this.routeData.display_name} Price Index Path</h3>
              <p class="card-subtitle">Daily elementary GEKS-Jevons index series relative to base period mean (=100.0).</p>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="display: inline-block; width: 14px; height: 1.5px; border-top: 1.5px dashed var(--color-chart-baseline);"></span>
              <span class="text-small" style="color: var(--color-text-secondary);">Base = 100.0</span>
            </div>
          </div>

          <!-- Chart Render Canvas -->
          <div id="route-detail-chart-canvas"></div>
        </div>

        <!-- 5. Chronological Observation Timeline Table Panel -->
        <div class="card-container">
          <div class="card-header">
            <div>
              <h3 class="card-title">Chronological Observation History</h3>
              <p class="card-subtitle">Point-by-point index values, period-on-period movement, and sample coverage for ${this.routeData.route_code}.</p>
            </div>
            <span class="badge badge-neutral">${points.length} Daily Observations</span>
          </div>

          <!-- Table Mount Point -->
          <div id="route-timeline-table-mount"></div>
        </div>

      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);

    // Attach Back Button Listener
    const backBtn = page.querySelector('#back-to-routes-action');
    if (backBtn) {
      backBtn.addEventListener('click', () => this.callbacks.onBackToRoutes());
    }

    // 6. Mount StatCards
    const kpi1 = page.querySelector('#detail-kpi-1');
    const kpi2 = page.querySelector('#detail-kpi-2');
    const kpi3 = page.querySelector('#detail-kpi-3');
    const kpi4 = page.querySelector('#detail-kpi-4');

    if (kpi1) {
      kpi1.appendChild(
        StatCard.render({
          label: 'CURRENT ROUTE INDEX',
          value: fmt.index(latestValue, 2),
          unit: 'pts',
          delta: deltaFromPrior != null ? { value: deltaFromPrior, label: 'Period Change' } : undefined,
          hint: `Latest date: ${latestPoint ? latestPoint.date : '—'}`,
          status: 'neutral'
        })
      );
    }

    if (kpi2) {
      kpi2.appendChild(
        StatCard.render({
          label: 'CUMULATIVE INFLATION',
          value: fmt.signedDelta(deltaFromBase, '%', 2),
          hint: 'Change vs Base Window (100.0)',
          status: deltaFromBase != null && deltaFromBase > 0 ? 'danger' : 'success'
        })
      );
    }

    if (kpi3) {
      kpi3.appendChild(
        StatCard.render({
          label: 'SAMPLE COVERAGE',
          value: fmt.percent(latestPoint?.coverage_pct, 1),
          hint: `${latestPoint?.n_obs || 0} flight quotes in period`,
          status: (latestPoint?.coverage_pct || 0) >= 90 ? 'success' : 'warning'
        })
      );
    }

    if (kpi4) {
      kpi4.appendChild(
        StatCard.render({
          label: 'BASKET EXPENDITURE SHARE',
          value: `${weightPct}%`,
          hint: 'Relative Laspeyres weight',
          status: 'neutral'
        })
      );
    }

    // 7. Mount TimeSeriesChart SVG
    const chartCanvas = page.querySelector('#route-detail-chart-canvas');
    if (chartCanvas) {
      const seriesList = [
        {
          id: this.routeData.route_code,
          name: this.routeData.display_name,
          color: 'var(--color-brand-secondary)',
          points: points.map((p) => ({
            x: p.date,
            y: p.value,
            nObs: p.n_obs,
            coveragePct: p.coverage_pct,
            isComplete: p.is_complete
          }))
        }
      ];

      TimeSeriesChart.render(chartCanvas, {
        series: seriesList,
        baseline: 100.0
      });
    }

    // 8. Mount Enterprise Timeline Table
    const tableMount = page.querySelector('#route-timeline-table-mount');
    if (tableMount) {
      const reversedPoints = [...points].reverse();

      const columns = [
        {
          key: 'date',
          label: 'Date',
          width: '140px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 600;">${row.date}</span>`
        },
        {
          key: 'value',
          label: 'Index Value',
          align: 'right',
          width: '160px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 700; font-size: 14px;">${fmt.index(row.value, 2)} pts</span>`
        },
        {
          key: 'deltaBase',
          label: 'vs Base (100.0)',
          align: 'right',
          width: '150px',
          render: (row) => {
            const delta = row.value - 100.0;
            const deltaClass = delta >= 0 ? 'delta-positive' : 'delta-negative';
            return `<span class="stat-delta ${deltaClass}">${fmt.signedDelta(delta, '%', 2)}</span>`;
          }
        },
        {
          key: 'n_obs',
          label: 'Quotation Count',
          align: 'right',
          width: '150px',
          render: (row) => `<span class="metric-tabular">${fmt.integer(row.n_obs)} quotes</span>`
        },
        {
          key: 'coverage_pct',
          label: 'Coverage %',
          align: 'right',
          width: '150px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 600;">${fmt.percent(row.coverage_pct, 1)}</span>`
        },
        {
          key: 'status',
          label: 'Data Health',
          align: 'center',
          width: '130px',
          render: (row) =>
            row.coverage_pct >= 90
              ? '<span class="badge badge-success">Optimal</span>'
              : '<span class="badge badge-warning">Partial</span>'
        }
      ];

      this.tableInstance.render(tableMount, {
        columns,
        data: reversedPoints,
        keyField: 'date',
        searchFields: ['date'],
        emptyMessage: 'No observations recorded for this route.',
        ariaLabel: `Chronological observation history for ${this.routeCode}`
      });
    }
  }
}
