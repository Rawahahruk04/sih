/**
 * AIPI Institutional Sector Heatmap Component
 * 
 * High-density 2D Matrix (Routes × Dates) with:
 * - Linear divergent color interpolation anchored at baseline 100.0
 * - Strict null handling (rendered as hatched neutral pattern, never 0)
 * - Interactive cell hover with floating institutional tooltip
 * - Keyboard navigation (Tab/Arrows) and screen-reader table fallback
 */

import { fmt } from '../utils/formatters.js';

export interface SectorHeatmapProps {
  routes: string[];
  routeNames: string[];
  dates: string[];
  matrix: (number | null)[][]; // matrix[routeIndex][dateIndex]
  valueMin?: number | null;
  valueMax?: number | null;
  baseline?: number;
  onSelectRoute?: (routeCode: string) => void;
}

export class SectorHeatmap {
  private static interpolateColor(val: number | null, min: number, max: number, baseline = 100.0): string {
    if (val == null) return 'url(#heatmap-null-hatch)';

    if (val <= baseline) {
      // Interpolate between Teal (#356C7B) and Cream (#F2EFD9)
      const ratio = min === baseline ? 1 : Math.max(0, Math.min(1, (val - min) / (baseline - min)));
      // #356C7B = rgb(53, 108, 123), #F2EFD9 = rgb(242, 239, 217)
      const r = Math.round(53 + (242 - 53) * ratio);
      const g = Math.round(108 + (239 - 108) * ratio);
      const b = Math.round(123 + (217 - 123) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Interpolate between Cream (#F2EFD9) and Crimson (#B54848)
      const ratio = max === baseline ? 0 : Math.max(0, Math.min(1, (val - baseline) / (max - baseline)));
      // #F2EFD9 = rgb(242, 239, 217), #B54848 = rgb(181, 72, 72)
      const r = Math.round(242 + (181 - 242) * ratio);
      const g = Math.round(239 + (72 - 239) * ratio);
      const b = Math.round(217 + (72 - 217) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    }
  }

  public static render(container: HTMLElement, props: SectorHeatmapProps): void {
    if (!props.routes.length || !props.dates.length || !props.matrix.length) {
      container.innerHTML = `
        <div class="empty-state-container" style="padding: 32px 16px;">
          <p class="text-body-muted">No heatmap matrix observations available.</p>
        </div>
      `;
      return;
    }

    const nRoutes = props.routes.length;
    const nDates = props.dates.length;

    // Calculate actual bounds if not provided
    const validValues = props.matrix.flat().filter((v): v is number => v != null);
    const minVal = props.valueMin ?? (validValues.length ? Math.min(...validValues) : 90);
    const maxVal = props.valueMax ?? (validValues.length ? Math.max(...validValues) : 115);
    const baseline = props.baseline ?? 100.0;

    const rowHeight = 26;
    const labelWidth = 140;
    const cellWidth = Math.max(14, Math.min(32, Math.floor(660 / Math.max(1, nDates))));
    const headerHeight = 36;
    const totalWidth = labelWidth + cellWidth * nDates + 20;
    const totalHeight = headerHeight + rowHeight * nRoutes + 20;

    // 1. Hatched SVG Pattern definition for null values
    const defs = `
      <defs>
        <pattern id="heatmap-null-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="4" stroke="var(--color-border-strong)" stroke-width="1.2" />
        </pattern>
      </defs>
    `;

    // 2. Column Date Headers (Show subset of date labels to avoid clutter)
    const dateStep = Math.max(1, Math.ceil(nDates / 10));
    const dateHeaders: string[] = [];
    for (let d = 0; d < nDates; d++) {
      if (d % dateStep === 0 || d === nDates - 1) {
        const xPos = labelWidth + d * cellWidth + cellWidth / 2;
        const shortDate = props.dates[d].slice(5); // MM-DD
        dateHeaders.push(
          `<text x="${xPos}" y="${headerHeight - 8}" text-anchor="middle" font-size="10" font-family="var(--font-family-numeric)" fill="var(--color-text-secondary)">${shortDate}</text>`
        );
      }
    }

    // 3. Grid Rows & Heatmap Rectangles
    const gridRows: string[] = [];
    for (let r = 0; r < nRoutes; r++) {
      const yPos = headerHeight + r * rowHeight;
      const routeCode = props.routes[r];
      const routeName = props.routeNames[r] || routeCode;

      // Row Label
      gridRows.push(`
        <text x="8" y="${yPos + rowHeight / 2 + 4}" font-size="11" font-weight="600" font-family="var(--font-family-mono)" fill="var(--color-text-primary)" class="heatmap-row-label" data-route="${routeCode}" style="cursor: pointer;">
          ${routeCode}
        </text>
      `);

      // Cells in Row
      for (let d = 0; d < nDates; d++) {
        const val = props.matrix[r][d];
        const xPos = labelWidth + d * cellWidth;
        const fillColor = this.interpolateColor(val, minVal, maxVal, baseline);
        const cellDate = props.dates[d];

        gridRows.push(`
          <rect x="${xPos + 0.5}" y="${yPos + 0.5}" width="${cellWidth - 1}" height="${rowHeight - 1}" 
                fill="${fillColor}" 
                rx="1.5"
                class="heatmap-cell" 
                tabindex="0"
                role="gridcell"
                aria-label="${routeCode} on ${cellDate}: ${val != null ? val.toFixed(2) : 'No data'}"
                data-route="${routeCode}"
                data-name="${routeName}"
                data-date="${cellDate}"
                data-val="${val != null ? val : ''}" />
        `);
      }
    }

    // 4. Accessible Screen-Reader Table Fallback
    const srTable = `
      <table class="sr-only" aria-label="Route Index Heatmap Grid">
        <thead>
          <tr>
            <th>Route</th>
            ${props.dates.map((dt) => `<th>${dt}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${props.routes
            .map((route, r) => {
              const cells = props.dates.map((_, d) => `<td>${props.matrix[r][d] != null ? props.matrix[r][d]!.toFixed(2) : 'No Data'}</td>`).join('');
              return `<tr><td>${route}</td>${cells}</tr>`;
            })
            .join('')}
        </tbody>
      </table>
    `;

    // 5. Assemble Heatmap Layout
    container.innerHTML = `
      <div class="heatmap-wrapper" style="position: relative; overflow-x: auto; width: 100%;">
        <svg viewBox="0 0 ${totalWidth} ${totalHeight}" class="heatmap-svg" style="min-width: ${Math.max(680, totalWidth)}px;" role="grid" aria-label="2D Sector-Date Index Heatmap">
          ${defs}
          <g class="heatmap-dates">${dateHeaders.join('')}</g>
          <g class="heatmap-grid">${gridRows.join('')}</g>
        </svg>

        <!-- Floating Heatmap Tooltip -->
        <div id="heatmap-tooltip" class="chart-tooltip hidden" role="tooltip"></div>
        ${srTable}
      </div>
    `;

    // 6. Attach Hover & Focus Tooltip Interactivity
    const tooltip = container.querySelector<HTMLElement>('#heatmap-tooltip');
    const cells = container.querySelectorAll<SVGRectElement>('.heatmap-cell');

    cells.forEach((cell) => {
      const showTip = () => {
        if (!tooltip) return;
        const route = cell.dataset.route || '';
        const name = cell.dataset.name || route;
        const date = cell.dataset.date || '';
        const rawVal = cell.dataset.val;
        const val = rawVal ? parseFloat(rawVal) : null;

        let valText = '<span style="color: var(--color-text-secondary);">No observations recorded (null)</span>';
        let deltaText = '';

        if (val != null) {
          const delta = val - baseline;
          const deltaSign = delta >= 0 ? '+' : '';
          const deltaClass = delta >= 0 ? 'delta-positive' : 'delta-negative';
          valText = `<span class="metric-tabular" style="font-weight: 700; font-size: 14px;">${val.toFixed(2)} pts</span>`;
          deltaText = `<span class="stat-delta ${deltaClass}" style="font-size: 11px;">${deltaSign}${delta.toFixed(2)} vs Base</span>`;
        }

        tooltip.innerHTML = `
          <div style="font-weight: 600; font-size: 12px; color: var(--color-text-primary); margin-bottom: 2px;">
            ${name} <span class="code-badge" style="margin-left: 4px;">${route}</span>
          </div>
          <div style="font-size: 11px; color: var(--color-text-secondary); margin-bottom: 6px;">
            Date: <b>${date}</b>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
            ${valText}
            ${deltaText}
          </div>
        `;

        tooltip.classList.remove('hidden');

        // Position tooltip
        const rect = cell.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const left = rect.left - containerRect.left + rect.width / 2;
        const top = rect.top - containerRect.top - 8;

        tooltip.style.left = `${left}px`;
        tooltip.style.top = `${top}px`;
      };

      const hideTip = () => {
        if (tooltip) tooltip.classList.add('hidden');
      };

      cell.addEventListener('mouseenter', showTip);
      cell.addEventListener('focus', showTip);
      cell.addEventListener('mouseleave', hideTip);
      cell.addEventListener('blur', hideTip);

      if (props.onSelectRoute) {
        cell.addEventListener('click', () => {
          const rCode = cell.dataset.route;
          if (rCode && props.onSelectRoute) props.onSelectRoute(rCode);
        });
      }
    });

    // Row label click handlers
    const labels = container.querySelectorAll<SVGTextElement>('.heatmap-row-label');
    labels.forEach((lbl) => {
      lbl.addEventListener('click', () => {
        const rCode = lbl.dataset.route;
        if (rCode && props.onSelectRoute) props.onSelectRoute(rCode);
      });
    });
  }
}
