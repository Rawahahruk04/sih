/**
 * AIPI Institutional LeadtimeCurveChart Component
 * 
 * SVG Curve displaying Relative Fare Level vs Advance Purchase Days (T+1 .. T+45)
 * Anchored to the backend's reference window (14 days = 100.0).
 */

import { fmt } from '../utils/formatters.js';

export interface CurvePoint {
  advance_days: number;
  relative_level: number;
}

export interface LeadtimeCurveChartProps {
  curve: CurvePoint[];
  referenceWindow?: number | null;
  asOf?: string | null;
}

export class LeadtimeCurveChart {
  private static readonly W = 820;
  private static readonly H = 300;
  private static readonly M = { t: 20, r: 32, b: 40, l: 56 };

  public static render(container: HTMLElement, props: LeadtimeCurveChartProps): void {
    if (!props.curve || props.curve.length === 0) {
      container.innerHTML = `
        <div class="empty-state-container" style="padding: 32px 16px;">
          <p class="text-body-muted">No lead-time price curve data available.</p>
        </div>
      `;
      return;
    }

    const sortedCurve = [...props.curve].sort((a, b) => a.advance_days - b.advance_days);
    const n = sortedCurve.length;
    const refWindow = props.referenceWindow ?? 14;

    const ys = sortedCurve.map((p) => p.relative_level);
    ys.push(100.0); // Ensure reference baseline is in domain

    let ymin = Math.min(...ys);
    let ymax = Math.max(...ys);
    if (ymin === ymax) {
      ymin -= 10;
      ymax += 10;
    }
    const pad = (ymax - ymin) * 0.12;
    ymin = Math.max(0, ymin - pad);
    ymax = ymax + pad;

    const px = (idx: number) =>
      this.M.l + (n <= 1 ? (this.W - this.M.l - this.M.r) / 2 : (idx / (n - 1)) * (this.W - this.M.l - this.M.r));
    const py = (y: number) => this.M.t + (1 - (y - ymin) / (ymax - ymin)) * (this.H - this.M.t - this.M.b);

    // 1. Grid & Y-Axis
    const gridY = 5;
    const gridElements: string[] = [];
    for (let g = 0; g <= gridY; g++) {
      const yVal = ymin + (g / gridY) * (ymax - ymin);
      const yCoord = py(yVal);
      gridElements.push(
        `<line x1="${this.M.l}" y1="${yCoord.toFixed(1)}" x2="${this.W - this.M.r}" y2="${yCoord.toFixed(1)}" stroke="var(--color-chart-grid)" stroke-width="1" />`
      );
      gridElements.push(
        `<text x="${this.M.l - 10}" y="${(yCoord + 4).toFixed(1)}" text-anchor="end" fill="var(--color-text-secondary)" font-family="var(--font-family-numeric)" font-size="11" font-variant-numeric="tabular-nums">${yVal.toFixed(0)}</text>`
      );
    }

    // 2. Reference Line at 100.0 (14-day window)
    const baseY = py(100.0);
    const baselineSvg = `
      <line class="baseline-rule" x1="${this.M.l}" y1="${baseY.toFixed(1)}" x2="${this.W - this.M.r}" y2="${baseY.toFixed(1)}" stroke="var(--color-chart-baseline)" stroke-width="1.5" stroke-dasharray="4,4" />
      <text x="${this.W - this.M.r}" y="${(baseY - 6).toFixed(1)}" text-anchor="end" fill="var(--color-text-secondary)" font-size="10" font-family="var(--font-family-body)">T+${refWindow} Ref = 100.0</text>
    `;

    // 3. X-Axis Labels (T+1, T+2, T+3, T+7, T+14, T+21, T+30, T+45)
    const xLabels: string[] = sortedCurve.map((p, i) => {
      const isRef = p.advance_days === refWindow;
      const labelText = `T+${p.advance_days}`;
      return `<text x="${px(i).toFixed(1)}" y="${this.H - 14}" text-anchor="middle" fill="${isRef ? 'var(--color-brand-primary)' : 'var(--color-text-secondary)'}" font-weight="${isRef ? '600' : '400'}" font-family="var(--font-family-numeric)" font-size="11">${labelText}</text>`;
    });

    // 4. Smooth Curve Line and Nodes
    const d = sortedCurve
      .map((p, i) => `${i ? 'L' : 'M'}${px(i).toFixed(1)},${py(p.relative_level).toFixed(1)}`)
      .join(' ');

    const nodes = sortedCurve
      .map((p, i) => {
        const cx = px(i).toFixed(1);
        const cy = py(p.relative_level).toFixed(1);
        const isRef = p.advance_days === refWindow;
        return `
          <circle cx="${cx}" cy="${cy}" r="${isRef ? 5.5 : 4}" 
                  fill="${isRef ? 'var(--color-brand-primary)' : 'var(--color-brand-secondary)'}" 
                  stroke="var(--color-bg-surface)" 
                  stroke-width="2" 
                  class="curve-node" 
                  tabindex="0"
                  role="button"
                  aria-label="Advance Purchase T+${p.advance_days} days: Relative Level ${p.relative_level.toFixed(2)}"
                  data-days="${p.advance_days}"
                  data-val="${p.relative_level.toFixed(2)}" />
        `;
      })
      .join('');

    // 5. Accessible Screen-Reader Table Fallback
    const srTable = `
      <table class="sr-only" aria-label="Lead-time Price Curve Data">
        <thead>
          <tr>
            <th>Advance Purchase Horizon</th>
            <th>Relative Fare Level (T+14 = 100.0)</th>
            <th>Walk-up Premium / Early Discount</th>
          </tr>
        </thead>
        <tbody>
          ${sortedCurve
            .map((p) => {
              const diff = p.relative_level - 100.0;
              const sign = diff >= 0 ? '+' : '';
              return `
              <tr>
                <td>T+${p.advance_days} days</td>
                <td>${p.relative_level.toFixed(2)}</td>
                <td>${sign}${diff.toFixed(2)}%</td>
              </tr>
            `;
            })
            .join('')}
        </tbody>
      </table>
    `;

    // 6. Assemble Chart
    container.innerHTML = `
      <div class="leadtime-chart-wrapper" style="position: relative; width: 100%;">
        <svg viewBox="0 0 ${this.W} ${this.H}" class="leadtime-svg" role="img" aria-label="Advance Purchase Price Elasticity Curve">
          <g class="grid-layer">${gridElements.join('')}</g>
          ${baselineSvg}
          <g class="axis-layer">${xLabels.join('')}</g>
          <path d="${d}" fill="none" stroke="var(--color-brand-secondary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          <g class="nodes-layer">${nodes}</g>
          <line id="curve-crosshair" x1="0" y1="${this.M.t}" x2="0" y2="${this.H - this.M.b}" stroke="var(--color-brand-primary)" stroke-width="1.5" stroke-dasharray="3,3" opacity="0" />
        </svg>

        <!-- Floating Tooltip -->
        <div id="curve-tooltip" class="chart-tooltip hidden" role="tooltip"></div>
        ${srTable}
      </div>
    `;

    // Attach Interactivity
    const svgEl = container.querySelector<SVGElement>('.leadtime-svg');
    const crosshair = container.querySelector<SVGLineElement>('#curve-crosshair');
    const tooltip = container.querySelector<HTMLElement>('#curve-tooltip');

    if (svgEl && crosshair && tooltip) {
      svgEl.addEventListener('mousemove', (evt) => {
        const rect = svgEl.getBoundingClientRect();
        const mouseX = ((evt.clientX - rect.left) / rect.width) * this.W;

        if (mouseX < this.M.l || mouseX > this.W - this.M.r) {
          crosshair.setAttribute('opacity', '0');
          tooltip.classList.add('hidden');
          return;
        }

        const idx = Math.min(
          n - 1,
          Math.max(0, Math.round(((mouseX - this.M.l) / (this.W - this.M.l - this.M.r)) * (n - 1)))
        );

        const pt = sortedCurve[idx];
        const snappedX = px(idx);
        crosshair.setAttribute('x1', snappedX.toFixed(1));
        crosshair.setAttribute('x2', snappedX.toFixed(1));
        crosshair.setAttribute('opacity', '1');

        const delta = pt.relative_level - 100.0;
        const deltaSign = delta >= 0 ? '+' : '';
        const deltaClass = delta >= 0 ? 'delta-positive' : 'delta-negative';

        tooltip.innerHTML = `
          <div style="font-weight: 600; font-size: 12px; color: var(--color-text-primary); margin-bottom: 4px;">
            Booking Horizon: T+${pt.advance_days} Days
          </div>
          <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 12px;">
            <span style="font-size: 11px; color: var(--color-text-secondary);">Relative Level:</span>
            <span class="metric-tabular" style="font-weight: 700; font-size: 13px;">${pt.relative_level.toFixed(2)} pts</span>
          </div>
          <div style="margin-top: 4px;">
            <span class="stat-delta ${deltaClass}" style="font-size: 11px;">
              ${deltaSign}${delta.toFixed(2)}% vs T+${refWindow} Ref
            </span>
          </div>
        `;

        tooltip.classList.remove('hidden');
        const leftPercent = (snappedX / this.W) * 100;
        tooltip.style.left = `${leftPercent}%`;
        tooltip.style.top = '16px';
      });

      svgEl.addEventListener('mouseleave', () => {
        crosshair.setAttribute('opacity', '0');
        tooltip.classList.add('hidden');
      });
    }
  }
}
