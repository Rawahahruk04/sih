/**
 * AIPI Screen 4: Booking Lead-Time Analysis
 * 
 * Deep-dive econometric lead-time elasticity workspace consuming:
 * - GET /api/v1/index/leadtime/curve
 * - GET /api/v1/index/leadtime
 */

import { api, ApiError } from '../api/client.js';
import { EnterpriseTable, TableColumn } from '../components/EnterpriseTable.js';
import { ErrorState } from '../components/ErrorState.js';
import { LeadtimeCurveChart } from '../components/LeadtimeCurveChart.js';
import { StatCard } from '../components/StatCard.js';
import { ChartSeries, TimeSeriesChart } from '../components/TimeSeriesChart.js';
import { Icons } from '../icons/index.js';
import { LeadtimeCurveResponse, LeadtimeIndexResponse, LeadtimeWindow } from '../types/api.js';
import { htmlToElement } from '../utils/dom.js';
import { fmt } from '../utils/formatters.js';

interface WindowSummaryRow {
  advance_days: number;
  relative_level: number | null;
  delta_ref: number | null;
  latest_index_value: number | null;
  latest_date: string | null;
  latest_n_obs: number | null;
  latest_coverage_pct: number | null;
}

export interface LeadTimeCallbacks {
  onNotify?: (type: 'success' | 'warning' | 'error' | 'info', title: string, message?: string) => void;
}

export class LeadTimePage {
  private container: HTMLElement | null = null;
  private callbacks: LeadTimeCallbacks;

  // Selected window for detailed time-series inspection
  private selectedWindowDays: number | null = null; // null = all key windows

  // Data States
  private curveData: LeadtimeCurveResponse | null = null;
  private indexData: LeadtimeIndexResponse | null = null;
  private loading = false;
  private error: ApiError | null = null;

  private tableInstance = new EnterpriseTable<WindowSummaryRow>();
  private abortController: AbortController | null = null;

  constructor(callbacks: LeadTimeCallbacks = {}) {
    this.callbacks = callbacks;
  }

  public render(container: HTMLElement): void {
    this.container = container;
    this.fetchData();
  }

  public async fetchData(): Promise<void> {
    this.abortController?.abort();
    const controller = new AbortController();
    this.abortController = controller;
    const { signal } = controller;

    this.loading = true;
    this.error = null;
    this.renderLoading();

    try {
      const [curve, leadtimeIndex] = await Promise.all([
        api.getLeadtimeCurve(undefined, signal),
        api.getLeadtimeIndex(signal)
      ]);

      if (signal.aborted) return;

      this.curveData = curve;
      this.indexData = leadtimeIndex;
      this.loading = false;

      this.renderContent();
    } catch (err) {
      if (signal.aborted || (err as any)?.name === 'AbortError') return;
      this.loading = false;
      this.error = err instanceof ApiError ? err : new ApiError(500, 'network_error', String(err));
      this.renderError();
    }
  }

