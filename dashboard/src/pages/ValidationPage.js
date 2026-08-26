/**
 * AIPI Screen 5: Statistical Validation & Quality Assurance (ES Module)
 */

import { api, ApiError } from '../api/client.js';
import { EnterpriseTable } from '../components/EnterpriseTable.js';
import { ErrorState } from '../components/ErrorState.js';
import { StatCard } from '../components/StatCard.js';
import { TimeSeriesChart } from '../components/TimeSeriesChart.js';
import { Icons } from '../icons/index.js';
import { escapeHtml, htmlToElement } from '../utils/dom.js';

export class ValidationPage {
  constructor(callbacks = {}) {
    this.callbacks = callbacks;
    this.container = null;

    this.validationData = null;
    this.volatilityData = null;
    this.loading = false;
    this.error = null;

    this.tableInstance = new EnterpriseTable();
    this.abortController = null;
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
      const [val, vol] = await Promise.all([
        api.getValidationDgca(signal),
        api.getVolatility(signal)
      ]);

      if (signal.aborted) return;

      this.validationData = val;
      this.volatilityData = vol;
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
      <div class="validation-loading-layout">
        <!-- 1. Caveat Banner Skeleton -->
        <div class="stat-card skeleton-shimmer stat-large" style="height: 110px; margin-bottom: var(--space-20);"></div>

        <!-- 2. KPI Grid Skeletons -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
        </div>

        <!-- 3. Dual-Line Chart Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 380px; margin-bottom: var(--space-20);"></div>

        <!-- 4. Quality Diagnostics Skeleton -->
        <div class="grid-12">
          <div class="col-6"><div class="card-container skeleton-shimmer" style="height: 240px;"></div></div>
          <div class="col-6"><div class="card-container skeleton-shimmer" style="height: 240px;"></div></div>
        </div>
      </div>
    `;
  }

  renderError() {
    ErrorState.render(this.container, {
      title: 'Failed to Load Statistical Validation Dossier',
      message: this.error?.detail || 'An unexpected error occurred while communicating with the statistical validation engine.',
      onRetry: () => this.fetchData()
    });
  }

  renderContent() {
    if (!this.container || !this.validationData || !this.volatilityData) return;

    const val = this.validationData;
    const vol = this.volatilityData;

    if (val.available === false) {
      this.container.innerHTML = `
        <div class="card-container" style="border-left: 4px solid var(--color-status-warning); padding: 32px 24px;">
          <div style="display: flex; gap: 16px; align-items: flex-start;">
            <div style="color: var(--color-status-warning);">${Icons.warning()}</div>
            <div>
              <h2 class="text-h2" style="margin-bottom: 8px;">Validation Reference Not Loaded</h2>
              <p class="text-body-muted" style="max-width: 600px; margin-bottom: 16px;">
                ${escapeHtml(val.reason) || 'No external DGCA reference series is loaded in this store snapshot. Seed a synthetic reference or load official DGCA monthly statistics.'}
              </p>
              <span class="badge badge-neutral">Operational State: Pre-Validation</span>
            </div>
          </div>
        </div>
      `;
      return;
    }

    const panel = val.route_month_panel;
    const national = val.national_monthly;
    const construct = val.construct_validity || {};
    const samplingError = vol.sampling_error;

    const isMonotone = construct.leadtime_monotone_decreasing !== false;
    const leadtimeSpread = construct.leadtime_spread_pct != null ? `${construct.leadtime_spread_pct}%` : '—';
    const dailyVol = vol.daily?.daily_volatility_pct != null ? `${vol.daily.daily_volatility_pct.toFixed(2)}%` : '—';
    const maxDailyMove = vol.daily?.max_daily_move_pct != null ? `${vol.daily.max_daily_move_pct.toFixed(2)}%` : '—';
    const isSuspiciouslyFlat = vol.daily?.suspiciously_flat === true;

    const tableRows = [];
    if (panel) {
      tableRows.push({
        comparison: 'Route-Month Panel (Primary Estimator)',
        n: panel.n,
        pearson_r: panel.pearson_r != null ? panel.pearson_r.toFixed(4) : 'Below N=8 Threshold',
        spearman_rho: panel.spearman_rho != null ? panel.spearman_rho.toFixed(4) : 'Below N=8 Threshold',
        mape_pct: panel.mape_pct != null ? `${panel.mape_pct.toFixed(2)}%` : '—',
        directional_accuracy: panel.directional_accuracy != null ? `${(panel.directional_accuracy * 100).toFixed(1)}%` : '—',
        status: panel.insufficient_n ? 'Under-powered' : 'Statistically Robust'
      });
    }

    if (national) {
      tableRows.push({
        comparison: 'National Monthly Aggregate',
        n: national.n,
        pearson_r: national.pearson_r != null ? national.pearson_r.toFixed(4) : 'Below N=8 Threshold',
        spearman_rho: national.spearman_rho != null ? national.spearman_rho.toFixed(4) : 'Below N=8 Threshold',
        mape_pct: national.mape_pct != null ? `${national.mape_pct.toFixed(2)}%` : '—',
        directional_accuracy: national.directional_accuracy != null ? `${(national.directional_accuracy * 100).toFixed(1)}%` : '—',
        status: national.insufficient_n ? 'Under-powered (N < 8)' : 'Robust'
      });
    }

    const page = htmlToElement(`
      <div class="validation-page-root">
        
        <!-- 1. Headline Caveat & Data Lineage Banner -->
        <div class="card-container" style="margin-bottom: var(--space-20); border-left: 4px solid var(--color-status-warning); background: linear-gradient(180deg, var(--color-bg-surface) 0%, var(--color-bg-surface-subtle) 100%);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
            <div>
              <div class="text-label" style="color: var(--color-status-warning); margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
                <span>ECONOMETRIC AUDIT &amp; STATISTICAL LINEAGE CAVEAT</span>
              </div>
              <p class="text-body" style="max-width: 740px; font-weight: 500; color: var(--color-text-primary); margin-bottom: 8px;">
                "${escapeHtml(val.caveat) || 'All validation figures are computed from controlled synthetic back-fills to verify pipeline correctness.'}"
              </p>
              <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px;">
                <span class="badge ${val.data_mode_breakdown?.real ? 'badge-success' : 'badge-warning'}">
                  Real Lineage: ${(val.data_mode_breakdown?.real || 0) * 100}%
                </span>
                <span class="badge badge-neutral">
                  Synthetic Share: ${(val.data_mode_breakdown?.synthetic || 0) * 100}%
                </span>
                <span class="badge ${val.reference_is_placeholder ? 'badge-warning' : 'badge-neutral'}">
                  Reference: ${val.reference_is_placeholder ? 'PLACEHOLDER BENCHMARK' : 'OFFICIAL DGCA'}
                </span>
              </div>
            </div>
            
            <div style="text-align: right;">
              <span class="badge badge-neutral" style="font-family: var(--font-family-mono);">
                GENERATED: ${val.generated_at ? new Date(val.generated_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) : '—'}
              </span>
              <div class="text-small" style="color: var(--color-text-tertiary); margin-top: 6px;">
                Primary Estimator: <b>Route-Month Pooled Panel</b>
              </div>
            </div>
          </div>
        </div>

        <!-- 2. Econometric KPI Grid -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3" id="val-kpi-1"></div>
          <div class="col-3" id="val-kpi-2"></div>
          <div class="col-3" id="val-kpi-3"></div>
          <div class="col-3" id="val-kpi-4"></div>
        </div>

        <!-- 3. Dual-Line Benchmark Overlay: AIPI vs DGCA -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">National Index vs DGCA Reference Benchmark</h3>
              <p class="card-subtitle">Monthly percentage movement comparison (Base Period = 100.0). AIPI fixed basket vs DGCA transacted average fares.</p>
            </div>
            
            <!-- Legend Bar -->
            <div style="display: flex; gap: 16px; align-items: center; font-size: 11px; color: var(--color-text-secondary);">
              <div style="display: flex; align-items: center; gap: 4px;">
                <span style="width: 14px; height: 3px; background-color: var(--color-brand-primary); border-radius: 2px;"></span>
                <span>AIPI Monthly Aggregate</span>
              </div>
              <div style="display: flex; align-items: center; gap: 4px;">
                <span style="width: 14px; height: 3px; background-color: #C97A3E; border-radius: 2px;"></span>
                <span>DGCA Reference Fares</span>
              </div>
              <div style="display: flex; align-items: center; gap: 4px;">
                <span style="width: 14px; height: 1.5px; border-top: 1.5px dashed var(--color-chart-baseline);"></span>
                <span>Baseline (100.0)</span>
              </div>
            </div>
          </div>

          <!-- Dual-Line Chart Mount -->
          <div id="dgca-comparison-chart-canvas"></div>
        </div>

        <!-- 4. Construct Validity & Measurement Error Panel -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <!-- Col 6: Internal Construct Validity -->
          <div class="col-6">
            <div class="card-container" style="height: 100%;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Internal Construct Validity Checks</h3>
                  <p class="card-subtitle">Algorithmic behavior tests verifiable without external DGCA data.</p>
                </div>
                <span class="badge badge-success">Automated Audit</span>
              </div>

              <div class="quality-metric-row">
                <span class="quality-label">Lead-Time Monotonicity</span>
                <span class="quality-value">
                  ${isMonotone ? '<span style="color: var(--color-status-success);">Passed (Monotone Decreasing)</span>' : '<span style="color: var(--color-status-danger);">Failed (Inverted Curve)</span>'}
                </span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Booking Horizon Spread</span>
                <span class="quality-value">${leadtimeSpread} yield delta</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Daily Standard Deviation</span>
                <span class="quality-value">${dailyVol} volatility</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Max Daily Jump</span>
                <span class="quality-value">${maxDailyMove} max move</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Amadeus Drift / Flat Cache Check</span>
                <span class="quality-value">
                  ${isSuspiciouslyFlat ? '<span style="color: var(--color-status-danger);">Alarm: Suspiciously Flat</span>' : '<span style="color: var(--color-status-success);">Passed (Active Variations)</span>'}
                </span>
              </div>
            </div>
          </div>

          <!-- Col 6: Sparse-Sampling Error Simulation -->
          <div class="col-6">
            <div class="card-container" style="height: 100%;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Sparse-Sampling Measurement Error</h3>
                  <p class="card-subtitle">Monte Carlo simulation quantifying accuracy loss from low-frequency collection.</p>
                </div>
                <span class="badge badge-neutral">Monte Carlo (2,000 Draws)</span>
              </div>

              ${
                samplingError && samplingError.available !== false
                  ? `
                <div style="background-color: var(--color-bg-surface-subtle); padding: var(--space-10) var(--space-12); border-radius: var(--radius-xs); margin-bottom: var(--space-12); font-size: var(--font-size-small); color: var(--color-text-primary); border-left: 3px solid var(--color-brand-secondary);">
                  ${escapeHtml(samplingError.headline) || 'Sparse collection carries measurable estimation error.'}
                </div>

                <div class="quality-metric-row">
                  <span class="quality-label">1-Day/Month Mean Abs Error (MAE)</span>
                  <span class="quality-value" style="color: var(--color-status-danger);">${samplingError.one_day_per_month?.mae_pct != null ? `${samplingError.one_day_per_month.mae_pct.toFixed(2)}%` : '—'}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">95th Percentile Error Bound</span>
                  <span class="quality-value">${samplingError.one_day_per_month?.p95_abs_pct != null ? `${samplingError.one_day_per_month.p95_abs_pct.toFixed(2)}%` : '—'}</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">Sign / Direction Error Risk</span>
                  <span class="quality-value" style="color: var(--color-status-warning);">${samplingError.one_day_per_month?.direction_error_rate != null ? `${(samplingError.one_day_per_month.direction_error_rate * 100).toFixed(1)}%` : '—'} of draws</span>
                </div>
                <div class="quality-metric-row">
                  <span class="quality-label">Required Days for &le; ${samplingError.required_days_for_1pct_mae?.target_mae_pct != null ? samplingError.required_days_for_1pct_mae.target_mae_pct.toFixed(1) : '1.0'}% MAE</span>
                  <span class="quality-value" style="color: var(--color-status-success);">${
                    samplingError.required_days_for_1pct_mae?.achieved && samplingError.required_days_for_1pct_mae.required_days_per_month != null
                      ? `${samplingError.required_days_for_1pct_mae.required_days_per_month} collection days/month`
                      : samplingError.required_days_for_1pct_mae != null
                        ? 'Not achieved within simulated range'
                        : '—'
                  }</span>
                </div>
              `
                  : `
                <div class="empty-state-container" style="padding: 24px 12px;">
                  <p class="text-body-muted">${escapeHtml(samplingError?.reason) || 'Insufficient daily points for Monte Carlo error simulation.'}</p>
                </div>
              `
              }
            </div>
          </div>
        </div>

        <!-- 5. Estimator Comparison Audit Table -->
        <div class="card-container">
          <div class="card-header">
            <div>
              <h3 class="card-title">Econometric Backtest Estimator Comparison</h3>
              <p class="card-subtitle">Why Route-Month Pooling is required over National Aggregation to achieve statistical degrees of freedom.</p>
            </div>
            <span class="badge badge-neutral">N &ge; 8 Reporting Invariant</span>
          </div>

          <!-- Table Mount Point -->
          <div id="estimator-table-mount-point"></div>
        </div>

      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);

