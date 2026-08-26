/**
 * AIPI Screen 1: Executive Overview (Headline Inflation Monitor - ES Module)
 */

import { api, ApiError } from '../api/client.js';
import { ErrorState } from '../components/ErrorState.js';
import { StatCard } from '../components/StatCard.js';
import { TimeSeriesChart } from '../components/TimeSeriesChart.js';
import { htmlToElement } from '../utils/dom.js';
import { fmt } from '../utils/formatters.js';

export class OverviewPage {
  constructor(callbacks = {}) {
    this.callbacks = callbacks;
    this.container = null;

    // Filter & Control States
    this.freq = 'daily';
    this.dowAdjusted = false;
    this.dateFrom = '';
    this.dateTo = '';

    // Data States
    this.headlineData = null;
    this.headlineAdjData = null;
    this.healthData = null;
    this.pipelineData = null;
    this.loading = false;
    this.error = null;

    // Request lifecycle: cancels a stale in-flight fetch when a new one starts
    // so a slow earlier response can never overwrite newer filter state.
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
      // 1. Parallel fetch of Health, PipelineRun, and Headline Index
      const [health, pipeline, headline] = await Promise.all([
        api.getHealth(signal).catch(() => null),
        api.getPipelineRun(signal).catch(() => null),
        api.getHeadlineIndex(
          {
            freq: this.freq,
            dowAdjusted: false,
            from: this.dateFrom || undefined,
            to: this.dateTo || undefined
          },
          signal
        )
      ]);

      if (signal.aborted) return;

      this.healthData = health;
      this.pipelineData = pipeline;
      this.headlineData = headline;

      // 2. If DoW adjustment is checked (only allowed on daily), fetch adjusted series in parallel
      if (this.dowAdjusted && this.freq === 'daily') {
        this.headlineAdjData = await api
          .getHeadlineIndex(
            {
              freq: 'daily',
              dowAdjusted: true,
              from: this.dateFrom || undefined,
              to: this.dateTo || undefined
            },
            signal
          )
          .catch(() => null);
      } else {
        this.headlineAdjData = null;
      }

      if (signal.aborted) return;

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
      <div class="overview-loading-layout">
        <!-- 1. Executive Summary Skeleton -->
        <div class="stat-card skeleton-shimmer stat-large" style="height: 120px; margin-bottom: var(--space-20);"></div>

        <!-- 2. Primary KPI Grid Skeletons -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
        </div>

        <!-- 3. Chart Container Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 380px; margin-bottom: var(--space-20);"></div>

        <!-- 4. Quality & Pipeline Grid Skeletons -->
        <div class="grid-12">
          <div class="col-6"><div class="card-container skeleton-shimmer" style="height: 220px;"></div></div>
          <div class="col-6"><div class="card-container skeleton-shimmer" style="height: 220px;"></div></div>
        </div>
      </div>
    `;
  }

  renderError() {
    ErrorState.render(this.container, {
      title: 'Failed to Load Headline Index',
      message: this.error?.detail || 'An unexpected error occurred while communicating with the index engine.',
      onRetry: () => this.fetchData()
    });
  }

  renderContent() {
    if (!this.container || !this.headlineData) return;

    const points = this.headlineData.points || [];
    const latestPoint = points.length > 0 ? points[points.length - 1] : null;
    const priorPoint = points.length > 1 ? points[points.length - 2] : null;

    // Calculations
    const latestValue = latestPoint ? latestPoint.value : null;
    const deltaFromBase = latestValue != null ? latestValue - 100.0 : null;
    const deltaFromPrior = latestValue != null && priorPoint != null ? latestValue - priorPoint.value : null;

    const page = htmlToElement(`
      <div class="overview-page-root">
        
        <!-- 1. Executive Summary Headline Banner -->
        <div class="card-container" style="margin-bottom: var(--space-20); background: linear-gradient(180deg, var(--color-bg-surface) 0%, var(--color-bg-surface-subtle) 100%); border-left: 4px solid var(--color-brand-primary);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
            <div>
              <div class="text-label" style="color: var(--color-text-secondary); margin-bottom: 4px;">
                NATIONAL AIRFARE PRICE INDEX (AIPI)
              </div>
              <div style="display: flex; align-items: baseline; gap: 12px;">
                <span class="metric-large" style="font-size: 36px; color: var(--color-brand-primary);">
                  ${fmt.index(latestValue, 2)}
                </span>
                <span class="text-h3" style="color: var(--color-text-secondary);">points</span>
                <span class="stat-delta ${deltaFromBase != null && deltaFromBase >= 0 ? 'delta-positive' : 'delta-negative'}" style="font-size: 13px;">
                  ${fmt.signedDelta(deltaFromBase, '%', 2)} vs Base Period
                </span>
              </div>
              <p class="text-body-muted" style="margin-top: 8px; max-width: 640px;">
                Laspeyres expenditure-weighted aggregation of rolling GEKS-Jevons multilateral airfare relatives across 12 primary domestic routes.
              </p>
            </div>
            
            <div style="text-align: right;">
              <span class="badge badge-neutral" style="font-family: var(--font-family-mono);">
                BASE WINDOW: ${this.headlineData.base_period.start || '—'} … ${this.headlineData.base_period.end || '—'} (=100.0)
              </span>
              <div class="text-small" style="color: var(--color-text-tertiary); margin-top: 6px;">
                Last observation date: <b>${latestPoint ? latestPoint.date : '—'}</b>
              </div>
            </div>
          </div>
        </div>

        <!-- 2. Primary KPI Grid -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3" id="kpi-card-1"></div>
          <div class="col-3" id="kpi-card-2"></div>
          <div class="col-3" id="kpi-card-3"></div>
          <div class="col-3" id="kpi-card-4"></div>
        </div>

        <!-- 3. Market Trend Time Series Chart Panel -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="chart-controls-bar">
            <!-- Left: Frequency Selector -->
            <div class="controls-left">
              <div class="segmented-control" role="tablist" aria-label="Frequency Selector">
                <button class="segmented-control-item ${this.freq === 'daily' ? 'active' : ''}" data-freq="daily" role="tab" aria-selected="${this.freq === 'daily'}">Daily</button>
                <button class="segmented-control-item ${this.freq === 'weekly' ? 'active' : ''}" data-freq="weekly" role="tab" aria-selected="${this.freq === 'weekly'}">Weekly</button>
                <button class="segmented-control-item ${this.freq === 'monthly' ? 'active' : ''}" data-freq="monthly" role="tab" aria-selected="${this.freq === 'monthly'}">Monthly</button>
              </div>

              <!-- Day of Week Toggle (Strict Backend Guardrail: Only for Daily) -->
              <label class="toggle-label ${this.freq !== 'daily' ? 'disabled' : ''}" 
                     title="${this.freq !== 'daily' ? 'Day-of-Week adjustment is applicable only to Daily frequency' : 'Toggle multiplicative 7-day seasonal adjustment'}">
                <input type="checkbox" id="dow-toggle-checkbox" ${this.dowAdjusted ? 'checked' : ''} ${this.freq !== 'daily' ? 'disabled' : ''} />
                <span>Day-of-Week Adjusted</span>
              </label>
            </div>

            <!-- Right: Date Range Slicing -->
            <div class="controls-right">
              <div class="filter-input-group">
                <label for="date-from-input">From:</label>
                <input type="date" id="date-from-input" class="filter-input" value="${this.dateFrom}" />
              </div>
              <div class="filter-input-group">
                <label for="date-to-input">To:</label>
                <input type="date" id="date-to-input" class="filter-input" value="${this.dateTo}" />
              </div>
              <button class="empty-state-action-btn" id="apply-filter-btn" style="padding: 4px 10px; font-size: 12px;">Apply</button>
              ${this.dateFrom || this.dateTo ? '<button class="breadcrumb-link" id="reset-filter-btn" style="font-size: 12px;">Reset</button>' : ''}
            </div>
          </div>

          <!-- Chart Render Canvas -->
          <div id="headline-chart-canvas"></div>

          <!-- Legend Bar -->
          <div style="display: flex; gap: 20px; align-items: center; font-size: 12px; color: var(--color-text-secondary); margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="display: inline-block; width: 14px; height: 3px; background-color: var(--color-brand-primary); border-radius: 2px;"></span>
              <span>Headline Index (${this.freq})</span>
            </div>
            ${
              this.dowAdjusted && this.freq === 'daily'
                ? `
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="display: inline-block; width: 14px; height: 3px; background-color: var(--color-brand-secondary); border-radius: 2px;"></span>
                <span>Seasonally Adjusted (DoW)</span>
              </div>
            `
                : ''
            }
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="display: inline-block; width: 14px; height: 1.5px; border-top: 1.5px dashed var(--color-chart-baseline);"></span>
              <span>Base Period Benchmark (100.0)</span>
            </div>
          </div>
        </div>

        <!-- 4. Quality & Provenance Panel -->
        <div class="grid-12">
          <!-- Col 6: Data Quality Panel -->
          <div class="col-6">
            <div class="card-container" style="height: 100%;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Sample Quality &amp; Governance</h3>
                  <p class="card-subtitle">Observation health across the current index series.</p>
                </div>
                <span class="badge badge-success">Quality Assured</span>
              </div>

              <div class="quality-metric-row">
                <span class="quality-label">Latest Sample Coverage</span>
                <span class="quality-value">${fmt.percent(latestPoint?.coverage_pct, 1)} of basket</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Matched Quotation Pairs</span>
                <span class="quality-value">${fmt.integer(latestPoint?.matched_n)} pairs</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Total Observations in Period</span>
                <span class="quality-value">${fmt.integer(latestPoint?.n_obs)} quotes</span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Resampling Completeness</span>
                <span class="quality-value">
                  ${latestPoint?.is_complete === false ? '<span style="color: var(--color-status-warning);">Incomplete (' + latestPoint?.n_days + '/' + latestPoint?.expected_days + ' days)</span>' : '<span style="color: var(--color-status-success);">Complete (100%)</span>'}
                </span>
              </div>
              <div class="quality-metric-row">
                <span class="quality-label">Data Lineage</span>
                <span class="quality-value">
                  ${this.headlineData.data_mode.is_demo_data ? '<span style="color: var(--color-status-warning);">Simulated (Demo Mode)</span>' : '<span style="color: var(--color-status-success);">100% Live Market</span>'}
                </span>
              </div>
            </div>
          </div>

          <!-- Col 6: Pipeline Provenance Card -->
          <div class="col-6">
            <div class="card-container" style="height: 100%;">
              <div class="card-header">
                <div>
                  <h3 class="card-title">Pipeline Provenance &amp; Run Lineage</h3>
                  <p class="card-subtitle">Cryptographic execution fingerprint (SHA-256).</p>
                </div>
                <span class="badge badge-neutral">Immutable Vintage</span>
              </div>

              <div class="meta-key-value">
                <span class="meta-key">RUN ID</span>
                <span class="meta-value">${this.pipelineData?.run_id || '—'}</span>

                <span class="meta-key">GIT SHA</span>
                <span class="meta-value">${this.pipelineData?.git_sha ? this.pipelineData.git_sha.slice(0, 16) : '—'}</span>

                <span class="meta-key">CONFIG HASH</span>
                <span class="meta-value">${this.pipelineData?.config_hash ? this.pipelineData.config_hash.slice(0, 16) : '—'}</span>

                <span class="meta-key">INPUT ROWS</span>
                <span class="meta-value">${fmt.integer(this.pipelineData?.input_row_count)} quotes</span>

                <span class="meta-key">INDEX ELIGIBLE</span>
                <span class="meta-value">${fmt.integer(this.pipelineData?.index_eligible_rows)} accepted</span>

                <span class="meta-key">COMPUTED AT</span>
                <span class="meta-value">${this.pipelineData?.created_at ? new Date(this.pipelineData.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }) + ' IST' : '—'}</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);

    // 5. Mount Reusable StatCards
    const kpi1 = page.querySelector('#kpi-card-1');
    const kpi2 = page.querySelector('#kpi-card-2');
    const kpi3 = page.querySelector('#kpi-card-3');
    const kpi4 = page.querySelector('#kpi-card-4');

    if (kpi1) {
      kpi1.appendChild(
        StatCard.render({
          label: 'CURRENT INDEX LEVEL',
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
          label: 'NET INFLATION VS BASE',
          value: fmt.signedDelta(deltaFromBase, '%', 2),
          hint: `Base window mean: 100.0 pts`,
          status: deltaFromBase != null && deltaFromBase > 0 ? 'danger' : 'success'
        })
      );
    }

    if (kpi3) {
      kpi3.appendChild(
        StatCard.render({
          label: 'SAMPLE COVERAGE',
          value: fmt.percent(latestPoint?.coverage_pct, 1),
          hint: `${latestPoint?.n_obs || 0} observations processed`,
          status: (latestPoint?.coverage_pct || 0) >= 90 ? 'success' : 'warning'
        })
      );
    }

    if (kpi4) {
      kpi4.appendChild(
        StatCard.render({
          label: 'MATCHED PAIR PURITY',
          value: fmt.integer(latestPoint?.matched_n),
          unit: 'pairs',
          hint: 'Jevons matched quote links',
          status: 'neutral'
        })
      );
    }

    // 6. Mount TimeSeriesChart SVG
    const chartCanvas = page.querySelector('#headline-chart-canvas');
    if (chartCanvas) {
      const seriesList = [
        {
          id: 'headline',
          name: `Headline (${this.freq})`,
          color: 'var(--color-brand-primary)',
          points: points.map((p) => ({
            x: p.date,
            y: p.value,
            nObs: p.n_obs,
            coveragePct: p.coverage_pct,
            isComplete: p.is_complete
          }))
        }
      ];

      if (this.headlineAdjData && this.headlineAdjData.points) {
        seriesList.push({
          id: 'headline-adj',
          name: 'DoW Adjusted',
          color: 'var(--color-brand-secondary)',
          points: this.headlineAdjData.points.map((p) => ({
            x: p.date,
            y: p.value,
            nObs: p.n_obs,
            coveragePct: p.coverage_pct,
            isComplete: p.is_complete
          }))
        });
      }

      TimeSeriesChart.render(chartCanvas, {
        series: seriesList,
        baseline: 100.0
      });
    }

    // 7. Attach Interactive Control Listeners
    this.attachControlListeners(page);
  }

  attachControlListeners(page) {
    // Frequency buttons
    const freqBtns = page.querySelectorAll('.segmented-control-item');
    freqBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const newFreq = btn.dataset.freq;
        if (newFreq && newFreq !== this.freq) {
          this.freq = newFreq;
          // Backend Guardrail: if freq is not daily, dowAdjusted MUST be false
          if (this.freq !== 'daily') {
            this.dowAdjusted = false;
          }
          this.fetchData();
        }
      });
    });

    // DoW Checkbox
    const dowCheckbox = page.querySelector('#dow-toggle-checkbox');
    if (dowCheckbox) {
      dowCheckbox.addEventListener('change', () => {
        if (this.freq === 'daily') {
          this.dowAdjusted = dowCheckbox.checked;
          this.fetchData();
        }
      });
    }

    // Date range filters
    const fromInput = page.querySelector('#date-from-input');
    const toInput = page.querySelector('#date-to-input');
    const applyBtn = page.querySelector('#apply-filter-btn');
    const resetBtn = page.querySelector('#reset-filter-btn');

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
