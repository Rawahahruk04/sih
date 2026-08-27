/**
 * AIPI Screen 6: Volatility & Sampling Error
 *
 * Intraday capture dispersion and Monte Carlo sparse-sampling error diagnostics
 * consuming:
 * - GET /api/v1/index/volatility
 *
 * Every field rendered here maps directly to aipi/store.py::SnapshotStore.volatility()
 * (daily / intraday / sampling_error). No metric on this page is invented.
 */

import { api, ApiError } from '../api/client.js';
import { EnterpriseTable, TableColumn } from '../components/EnterpriseTable.js';
import { ErrorState } from '../components/ErrorState.js';
import { StatCard } from '../components/StatCard.js';
import { ChartSeries, TimeSeriesChart } from '../components/TimeSeriesChart.js';
import { Icons } from '../icons/index.js';
import { VolatilityResponse } from '../types/api.js';
import { htmlToElement } from '../utils/dom.js';
import { fmt } from '../utils/formatters.js';

interface AdvanceWindowRow {
  advance_days: string;
  cv_pct: number;
}

interface SamplingCurveRow {
  days_per_month: number;
  mae_pct: number;
  p95_abs_pct: number;
  direction_error_rate: number;
}

export interface VolatilityCallbacks {
  onNotify?: (type: 'success' | 'warning' | 'error' | 'info', title: string, message?: string) => void;
}

export class VolatilityPage {
  private container: HTMLElement | null = null;
  private callbacks: VolatilityCallbacks;

  private data: VolatilityResponse | null = null;
  private loading = false;
  private error: ApiError | null = null;

  private windowTable = new EnterpriseTable<AdvanceWindowRow>();
  private curveTable = new EnterpriseTable<SamplingCurveRow>();
  private abortController: AbortController | null = null;