    // 5. Mount StatCards
    const kpi1 = page.querySelector('#val-kpi-1');
    const kpi2 = page.querySelector('#val-kpi-2');
    const kpi3 = page.querySelector('#val-kpi-3');
    const kpi4 = page.querySelector('#val-kpi-4');

    if (kpi1) {
      const rVal = panel?.pearson_r;
      kpi1.appendChild(
        StatCard.render({
          label: 'PANEL PEARSON CORRELATION (r)',
          value: rVal != null ? rVal.toFixed(4) : 'N/A (N < 8)',
          hint: `${panel?.n || 0} paired route-month movements`,
          status: rVal != null && rVal >= 0.8 ? 'success' : 'neutral'
        })
      );
    }

    if (kpi2) {
      const dirVal = panel?.directional_accuracy;
      kpi2.appendChild(
        StatCard.render({
          label: 'DIRECTIONAL ACCURACY',
          value: dirVal != null ? `${(dirVal * 100).toFixed(1)}%` : 'N/A',
          hint: 'Matching sign of MoM movement',
          status: dirVal != null && dirVal >= 0.8 ? 'success' : 'warning'
        })
      );
    }

    if (kpi3) {
      const mapeVal = panel?.mape_pct;
      kpi3.appendChild(
        StatCard.render({
          label: 'MEAN ABS % ERROR (MAPE)',
          value: mapeVal != null ? `${mapeVal.toFixed(2)}%` : 'N/A',
          hint: 'Computed on MoM percentage changes',
          status: 'neutral'
        })
      );
    }

