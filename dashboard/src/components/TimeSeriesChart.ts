/**
 * AIPI Institutional TimeSeriesChart Component
 * 
 * High-performance SVG Time-Series Chart with baseline 100 indicator,
 * dual-line comparisons, incomplete period dashed strokes, interactive crosshair,
 * and accessible screen reader tabular fallback.
 */

import { fmt } from '../utils/formatters.js';

export interface ChartPoint {
  x: string; // ISO date string or period label
  y: number; // Index value
  nObs?: number;
  coveragePct?: number;
  isComplete?: boolean | null;
}

export interface ChartSeries {
  id: string;
  name: string;
  color: string;
  points: ChartPoint[];
  dashed?: boolean;
}

export interface TimeSeriesChartProps {
  series: ChartSeries[];
  baseline?: number | null;
  yFormat?: (val: number) => string;
  dateAxis?: boolean;
  onHover?: (point: ChartPoint | null, seriesName: string | null) => void;
}

export class TimeSeriesChart {
  private static readonly W = 820;
  private static readonly H = 300;
  private static readonly M = { t: 16, r: 24, b: 36, l: 52 };

  public static render(container: HTMLElement, props: TimeSeriesChartProps): void {
    if (!props.series.length || !props.series.some((s) => s.points.length > 0)) {
      container.innerHTML = `
        <div class="empty-state-container" style="padding: 32px 16px;">
          <p class="text-body-muted">No time-series data available for the selected range.</p>
        </div>
      `;
      return;
    }

    const allX = [...new Set(props.series.flatMap((s) => s.points.map((p) => p.x)))].sort();
    const xi = new Map(allX.map((x, i) => [x, i]));
    const ys = props.series.flatMap((s) => s.points.map((p) => p.y));
    if (props.baseline != null) ys.push(props.baseline);

    let ymin = Math.min(...ys);
    let ymax = Math.max(...ys);
    if (ymin === ymax) {
      ymin -= 1;
      ymax += 1;
    }
    const pad = (ymax - ymin) * 0.1;
    ymin = ymin - pad;
    ymax = ymax + pad;

    const n = allX.length;
    const px = (i: number) =>
      this.M.l + (n <= 1 ? (this.W - this.M.l - this.M.r) / 2 : (i / (n - 1)) * (this.W - this.M.l - this.M.r));
    const py = (y: number) => this.M.t + (1 - (y - ymin) / (ymax - ymin)) * (this.H - this.M.t - this.M.b);

    const yfmt = props.yFormat || ((v: number) => fmt.index(v, 1));

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
        `<text x="${this.M.l - 10}" y="${(yCoord + 4).toFixed(1)}" text-anchor="end" fill="var(--color-text-secondary)" font-family="var(--font-family-numeric)" font-size="11" font-variant-numeric="tabular-nums">${yfmt(yVal)}</text>`
      );
    }

    // 2. Baseline Reference (100.0)
    let baselineSvg = '';
    if (props.baseline != null) {
      const baseY = py(props.baseline);
      baselineSvg = `
        <line class="baseline-rule" x1="${this.M.l}" y1="${baseY.toFixed(1)}" x2="${this.W - this.M.r}" y2="${baseY.toFixed(1)}" stroke="var(--color-chart-baseline)" stroke-width="1.5" stroke-dasharray="4,4" />
        <text x="${this.W - this.M.r}" y="${(baseY - 6).toFixed(1)}" text-anchor="end" fill="var(--color-text-secondary)" font-size="10" font-family="var(--font-family-body)">Base = 100.0</text>
      `;
    }

    // 3. X-Axis Labels
    const nLabels = Math.min(7, n);
    const xLabels: string[] = [];
    for (let k = 0; k < nLabels; k++) {
      const i = Math.round((k / Math.max(1, nLabels - 1)) * (n - 1));
      const raw = allX[i];
      const label = props.dateAxis !== false && raw.length >= 10 ? raw.slice(5) : raw;
      xLabels.push(
        `<text x="${px(i).toFixed(1)}" y="${this.H - 12}" text-anchor="middle" fill="var(--color-text-secondary)" font-family="var(--font-family-numeric)" font-size="11">${label}</text>`
      );
    }

    // 4. Series Paths
    const linesSvg = props.series
      .map((s) => {
        const sortedPoints = s.points.filter((p) => xi.has(p.x)).sort((a, b) => xi.get(a.x)! - xi.get(b.x)!);
        if (sortedPoints.length === 0) return '';

        const d = sortedPoints
          .map((p, j) => `${j ? 'L' : 'M'}${px(xi.get(p.x)!).toFixed(1)},${py(p.y).toFixed(1)}`)
          .join(' ');

        const isDashed = s.dashed === true;
        const dashAttr = isDashed ? 'stroke-dasharray="5,4"' : '';

        // Check if any point has isComplete === false
        const pointCircles = sortedPoints
          .map((p) => {
            const cx = px(xi.get(p.x)!).toFixed(1);
            const cy = py(p.y).toFixed(1);
            const isIncomplete = p.isComplete === false;

            return `<circle cx="${cx}" cy="${cy}" r="${isIncomplete ? 3.5 : 2.5}" fill="${isIncomplete ? 'var(--color-bg-surface)' : s.color}" stroke="${s.color}" stroke-width="${isIncomplete ? 2 : 1}" />`;
          })
          .join('');

        return `
          <g class="series-group" data-series-id="${s.id}">
            <path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" ${dashAttr} />
            ${pointCircles}
          </g>
        `;
      })
      .join('');

    // 5. Accessible Screen-Reader Data Table
    const srTable = `
      <table class="sr-only" aria-label="Headline Index Time Series Data Table">
        <thead>
          <tr>
            <th>Date</th>
            ${props.series.map((s) => `<th>${s.name}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${allX
            .map((x) => {
              const rowCols = props.series
                .map((s) => {
                  const pt = s.points.find((p) => p.x === x);
                  return `<td>${pt ? pt.y.toFixed(2) : 'N/A'}</td>`;
                })
                .join('');
              return `<tr><td>${x}</td>${rowCols}</tr>`;
            })
            .join('')}
        </tbody>
      </table>
    `;

    // 6. Assemble Chart SVG + Interactive Overlay
    container.innerHTML = `
      <div class="time-series-chart-wrapper" style="position: relative; width: 100%;">
        <svg viewBox="0 0 ${this.W} ${this.H}" class="time-series-svg" role="img" aria-label="Interactive Airfare Price Index Time Series Chart">
          <g class="grid-layer">${gridElements.join('')}</g>
          ${baselineSvg}
          <g class="axis-layer">${xLabels.join('')}</g>
          <g class="lines-layer">${linesSvg}</g>
          <line id="chart-crosshair" x1="0" y1="${this.M.t}" x2="0" y2="${this.H - this.M.b}" stroke="var(--color-brand-secondary)" stroke-width="1.5" stroke-dasharray="3,3" opacity="0" />
        </svg>

        <!-- Floating Institutional Tooltip -->
        <div id="chart-tooltip" class="chart-tooltip hidden" role="tooltip"></div>
        ${srTable}
      </div>
    `;

    // Attach Hover Crosshair Interactivity
    const svgEl = container.querySelector<SVGElement>('.time-series-svg');
    const crosshair = container.querySelector<SVGLineElement>('#chart-crosshair');
    const tooltip = container.querySelector<HTMLElement>('#chart-tooltip');

    if (svgEl && crosshair && tooltip) {
      svgEl.addEventListener('mousemove', (evt) => {
        const rect = svgEl.getBoundingClientRect();
        const mouseX = ((evt.clientX - rect.left) / rect.width) * this.W;

        if (mouseX < this.M.l || mouseX > this.W - this.M.r) {
          crosshair.setAttribute('opacity', '0');
          tooltip.classList.add('hidden');
          return;
        }

        // Find nearest index
        const idx = Math.min(
          n - 1,
          Math.max(0, Math.round(((mouseX - this.M.l) / (this.W - this.M.l - this.M.r)) * (n - 1)))
        );

        const currentX = allX[idx];
        const snappedX = px(idx);
        crosshair.setAttribute('x1', snappedX.toFixed(1));
        crosshair.setAttribute('x2', snappedX.toFixed(1));
        crosshair.setAttribute('opacity', '1');

        // Tooltip Content
        let tooltipLines = `
          <div class="tooltip-header text-small" style="font-weight: 600; color: var(--color-text-primary); margin-bottom: 4px;">
            ${currentX}
          </div>
        `;

        props.series.forEach((s) => {
          const pt = s.points.find((p) => p.x === currentX);
          if (pt) {
            const incompleteBadge = pt.isComplete === false ? '<span style="color: var(--color-status-warning); font-size: 10px;"> (Partial)</span>' : '';
            tooltipLines += `
              <div class="tooltip-row" style="display: flex; justify-content: space-between; gap: 12px; font-size: 12px; margin-top: 2px;">
                <span style="color: ${s.color};">${s.name}:</span>
                <span class="metric-tabular" style="font-weight: 600;">${pt.y.toFixed(2)}${incompleteBadge}</span>
              </div>
            `;
            if (pt.coveragePct != null) {
              tooltipLines += `
                <div style="font-size: 10px; color: var(--color-text-secondary); margin-top: 1px;">
                  Coverage: ${pt.coveragePct.toFixed(1)}% · ${pt.nObs || 0} obs
                </div>
              `;
            }
          }
        });

        tooltip.innerHTML = tooltipLines;
        tooltip.classList.remove('hidden');

        // Position tooltip relative to container
        const leftPercent = ((snappedX) / this.W) * 100;
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