  constructor(callbacks: VolatilityCallbacks = {}) {
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
      this.data = await api.getVolatility(signal);
      if (signal.aborted) return;
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
      <div class="volatility-loading-layout">
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
        </div>
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-6"><div class="card-container skeleton-shimmer" style="height: 240px;"></div></div>
          <div class="col-6"><div class="card-container skeleton-shimmer" style="height: 240px;"></div></div>
        </div>
        <div class="card-container skeleton-shimmer" style="height: 340px;"></div>
      </div>
    `;
  }

  private renderError(): void {
    ErrorState.render(this.container, {
      title: 'Failed to Load Volatility Diagnostics',
      message: this.error?.detail || 'An unexpected error occurred while communicating with the volatility calculation engine.',
      onRetry: () => this.fetchData()
    });
  }

  private renderContent(): void {
    if (!this.container || !this.data) return;

    const vol = this.data;
    const daily = vol.daily || { daily_volatility_pct: null, max_daily_move_pct: null, suspiciously_flat: null };
    const intraday = vol.intraday;
    const samplingError = vol.sampling_error;
    const samplingAvailable = !!samplingError && samplingError.available !== false;
    const oneDayPerMonth = samplingError?.one_day_per_month;
    const requiredDays = samplingError?.required_days_for_1pct_mae;

    const dailyVolStr = daily.daily_volatility_pct != null ? `${daily.daily_volatility_pct.toFixed(2)}%` : '—';
    const maxMoveStr = daily.max_daily_move_pct != null ? `${daily.max_daily_move_pct.toFixed(2)}%` : '—';
    const isSuspiciouslyFlat = daily.suspiciously_flat === true;

    const windowRows: AdvanceWindowRow[] = intraday?.by_advance_window
      ? Object.entries(intraday.by_advance_window)
          .map(([advance_days, cv_pct]) => ({ advance_days, cv_pct }))
          .sort((a, b) => Number(a.advance_days) - Number(b.advance_days))
      : [];

    const curveRows: SamplingCurveRow[] = samplingError?.curve || [];

    const page = htmlToElement(`
      <div class="volatility-page-root">

        <!-- 1. Section Intro Banner -->
        <div class="card-container" style="margin-bottom: var(--space-20); border-left: 4px solid var(--color-brand-primary); background: linear-gradient(180deg, var(--color-bg-surface) 0%, var(--color-bg-surface-subtle) 100%);">
          <div class="text-label" style="color: var(--color-text-secondary); margin-bottom: 4px;">DAILY VOLATILITY &amp; SPARSE-SAMPLING MEASUREMENT ERROR</div>
          <p class="text-body-muted" style="max-width: 720px;">
            Day-to-day dispersion of the headline index, within-day fare dispersion across capture slots (when
            captured), and a Monte Carlo simulation of the error a monthly-sampling collection design would carry
            versus AIPI's daily capture.
          </p>
        </div>

        <!-- 2. KPI Grid -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3" id="vol-kpi-1"></div>
          <div class="col-3" id="vol-kpi-2"></div>
          <div class="col-3" id="vol-kpi-3"></div>
          <div class="col-3" id="vol-kpi-4"></div>
        </div>

        <!-- 3. Daily Volatility & Intraday Dispersion -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-6">
            <div class="card-container" style="height: 100%;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Daily Index Volatility</h3>
                  <p class="card-subtitle">Standard deviation of day-on-day relative movement in the headline index.</p>
                </div>
                <span class="badge badge-neutral">daily.*</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Daily Volatility (Std Dev)</span>
                <span class="quality-value">${dailyVolStr}</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Max Single-Day Move</span>
                <span class="quality-value">${maxMoveStr}</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Amadeus Drift / Flat Cache Check</span>
                <span class="quality-value">
                  ${
                    daily.suspiciously_flat == null
                      ? '<span style="color: var(--color-text-tertiary);">Not computed (insufficient points)</span>'
                      : isSuspiciouslyFlat
                        ? '<span style="color: var(--color-status-danger);">Alarm: Suspiciously Flat</span>'
                        : '<span style="color: var(--color-status-success);">Passed (Active Variation)</span>'
                  }
                </span>
              </div>
            </div>
          </div>

          <div class="col-6">
            <div class="card-container" style="height: 100%;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Intraday Fare Dispersion</h3>
                  <p class="card-subtitle">Coefficient of variation across capture slots within a single offer-day.</p>
                </div>
                <span class="badge badge-neutral">intraday.*</span>
              </div>
              ${
                intraday?.available
                  ? `
                <div class="quality-metric-row">
                  <span class="quality-label">Offer-Days with Multiple Slots</span>
                  <span class="quality-value">${fmt.integer(intraday.offer_days_with_multiple_slots ?? null)}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">Mean Intraday CV</span>
                  <span class="quality-value">${intraday.mean_intraday_cv_pct != null ? `${intraday.mean_intraday_cv_pct.toFixed(2)}%` : '—'}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">95th Percentile Intraday CV</span>
                  <span class="quality-value">${intraday.p95_intraday_cv_pct != null ? `${intraday.p95_intraday_cv_pct.toFixed(2)}%` : '—'}</span>
                </div>
                ${intraday.note ? `<p class="text-small" style="color: var(--color-text-tertiary); margin-top: var(--space-10);">${intraday.note}</p>` : ''}
              `
                  : `
                <div class="empty-state-container" style="padding: 24px 12px;">
                  <p class="text-body-muted">${intraday?.note || 'Single capture slot per day; no intraday spread to measure.'}</p>
                </div>
              `
              }
            </div>
          </div>
        </div>

        <!-- 4. Intraday CV by Advance Window -->
        ${
          windowRows.length > 0
            ? `
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Intraday CV by Advance-Purchase Window</h3>
              <p class="card-subtitle">Within-day fare coefficient of variation, broken out by booking horizon.</p>
            </div>
            <span class="badge badge-neutral">intraday.by_advance_window</span>
          </div>
          <div id="advance-window-table-mount"></div>
        </div>
        `
            : ''
        }

        <!-- 5. Sparse-Sampling Measurement Error -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Sparse-Sampling Measurement Error</h3>
              <p class="card-subtitle">Monte Carlo simulation of the error from estimating a monthly average with fewer collection days.</p>
            </div>
            <span class="badge badge-neutral">sampling_error.*</span>
          </div>
          ${
            samplingAvailable
              ? `
            <div style="background-color: var(--color-bg-surface-subtle); padding: var(--space-10) var(--space-12); border-radius: var(--radius-xs); margin-bottom: var(--space-12); font-size: var(--font-size-small); color: var(--color-text-primary); border-left: 3px solid var(--color-brand-secondary);">
              ${samplingError?.headline || 'Sparse collection carries measurable estimation error.'}
            </div>
            <div class="grid-12" style="margin-bottom: var(--space-12);">
              <div class="col-6">
                <div class="quality-metric-row">
                  <span class="quality-label">1-Day/Month MAE</span>
                  <span class="quality-value" style="color: var(--color-status-danger);">${oneDayPerMonth?.mae_pct != null ? `${oneDayPerMonth.mae_pct.toFixed(2)}%` : '—'}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">1-Day/Month RMSE</span>
                  <span class="quality-value">${oneDayPerMonth?.rmse_pct != null ? `${oneDayPerMonth.rmse_pct.toFixed(2)}%` : '—'}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">95th Percentile Abs Error</span>
                  <span class="quality-value">${oneDayPerMonth?.p95_abs_pct != null ? `${oneDayPerMonth.p95_abs_pct.toFixed(2)}%` : '—'}</span>
                </div>
              </div>
              <div class="col-6">
                <div class="quality-metric-row">
                  <span class="quality-label">Max Abs Error</span>
                  <span class="quality-value">${oneDayPerMonth?.max_abs_pct != null ? `${oneDayPerMonth.max_abs_pct.toFixed(2)}%` : '—'}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">Direction Error Rate</span>
                  <span class="quality-value" style="color: var(--color-status-warning);">${oneDayPerMonth?.direction_error_rate != null ? `${(oneDayPerMonth.direction_error_rate * 100).toFixed(1)}%` : '—'}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">Direction Comparisons (N)</span>
                  <span class="quality-value">${fmt.integer(oneDayPerMonth?.n_direction_comparisons ?? null)}</span>
                </div>
              </div>
            </div>

            <div class="quality-metric-row" style="margin-bottom: var(--space-12);">
              <span class="quality-label">Required Days/Month for &le; ${requiredDays?.target_mae_pct != null ? requiredDays.target_mae_pct.toFixed(1) : '1.0'}% MAE</span>
              <span class="quality-value" style="color: var(--color-status-success);">
                ${
                  requiredDays == null
                    ? '—'
                    : requiredDays.achieved && requiredDays.required_days_per_month != null
                      ? `${requiredDays.required_days_per_month} collection days/month`
                      : `Not achieved within simulated range`
                }
              </span>
            </div>

            ${
              curveRows.length > 0
                ? `
              <div id="sampling-curve-chart-canvas" style="margin-bottom: var(--space-12);"></div>
              <div id="sampling-curve-table-mount"></div>
            `
                : ''
            }
          `
              : `
            <div class="empty-state-container" style="padding: 24px 12px;">
              <p class="text-body-muted">${samplingError?.reason || 'Insufficient daily points for Monte Carlo error simulation.'}</p>
            </div>
          `
          }
        </div>

      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);

