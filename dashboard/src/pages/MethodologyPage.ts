/**
 * AIPI Screen 6: Methodology & Governance Dossier
 * 
 * Formal statistical publication dossier consuming:
 * - GET /api/v1/methodology
 * - GET /api/v1/pipeline-run
 */

import { api, ApiError } from '../api/client.js';
import { EnterpriseTable, TableColumn } from '../components/EnterpriseTable.js';
import { StatCard } from '../components/StatCard.js';
import { Icons } from '../icons/index.js';
import { MethodologyResponse, PipelineRunModel } from '../types/api.js';
import { htmlToElement } from '../utils/dom.js';
import { fmt } from '../utils/formatters.js';

interface WeightRow {
  route_code: string;
  weight: number;
  weight_pct: string;
}

interface QuarantineRow {
  reason: string;
  count: number;
  share_pct: string;
}

export interface MethodologyCallbacks {
  onNotify?: (type: 'success' | 'warning' | 'error' | 'info', title: string, message?: string) => void;
}

export class MethodologyPage {
  private container: HTMLElement | null = null;
  private callbacks: MethodologyCallbacks;

  // Data States
  private methodologyData: MethodologyResponse | null = null;
  private pipelineData: PipelineRunModel | null = null;
  private loading = false;
  private error: ApiError | null = null;

  private showRawJson = false;

  private weightsTable = new EnterpriseTable<WeightRow>();
  private quarantineTable = new EnterpriseTable<QuarantineRow>();