  private renderLoading(): void {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="leadtime-loading-layout">
        <!-- 1. KPI Grid Skeletons -->
        <div class="grid-12">
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
        </div>

        <!-- 2. Lead-Time Curve Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 280px;"></div>

        <!-- 3. Inflation by Window Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 240px;"></div>
      </div>
    `;
  }

  private renderError(): void {
    ErrorState.render(this.container, {
      title: 'Failed to Load Lead-Time Elasticity',
      message: this.error?.detail || 'An unexpected error occurred while communicating with the lead-time calculation engine.',
      onRetry: () => this.fetchData()
    });
  }

  private renderContent(): void {
    if (!this.container || !this.curveData || !this.indexData) return;

    const curvePoints = this.curveData.curve || [];
    const windows = this.indexData.windows || [];

    // Calculate Executive Insights
    const refWindow = this.curveData.reference_window ?? 14;
    const ptWalkup = curvePoints.find((p) => p.advance_days === 1) || curvePoints[0];
    const ptEarly = curvePoints.find((p) => p.advance_days === 45) || curvePoints[curvePoints.length - 1];

    const walkupLevel = ptWalkup ? ptWalkup.relative_level : null;
    const walkupDelta = walkupLevel != null ? walkupLevel - 100.0 : null;

    const earlyLevel = ptEarly ? ptEarly.relative_level : null;
    const earlyDelta = earlyLevel != null ? earlyLevel - 100.0 : null;

    const spreadPts =
      walkupLevel != null && earlyLevel != null ? (walkupLevel - earlyLevel).toFixed(2) : '—';

    // Build Table Rows mapping Curve + Index
    const tableRows: WindowSummaryRow[] = curvePoints.map((cp) => {
      const win = windows.find((w) => w.advance_days === cp.advance_days);
      const pts = win ? win.points : [];
      const latestPt = pts.length > 0 ? pts[pts.length - 1] : null;

      return {
        advance_days: cp.advance_days,
        relative_level: cp.relative_level,
        delta_ref: cp.relative_level - 100.0,
        latest_index_value: latestPt ? latestPt.value : null,
        latest_date: latestPt ? latestPt.date : null,
        latest_n_obs: latestPt ? latestPt.n_obs : null,
        latest_coverage_pct: latestPt ? latestPt.coverage_pct : null
      };
    });

    const page = htmlToElement(`
      <div class="leadtime-page-root">
        <!-- 1. Primary KPI Grid -->
        <div class="grid-12">
          <div class="col-3" id="leadtime-kpi-1"></div>
          <div class="col-3" id="leadtime-kpi-2"></div>
          <div class="col-3" id="leadtime-kpi-3"></div>
          <div class="col-3" id="leadtime-kpi-4"></div>
        </div>

        <!-- 2. Dual Panel Row: Curve Chart (Left) + Horizon Table (Right) -->
        <div class="grid-12">
          <!-- Left: Empirical Advance Purchase Fare Level Curve -->
          <div class="col-7">
            <div class="card-container" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Empirical Advance Purchase Fare Level Curve</h3>
                  <p class="card-subtitle">Relative fare level multiplier by advance window (T+${refWindow} = 100.0). Pooled 7-day window.</p>
                </div>
                <span class="badge badge-neutral">T+${refWindow} Baseline</span>
              </div>

              <!-- Curve Render Canvas -->
              <div id="leadtime-curve-canvas"></div>
            </div>
          </div>

          <!-- Right: Advance Window Summary Table Panel -->
          <div class="col-5">
            <div class="card-container" style="height: 100%;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Advance Horizon Metrics Grid</h3>
                  <p class="card-subtitle">Comparative fare multipliers across all ${curvePoints.length} tracked horizons.</p>
                </div>
                <span class="badge badge-neutral">${curvePoints.length} Horizons</span>
              </div>

              <!-- Table Mount Point -->
              <div id="window-table-mount-point"></div>
            </div>
          </div>
        </div>

        <!-- 3. Secondary Visualization: Advance Window Inflation Trajectories -->
        <div class="card-container">
          <div class="card-header">
            <div>
              <h3 class="card-title">Inflation by Advance Purchase Window (Base Period = 100.0)</h3>
              <p class="card-subtitle">Time-series tracking inflation rate differences between advance booking horizons over time.</p>
            </div>
            
            <!-- Window Selector Segmented Control -->
            <div class="segmented-control" id="window-filter-control" role="tablist" aria-label="Window Filter">
              <button class="segmented-control-item ${this.selectedWindowDays == null ? 'active' : ''}" data-window="all">All Horizons</button>
              <button class="segmented-control-item ${this.selectedWindowDays === 1 ? 'active' : ''}" data-window="1">T+1 Walk-Up</button>
              <button class="segmented-control-item ${this.selectedWindowDays === 7 ? 'active' : ''}" data-window="7">T+7 Short</button>
              <button class="segmented-control-item ${this.selectedWindowDays === refWindow ? 'active' : ''}" data-window="${refWindow}">T+${refWindow} Ref</button>
              <button class="segmented-control-item ${this.selectedWindowDays === 30 ? 'active' : ''}" data-window="30">T+30 Advance</button>
            </div>
          </div>

          <!-- Window Inflation Chart Canvas -->
          <div id="window-inflation-chart-canvas"></div>
        </div>
      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);

    // Dynamically synchronize page header badge with real backend reference horizon
    const pageHeaderBadge = document.querySelector('.title-with-badge .badge');
    if (pageHeaderBadge) {
      pageHeaderBadge.textContent = `T+${refWindow} Reference Horizon (=100.0)`;
    }

    // 6. Mount StatCards
    const kpi1 = page.querySelector('#leadtime-kpi-1');
    const kpi2 = page.querySelector('#leadtime-kpi-2');
    const kpi3 = page.querySelector('#leadtime-kpi-3');
    const kpi4 = page.querySelector('#leadtime-kpi-4');

    if (kpi1) {
      kpi1.appendChild(
        StatCard.render({
          label: 'T+1 WALK-UP MULTIPLIER',
          value: fmt.index(walkupLevel, 2),
          unit: 'pts',
          delta: walkupDelta != null ? { value: walkupDelta, isPercent: true, label: `vs T+${refWindow}` } : undefined,
          hint: 'Last-minute departure premium',
          status: 'danger'
        })
      );
    }

    if (kpi2) {
      kpi2.appendChild(
        StatCard.render({
          label: 'T+45 EARLY BIRD LEVEL',
          value: fmt.index(earlyLevel, 2),
          unit: 'pts',
          delta: earlyDelta != null ? { value: earlyDelta, isPercent: true, label: `vs T+${refWindow}` } : undefined,
          hint: '45-day advance booking discount',
          status: 'success'
        })
      );
    }