    // Mount StatCards
    const kpi1 = page.querySelector('#vol-kpi-1');
    const kpi2 = page.querySelector('#vol-kpi-2');
    const kpi3 = page.querySelector('#vol-kpi-3');
    const kpi4 = page.querySelector('#vol-kpi-4');

    if (kpi1) {
      kpi1.appendChild(
        StatCard.render({
          label: 'DAILY VOLATILITY',
          value: daily.daily_volatility_pct != null ? daily.daily_volatility_pct.toFixed(2) : '—',
          unit: '%',
          hint: 'Std dev of day-on-day movement',
          status: 'neutral'
        })
      );
    }

    if (kpi2) {
      kpi2.appendChild(
        StatCard.render({
          label: 'MAX DAILY MOVE',
          value: daily.max_daily_move_pct != null ? daily.max_daily_move_pct.toFixed(2) : '—',
          unit: '%',
          hint: 'Largest single-day absolute move',
          status: 'neutral'
        })
      );
    }

    if (kpi3) {
      kpi3.appendChild(
        StatCard.render({
          label: '1-DAY/MO SAMPLING MAE',
          value: oneDayPerMonth?.mae_pct != null ? oneDayPerMonth.mae_pct.toFixed(2) : '—',
          unit: '%',
          hint: 'Monthly sparse-sampling error loss',
          status: 'danger'
        })
      );
    }