  constructor(callbacks: MethodologyCallbacks = {}) {
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
      const [meth, pipe] = await Promise.all([
        api.getMethodology(),
        api.getPipelineRun()
      ]);

      this.methodologyData = meth;
      this.pipelineData = pipe;
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
      <div class="methodology-loading-layout">
        <!-- 1. Banner Skeleton -->
        <div class="stat-card skeleton-shimmer stat-large" style="height: 120px; margin-bottom: var(--space-20);"></div>

        <!-- 2. KPI Grid Skeletons -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
          <div class="col-3">${StatCard.renderSkeleton().outerHTML}</div>
        </div>

        <!-- 3. Formulae Grid Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 320px; margin-bottom: var(--space-20);"></div>

        <!-- 4. Cleaning Row Accounting Skeleton -->
        <div class="card-container skeleton-shimmer" style="height: 280px;"></div>
      </div>
    `;
  }

  private renderError(): void {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="card-container" style="border-left: 4px solid var(--color-status-danger); padding: 32px 24px; text-align: center;">
        <div style="color: var(--color-status-danger); margin-bottom: 12px;">${Icons.danger()}</div>
        <h2 class="text-h2" style="margin-bottom: 8px;">Failed to Load Methodology Dossier</h2>
        <p class="text-body-muted" style="max-width: 480px; margin: 0 auto 16px;">
          ${this.error?.detail || 'An unexpected error occurred while communicating with the methodology registry.'}
        </p>
        <button class="empty-state-action-btn" id="retry-methodology-btn">Retry Connection</button>
      </div>
    `;

    const retryBtn = this.container.querySelector('#retry-methodology-btn');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => this.fetchData());
    }
  }

  private renderContent(): void {
    if (!this.container || !this.methodologyData) return;

    const m = this.methodologyData;
    const p = this.pipelineData;
    const cleaning = m.cleaning || {};
    const diag = m.diagnostics || {};
    const base = m.base_period || {};
    const weights = m.route_weights || {};

    const weightRows: WeightRow[] = Object.entries(weights)
      .map(([code, w]) => ({
        route_code: code,
        weight: w,
        weight_pct: `${(w * 100).toFixed(2)}%`
      }))
      .sort((a, b) => b.weight - a.weight);

    const quarantineReasons = cleaning.quarantine_reasons || {};
    const totalQuarantined = cleaning.rows_quarantined || 0;
    const quarantineRows: QuarantineRow[] = Object.entries(quarantineReasons).map(([reason, count]) => ({
      reason,
      count: count as number,
      share_pct: totalQuarantined > 0 ? `${(((count as number) / totalQuarantined) * 100).toFixed(1)}%` : '0.0%'
    }));

    const page = htmlToElement(`
      <div class="methodology-page-root">
        
        <!-- 1. Official Publication Banner -->
        <div class="card-container" style="margin-bottom: var(--space-20); background: linear-gradient(180deg, var(--color-bg-surface) 0%, var(--color-bg-surface-subtle) 100%); border-left: 4px solid var(--color-brand-primary);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
            <div>
              <div class="text-label" style="color: var(--color-text-secondary); margin-bottom: 4px;">
                OFFICIAL METHODOLOGY SPECIFICATION &amp; GOVERNANCE DOSSIER
              </div>
              <h1 class="text-h1" style="color: var(--color-text-primary); margin-bottom: 8px;">
                ${m.title || 'Real-Time Airfare Price Index for India (AIPI)'}
              </h1>
              <p class="text-body-muted" style="max-width: 720px;">
                ${m.disclaimer || 'Methodology proof of concept for SIH 2026 PS 26056 (MoSPI). Built to candidate CPI component standards.'}
              </p>
              <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;">
                <span class="badge badge-neutral" style="font-family: var(--font-family-mono);">
                  FINGERPRINT: ${typeof m.fingerprint === 'string' ? m.fingerprint.slice(0, 16) : `GEKS W=${(m.fingerprint as any)?.geks_window_days || 25}d · MAD k=${(m.fingerprint as any)?.mad_trim_k || 3.5}`}
                </span>
                <span class="badge badge-neutral">
                  BASE WINDOW: ${base.start || '—'} … ${base.end || '—'} (${base.n_days || 0} days = 100.0)
                </span>
                <span class="badge badge-success">
                  RETENTION: ${cleaning.retention_pct != null ? `${cleaning.retention_pct}%` : '—'}
                </span>
              </div>
            </div>
            
            <div style="text-align: right;">
              <span class="badge badge-neutral" style="font-family: var(--font-family-mono);">
                RUN ID: ${p?.run_id || '—'}
              </span>
              <div class="text-small" style="color: var(--color-text-tertiary); margin-top: 6px;">
                Git Commit: <span style="font-family: var(--font-family-mono); font-weight: 600;">${p?.git_sha ? p.git_sha.slice(0, 12) : '—'}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 2. Primary Provenance & Metric KPI Grid -->
        <div class="grid-12" style="margin-bottom: var(--space-20);">
          <div class="col-3" id="meth-kpi-1"></div>
          <div class="col-3" id="meth-kpi-2"></div>
          <div class="col-3" id="meth-kpi-3"></div>
          <div class="col-3" id="meth-kpi-4"></div>
        </div>

        <!-- 3. Mathematical Formulae Architecture -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Mathematical Formulae &amp; Aggregation Architecture</h3>
              <p class="card-subtitle">Formal index-number aggregation equations compliant with international consumer price index standards (CPI Manual).</p>
            </div>
            <span class="badge badge-neutral">IMF / ILO Standard</span>
          </div>

          <div class="grid-12">
            <!-- Col 6: Elementary Aggregate -->
            <div class="col-6" style="margin-bottom: var(--space-16);">
              <div style="background-color: var(--color-bg-surface-subtle); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-xs); padding: var(--space-16); height: 100%;">
                <div class="text-label" style="color: var(--color-brand-primary); margin-bottom: 4px;">1. ELEMENTARY AGGREGATION (CELL LEVEL)</div>
                <div style="font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px;">
                  ${m.index_number?.elementary_aggregate || 'Jevons (geometric mean of price RELATIVES) on matched items'}
                </div>
                <div style="font-family: var(--font-family-mono); font-size: 13px; background-color: var(--color-bg-surface); padding: 8px 12px; border-radius: 4px; border: 1px solid var(--color-border-strong); margin-bottom: 8px;">
                  I_{r,w,t} = ∏_{k ∈ S_{r,w,t}} ( p_{k,t} / p_{k,0} )^{ 1 / N }
                </div>
                <p class="text-small" style="color: var(--color-text-secondary);">
                  Geometric mean of price relatives on matched quotation links. Dropping sold-out items is arithmetically identical to textbook class-mean imputation.
                </p>
              </div>
            </div>

            <!-- Col 6: Multilateral GEKS -->
            <div class="col-6" style="margin-bottom: var(--space-16);">
              <div style="background-color: var(--color-bg-surface-subtle); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-xs); padding: var(--space-16); height: 100%;">
                <div class="text-label" style="color: var(--color-brand-primary); margin-bottom: 4px;">2. MULTILATERAL EXTENSION (CHAIN DRIFT FIX)</div>
                <div style="font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px;">
                  ${m.index_number?.multilateral || 'GEKS-Jevons on a rolling window with movement splice (no revision)'}
                </div>
                <div style="font-family: var(--font-family-mono); font-size: 13px; background-color: var(--color-bg-surface); padding: 8px 12px; border-radius: 4px; border: 1px solid var(--color-border-strong); margin-bottom: 8px;">
                  I_{GEKS}^{t} = ∏_{k ∈ W} ( I_{r}^{t/k} · I_{r}^{k/0} )^{ 1 / |W| }
                </div>
                <p class="text-small" style="color: var(--color-text-secondary);">
                  Rolling window multilateral aggregation eliminating downward ratcheting caused by asymmetric churn in promotional fares.
                </p>
              </div>
            </div>

            <!-- Col 6: Upper-Level Aggregation -->
            <div class="col-6">
              <div style="background-color: var(--color-bg-surface-subtle); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-xs); padding: var(--space-16); height: 100%;">
                <div class="text-label" style="color: var(--color-brand-primary); margin-bottom: 4px;">3. UPPER-LEVEL COMPOSITE AGGREGATION</div>
                <div style="font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px;">
                  ${m.index_number?.upper_aggregation || 'Laspeyres over base-period EXPENDITURE shares'}
                </div>
                <div style="font-family: var(--font-family-mono); font-size: 13px; background-color: var(--color-bg-surface); padding: 8px 12px; border-radius: 4px; border: 1px solid var(--color-border-strong); margin-bottom: 8px;">
                  I_{AIPI}^{t} = ∑_{r=1}^{12} w_{r}^{0} · I_{r}^{t} \quad \text{where } w_{r}^{0} = \frac{p_{r,0} q_{r,0}}{∑ p_{m,0} q_{m,0}}
                </div>
                <p class="text-small" style="color: var(--color-text-secondary);">
                  Fixed base-period expenditure weights derived from DGCA passenger volumes multiplied by base period route fares (not passenger counts alone).
                </p>
              </div>
            </div>

            <!-- Col 6: Seasonal Adjustment -->
            <div class="col-6">
              <div style="background-color: var(--color-bg-surface-subtle); border: 1px solid var(--color-border-subtle); border-radius: var(--radius-xs); padding: var(--space-16); height: 100%;">
                <div class="text-label" style="color: var(--color-brand-primary); margin-bottom: 4px;">4. SEASONAL DECOMPOSITION &amp; REBASING</div>
                <div style="font-weight: 600; color: var(--color-text-primary); margin-bottom: 6px;">
                  ${m.index_number?.seasonal || 'Multiplicative day-of-week adjustment'}
                </div>
                <div style="font-family: var(--font-family-mono); font-size: 13px; background-color: var(--color-bg-surface); padding: 8px 12px; border-radius: 4px; border: 1px solid var(--color-border-strong); margin-bottom: 8px;">
                  I_{adj}^{t} = I_{raw}^{t} / S_{dow(t)} \quad \text{where } \prod_{d=1}^{7} S_{d} = 1.0
                </div>
                <p class="text-small" style="color: var(--color-text-secondary);">
                  Multiplicative 7-day cyclical adjustment removing travel weekday premiums while strictly conserving geometric mean levels.
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 4. Cleaning Pipeline Row Accounting Funnel -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Cleaning Pipeline Row Accounting (11 Load-Bearing Stages)</h3>
              <p class="card-subtitle">Exact row retention and exclusion accounting from raw collected flight quotes to index-eligible observations.</p>
            </div>
            <span class="badge badge-success">${fmt.integer(cleaning.rows_index_eligible)} Accepted Rows</span>
          </div>

          <div class="grid-12" style="margin-bottom: var(--space-16);">
            <div class="col-3">
              <div class="stat-card" style="background-color: var(--color-bg-surface-subtle);">
                <span class="text-label">RAW INPUT QUOTES</span>
                <span class="metric-medium">${fmt.integer(cleaning.rows_in)}</span>
                <span class="text-small" style="color: var(--color-text-tertiary);">100.0% of batch</span>
              </div>
            </div>
            <div class="col-3">
              <div class="stat-card" style="background-color: var(--color-bg-surface-subtle);">
                <span class="text-label">QUARANTINED ROWS</span>
                <span class="metric-medium" style="color: var(--color-status-danger);">${fmt.integer(cleaning.rows_quarantined)}</span>
                <span class="text-small" style="color: var(--color-text-tertiary);">Failed schema/contract</span>
              </div>
            </div>
            <div class="col-3">
              <div class="stat-card" style="background-color: var(--color-bg-surface-subtle);">
                <span class="text-label">DEDUPLICATED</span>
                <span class="metric-medium">${fmt.integer(cleaning.rows_deduplicated)}</span>
                <span class="text-small" style="color: var(--color-text-tertiary);">Duplicate flight keys</span>
              </div>
            </div>
            <div class="col-3">
              <div class="stat-card" style="background-color: var(--color-bg-surface-subtle);">
                <span class="text-label">INDEX ELIGIBLE</span>
                <span class="metric-medium" style="color: var(--color-status-success);">${fmt.integer(cleaning.rows_index_eligible)}</span>
                <span class="text-small" style="color: var(--color-text-tertiary);">${cleaning.retention_pct}% retention rate</span>
              </div>
            </div>
          </div>

          <!-- Quarantine Breakdown Table -->
          <div id="quarantine-table-mount-point"></div>
        </div>

        <!-- 5. DGCA Expenditure Weight Master Vector (12 Routes) -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">DGCA Base-Period Expenditure Weight Master Vector</h3>
              <p class="card-subtitle">Exact expenditure share weights ($w_r$) summing to 1.000000 across all 12 tracked domestic sectors.</p>
            </div>
            <span class="badge badge-neutral">${weightRows.length} Sector Weights</span>
          </div>

          <div id="weights-table-mount-point"></div>
        </div>

        <!-- 6. Institutional Methodology Footnotes -->
        <div class="card-container" style="margin-bottom: var(--space-20);">
          <div class="card-header">
            <div>
              <h3 class="card-title">Methodological Footnotes &amp; Governance Rules</h3>
              <p class="card-subtitle">Authoritative footnotes emitted by the calculation engine.</p>
            </div>
            <span class="badge badge-neutral">Auditor Reference</span>
          </div>

          <ul style="padding-left: 20px; font-size: var(--font-size-small); color: var(--color-text-primary); line-height: 1.6;">
            ${(m.notes || []).map((n) => `<li style="margin-bottom: 6px;">${n}</li>`).join('')}
          </ul>
        </div>

        <!-- 7. Raw JSON Inspector -->
        <div class="card-container">
          <div class="card-header">
            <div>
              <h3 class="card-title">Auditor Raw JSON Payload Inspector</h3>
              <p class="card-subtitle">Direct, unmutated JSON payload emitted by GET /api/v1/methodology.</p>
            </div>
            <button class="empty-state-action-btn" id="toggle-raw-json-btn" style="padding: 4px 10px; font-size: 12px;">
              ${this.showRawJson ? 'Hide JSON' : 'Inspect Raw JSON'}
            </button>
          </div>

          <div id="raw-json-canvas" class="${this.showRawJson ? '' : 'hidden'}" style="margin-top: 12px;">
            <pre style="background-color: var(--color-bg-surface-subtle); border: 1px solid var(--color-border-strong); border-radius: var(--radius-xs); padding: 16px; font-family: var(--font-family-mono); font-size: 11px; overflow-x: auto; max-height: 400px; color: var(--color-text-primary);">${JSON.stringify(m, null, 2)}</pre>
          </div>
        </div>

      </div>
    `);

    this.container.innerHTML = '';
    this.container.appendChild(page);

    // Attach Raw JSON Toggle Listener
    const toggleBtn = page.querySelector('#toggle-raw-json-btn');
    const jsonCanvas = page.querySelector('#raw-json-canvas');
    if (toggleBtn && jsonCanvas) {
      toggleBtn.addEventListener('click', () => {
        this.showRawJson = !this.showRawJson;
        if (this.showRawJson) {
          jsonCanvas.classList.remove('hidden');
          toggleBtn.textContent = 'Hide JSON';
        } else {
          jsonCanvas.classList.add('hidden');
          toggleBtn.textContent = 'Inspect Raw JSON';
        }
      });
    }

    // 8. Mount StatCards
    const kpi1 = page.querySelector('#meth-kpi-1');
    const kpi2 = page.querySelector('#meth-kpi-2');
    const kpi3 = page.querySelector('#meth-kpi-3');
    const kpi4 = page.querySelector('#meth-kpi-4');

    if (kpi1) {
      kpi1.appendChild(
        StatCard.render({
          label: 'TOTAL INPUT ROWS',
          value: fmt.integer(cleaning.rows_in),
          hint: 'Raw collected quotes processed',
          status: 'neutral'
        })
      );
    }

    if (kpi2) {
      kpi2.appendChild(
        StatCard.render({
          label: 'RETENTION RATE',
          value: `${cleaning.retention_pct != null ? cleaning.retention_pct : '—'}%`,
          hint: `${fmt.integer(cleaning.rows_index_eligible)} eligible rows`,
          status: (cleaning.retention_pct || 0) >= 80 ? 'success' : 'warning'
        })
      );
    }

    if (kpi3) {
      kpi3.appendChild(
        StatCard.render({
          label: 'DAY-OF-WEEK AMPLITUDE',
          value: `${diag.dow_amplitude_pct != null ? diag.dow_amplitude_pct.toFixed(2) : '—'}%`,
          hint: 'Within-week fare variation cycle',
          status: 'neutral'
        })
      );
    }

    if (kpi4) {
      kpi4.appendChild(
        StatCard.render({
          label: 'COMPOSITION BIAS SPREAD',
          value: `${diag.composition_bias_pct != null ? diag.composition_bias_pct.toFixed(2) : '—'}%`,
          hint: 'Expenditure vs passenger weighting gap',
          status: 'neutral'
        })
      );
    }

    // 9. Mount Quarantine Breakdown Table
    const quaranMount = page.querySelector<HTMLElement>('#quarantine-table-mount-point');
    if (quaranMount) {
      const qCols: TableColumn<QuarantineRow>[] = [
        {
          key: 'reason',
          label: 'Validation Quarantine Reason Code',
          width: '320px',
          render: (row) => `<span class="code-badge" style="font-weight: 600;">${row.reason}</span>`
        },
        {
          key: 'count',
          label: 'Rejected Rows',
          align: 'right',
          width: '180px',
          render: (row) => `<span class="metric-tabular">${fmt.integer(row.count)} rows</span>`
        },
        {
          key: 'share_pct',
          label: 'Share of Quarantined',
          align: 'right',
          width: '180px',
          render: (row) => `<span class="metric-tabular" style="font-weight: 600;">${row.share_pct}</span>`
        }
      ];

      this.quarantineTable.render(quaranMount, {
        columns: qCols,
        data: quarantineRows,
        keyField: 'reason',
        emptyMessage: 'No rows quarantined (100% clean sample).'
      });
    }

    // 10. Mount Weight Vector Master Table
    const weightMount = page.querySelector<HTMLElement>('#weights-table-mount-point');
    if (weightMount) {
      const wCols: TableColumn<WeightRow>[] = [
        {
          key: 'route_code',
          label: 'Route Sector Code',
          width: '160px',
          render: (row) => `<span class="code-badge" style="font-weight: 600;">${row.route_code}</span>`
        },
        {
          key: 'weight',
          label: 'Expenditure Share (w_r)',
          align: 'right',
          width: '220px',
          render: (row) => `<span class="metric-tabular" style="font-family: var(--font-family-mono); font-weight: 600;">${row.weight.toFixed(6)}</span>`
        },
        {
          key: 'weight_pct',
          label: 'Share % (Visualized)',
          align: 'right',
          width: '240px',
          render: (row) => `
            <div style="display: flex; align-items: center; justify-content: flex-end; gap: 10px;">
              <div style="width: 80px; height: 6px; background-color: var(--color-bg-surface-subtle); border-radius: 3px; overflow: hidden;">
                <div style="width: ${Math.min(100, row.weight * 350)}%; height: 100%; background-color: var(--color-brand-primary);"></div>
              </div>
              <span class="metric-tabular" style="font-weight: 600;">${row.weight_pct}</span>
            </div>
          `
        }
      ];

      this.weightsTable.render(weightMount, {
        columns: wCols,
        data: weightRows,
        keyField: 'route_code',
        emptyMessage: 'No weight vector data available.'
      });
    }
  }
}