    if (kpi4) {
      const maeVal = samplingError?.one_day_per_month?.mae_pct;
      kpi4.appendChild(
        StatCard.render({
          label: '1-DAY/MO SAMPLING ERROR',
          value: maeVal != null ? `${maeVal.toFixed(2)}%` : '—',
          hint: 'Monthly sparse-sampling error loss',
          status: 'danger'
        })
      );
    }

    // 6. Mount Dual-Line Comparison Chart
    const chartCanvas = page.querySelector('#dgca-comparison-chart-canvas');
    if (chartCanvas && val.series && val.series.length > 0) {
      const seriesList = [
        {
          id: 'aipi-national',
          name: 'AIPI Monthly Aggregate',
          color: 'var(--color-brand-primary)',
          points: val.series.map((s) => ({
            x: s.period,
            y: s.aipi_index
          }))
        },
        {
          id: 'dgca-reference',
          name: 'DGCA Benchmark Fares',
          color: '#C97A3E',
          points: val.series.map((s) => ({
            x: s.period,
            y: s.dgca_index
          }))
        }
      ];

      TimeSeriesChart.render(chartCanvas, {
        series: seriesList,
        baseline: 100.0,
        dateAxis: false
      });
    }

    // 7. Mount Enterprise Table
    const tableMount = page.querySelector('#estimator-table-mount-point');
    if (tableMount) {
      const columns = [
        {
          key: 'comparison',
          label: 'Estimator Specification',
          width: '260px',
          render: (row) => `<span style="font-weight: 600; color: var(--color-text-primary);">${row.comparison}</span>`
        },
        {
          key: 'n',
          label: 'Paired Movements (N)',
          align: 'right',
          width: '180px',
          render: (row) => `<span class="metric-tabular">${row.n} pairs</span>`
        },
        {
          key: 'pearson_r',
          label: 'Pearson r',
          align: 'right',
          width: '140px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 700;">${row.pearson_r}</span>`
        },
        {
          key: 'directional_accuracy',
          label: 'Directional Accuracy',
          align: 'right',
          width: '170px',
          render: (row) => `<span class="metric-tabular">${row.directional_accuracy}</span>`
        },
        {
          key: 'mape_pct',
          label: 'MAPE %',
          align: 'right',
          width: '140px',
          render: (row) => `<span class="metric-tabular">${row.mape_pct}</span>`
        },
        {
          key: 'status',
          label: 'Statistical Quality',
          align: 'center',
          width: '160px',
          render: (row) =>
            row.status.includes('Robust')
              ? '<span class="badge badge-success">Robust Estimator</span>'
              : '<span class="badge badge-warning">Under-Powered</span>'
        }
      ];

      this.tableInstance.render(tableMount, {
        columns,
        data: tableRows,
        keyField: 'comparison',
        emptyMessage: 'No backtest estimator data available.',
        ariaLabel: 'Econometric backtest estimator comparison table'
      });
    }
  }
}