    if (kpi4) {
      kpi4.appendChild(
        StatCard.render({
          label: 'REQUIRED DAYS FOR TARGET MAE',
          value: requiredDays?.achieved && requiredDays.required_days_per_month != null ? String(requiredDays.required_days_per_month) : '—',
          unit: requiredDays?.achieved ? 'days/mo' : '',
          hint: `Target &le; ${requiredDays?.target_mae_pct != null ? requiredDays.target_mae_pct.toFixed(1) : '1.0'}% MAE`,
          status: 'success'
        })
      );
    }

    // Mount advance-window table
    const windowMount = page.querySelector<HTMLElement>('#advance-window-table-mount');
    if (windowMount && windowRows.length > 0) {
      const columns: TableColumn<AdvanceWindowRow>[] = [
        {
          key: 'advance_days',
          label: 'Advance Window',
          width: '180px',
          render: (row) => `<span class="code-badge" style="font-weight: 600;">T+${row.advance_days} Days</span>`
        },
        {
          key: 'cv_pct',
          label: 'Mean Intraday CV',
          align: 'right',
          render: (row) => `<span class="metric-tabular" style="font-weight: 700;">${row.cv_pct.toFixed(2)}%</span>`
        }
      ];
      this.windowTable.render(windowMount, {
        columns,
        data: windowRows,
        keyField: 'advance_days',
        emptyMessage: 'No intraday advance-window data available.'
      });
    }

    // Mount sampling-error curve chart + table
    if (curveRows.length > 0) {
      const chartCanvas = page.querySelector<HTMLElement>('#sampling-curve-chart-canvas');
      if (chartCanvas) {
        const seriesList: ChartSeries[] = [
          {
            id: 'mae',
            name: 'MAE %',
            color: 'var(--color-status-danger)',
            points: curveRows.map((r) => ({ x: `T+${r.days_per_month}`, y: r.mae_pct }))
          },
          {
            id: 'p95',
            name: 'P95 Abs Error %',
            color: 'var(--color-brand-secondary)',
            points: curveRows.map((r) => ({ x: `T+${r.days_per_month}`, y: r.p95_abs_pct }))
          }
        ];
        TimeSeriesChart.render(chartCanvas, {
          series: seriesList,
          dateAxis: false,
          yFormat: (v) => `${v.toFixed(1)}%`
        });
      }

      const curveMount = page.querySelector<HTMLElement>('#sampling-curve-table-mount');
      if (curveMount) {
        const columns: TableColumn<SamplingCurveRow>[] = [
          {
            key: 'days_per_month',
            label: 'Collection Days/Month',
            render: (row) => `<span class="code-badge" style="font-weight: 600;">${row.days_per_month}</span>`
          },
          {
            key: 'mae_pct',
            label: 'MAE %',
            align: 'right',
            render: (row) => `<span class="metric-tabular" style="font-weight: 700;">${row.mae_pct.toFixed(2)}%</span>`
          },
          {
            key: 'p95_abs_pct',
            label: 'P95 Abs Error %',
            align: 'right',
            render: (row) => `<span class="metric-tabular">${row.p95_abs_pct.toFixed(2)}%</span>`
          },
          {
            key: 'direction_error_rate',
            label: 'Direction Error Rate',
            align: 'right',
            render: (row) => `<span class="metric-tabular">${(row.direction_error_rate * 100).toFixed(1)}%</span>`
          }
        ];
        this.curveTable.render(curveMount, {
          columns,
          data: curveRows,
          keyField: 'days_per_month',
          emptyMessage: 'No sampling-error curve data available.'
        });
      }
    }
  }
}