    if (kpi3) {
      kpi3.appendChild(
        StatCard.render({
          label: 'BOOKING HORIZON SPREAD',
          value: spreadPts,
          unit: 'pts',
          hint: 'Max T+1 vs Min T+45 yield delta',
          status: 'neutral'
        })
      );
    }

    if (kpi4) {
      kpi4.appendChild(
        StatCard.render({
          label: 'TRACKED HORIZONS',
          value: `${curvePoints.length}`,
          unit: 'windows',
          hint: 'T+1 through T+45 days',
          status: 'neutral'
        })
      );
    }

    // 7. Mount LeadtimeCurveChart
    const curveCanvas = page.querySelector<HTMLElement>('#leadtime-curve-canvas');
    if (curveCanvas) {
      LeadtimeCurveChart.render(curveCanvas, {
        curve: curvePoints,
        referenceWindow: refWindow,
        asOf: this.curveData.as_of
      });
    }

    // 8. Mount Window Inflation Time-Series Chart
    this.renderWindowInflationChart(page);

    // 9. Mount Summary Enterprise Table
    const tableMount = page.querySelector<HTMLElement>('#window-table-mount-point');
    if (tableMount) {
      const columns: TableColumn<WindowSummaryRow>[] = [
        {
          key: 'advance_days',
          label: 'Horizon',
          width: '130px',
          render: (row) => `<span class="code-badge" style="font-weight: 600;">T+${row.advance_days} Days</span>`
        },
        {
          key: 'relative_level',
          label: `Fare Level (T+${refWindow} = 100)`,
          align: 'right',
          width: '180px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 700; font-size: 14px;">${fmt.index(row.relative_level, 2)} pts</span>`
        },
        {
          key: 'delta_ref',
          label: `vs T+${refWindow} Reference`,
          align: 'right',
          width: '170px',
          render: (row) => {
            if (row.delta_ref == null) return '—';
            const deltaClass = row.delta_ref >= 0 ? 'delta-positive' : 'delta-negative';
            return `<span class="stat-delta ${deltaClass}">${fmt.signedDelta(row.delta_ref, '%', 2)}</span>`;
          }
        },
        {
          key: 'latest_index_value',
          label: 'Window Inflation Index',
          align: 'right',
          width: '180px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 600;">${fmt.index(row.latest_index_value, 2)} pts</span>`
        },
        {
          key: 'latest_n_obs',
          label: 'Observations',
          align: 'right',
          width: '140px',
          render: (row) => `<span class="metric-tabular">${fmt.integer(row.latest_n_obs)} quotes</span>`
        },
        {
          key: 'latest_coverage_pct',
          label: 'Coverage %',
          align: 'right',
          width: '140px',
          render: (row) => `<span class="metric-tabular">${fmt.percent(row.latest_coverage_pct, 1)}</span>`
        }
      ];

      this.tableInstance.render(tableMount, {
        columns,
        data: tableRows,
        keyField: 'advance_days',
        emptyMessage: 'No advance window data available.'
      });
    }

    // 10. Attach Window Filter Listener
    const filterButtons = page.querySelectorAll<HTMLButtonElement>('.segmented-control-item');
    filterButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const winAttr = btn.dataset.window;
        this.selectedWindowDays = winAttr === 'all' ? null : parseInt(winAttr || '0', 10);
        filterButtons.forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        this.renderWindowInflationChart(page);
      });
    });
  }

  private renderWindowInflationChart(page: HTMLElement): void {
    const chartCanvas = page.querySelector<HTMLElement>('#window-inflation-chart-canvas');
    if (!chartCanvas || !this.indexData) return;

    const windows = this.indexData.windows || [];

    // Distinct palette for windows
    const colors: Record<number, string> = {
      1: 'var(--color-status-danger)', // T+1 Crimson
      2: '#C97A3E',
      3: '#B97A2D',
      7: 'var(--color-brand-secondary)', // T+7 Teal
      14: 'var(--color-brand-primary)', // T+14 Navy
      21: '#4B7B8C',
      30: 'var(--color-status-success)', // T+30 Green
      45: '#5C6B73'
    };

    let targetWindows = windows;
    if (this.selectedWindowDays != null) {
      targetWindows = windows.filter((w) => w.advance_days === this.selectedWindowDays);
    } else {
      // Focus on key representative horizons: 1, 7, 14, 30
      const keySet = new Set([1, 7, 14, 30]);
      targetWindows = windows.filter((w) => keySet.has(w.advance_days));
    }

    const seriesList: ChartSeries[] = targetWindows.map((w) => ({
      id: `w-${w.advance_days}`,
      name: `T+${w.advance_days} Days`,
      color: colors[w.advance_days] || 'var(--color-brand-secondary)',
      points: w.points.map((p) => ({
        x: p.date,
        y: p.value,
        nObs: p.n_obs,
        coveragePct: p.coverage_pct,
        isComplete: p.is_complete
      }))
    }));

    TimeSeriesChart.render(chartCanvas, {
      series: seriesList,
      baseline: 100.0
    });
  }
}
