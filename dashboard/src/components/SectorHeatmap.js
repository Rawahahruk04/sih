/**
 * AIPI Institutional Sector Heatmap Component (ES Module)
 */

import { fmt } from '../utils/formatters.js';

export class SectorHeatmap {
  static interpolateColor(val, min, max, baseline = 100.0) {
    if (val == null) return 'url(#heatmap-null-hatch)';

    if (val <= baseline) {
      // Below or at Baseline: Interpolate from Deep Forest (#286F63) to Warm Ivory (#F3EFEA)
      const ratio = min === baseline ? 1 : Math.max(0, Math.min(1, (val - min) / (baseline - min)));
      const r = Math.round(40 + (243 - 40) * ratio);
      const g = Math.round(111 + (239 - 111) * ratio);
      const b = Math.round(99 + (234 - 99) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // Above Baseline: Interpolate from Warm Ivory (#F3EFEA) to Deep Crimson (#B83232)
      const ratio = max === baseline ? 0 : Math.max(0, Math.min(1, (val - baseline) / (max - baseline)));
      const r = Math.round(243 + (184 - 243) * ratio);
      const g = Math.round(239 + (50 - 239) * ratio);
      const b = Math.round(234 + (50 - 234) * ratio);
      return `rgb(${r}, ${g}, ${b})`;
    }
  }

  static render(container, props) {
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

    const validValues = props.matrix.flat().filter((v) => v != null);
    const minVal = props.valueMin ?? (validValues.length ? Math.min(...validValues) : 90);
    const maxVal = props.valueMax ?? (validValues.length ? Math.max(...validValues) : 115);
    const baseline = props.baseline ?? 100.0;

    const rowHeight = 20;
    const labelWidth = 110;
    const cellWidth = Math.max(16, Math.min(28, Math.floor(700 / Math.max(1, nDates))));
    const headerHeight = 26;
    const totalWidth = labelWidth + cellWidth * nDates + 12;
    const totalHeight = headerHeight + rowHeight * nRoutes + 8;

    // 1. Hatched SVG Pattern definition for null values
    const defs = `
      <defs>
        <pattern id="heatmap-null-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-border-strong)" stroke-width="1.5" />
        </pattern>
      </defs>
    `;

    // 2. Column Date Headers — Prevent label collisions with clean minimum step
    const minLabelDistPx = 48;
    const dateStep = Math.max(1, Math.ceil(minLabelDistPx / cellWidth));
    const dateIndices = [];
    for (let d = 0; d < nDates; d += dateStep) {
      dateIndices.push(d);
    }
    if (nDates - 1 - dateIndices[dateIndices.length - 1] >= Math.floor(dateStep * 0.6)) {
      dateIndices.push(nDates - 1);
    } else if (dateIndices.length > 1) {
      dateIndices[dateIndices.length - 1] = nDates - 1;
    }

    const dateHeaders = dateIndices.map((d) => {
      const xPos = labelWidth + d * cellWidth + cellWidth / 2;
      const shortDate = props.dates[d].slice(5);
      return `
        <line x1="${xPos}" y1="${headerHeight - 4}" x2="${xPos}" y2="${headerHeight - 1}" stroke="var(--color-border-strong)" stroke-width="1" />
        <text x="${xPos}" y="${headerHeight - 7}" text-anchor="middle" font-size="9" font-weight="500" font-family="var(--font-family-numeric)" fill="var(--color-text-secondary)">${shortDate}</text>
      `;
    });

    // 3. Grid Rows & Heatmap Rectangles
    const gridRows = [];
    for (let r = 0; r < nRoutes; r++) {
      const yPos = headerHeight + r * rowHeight;
      const routeCode = props.routes[r];
      const routeName = props.routeNames[r] || routeCode;

      gridRows.push(`
        <g class="heatmap-row-group" data-route="${routeCode}" style="cursor: pointer;">
          <text x="6" y="${yPos + rowHeight / 2}" dominant-baseline="central" font-size="11" font-weight="700" font-family="var(--font-family-mono)" fill="var(--color-text-primary)" class="heatmap-row-label">
            ${routeCode}
          </text>
        </g>
      `);

      for (let d = 0; d < nDates; d++) {
        const val = props.matrix[r][d];
        const xPos = labelWidth + d * cellWidth;
        const fillColor = this.interpolateColor(val, minVal, maxVal, baseline);
        const cellDate = props.dates[d];

        gridRows.push(`
          <rect x="${xPos + 0.5}" y="${yPos + 0.5}" width="${cellWidth - 1}" height="${rowHeight - 1}" 
                fill="${fillColor}" 
                rx="2"
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
              const cells = props.dates.map((_, d) => `<td>${props.matrix[r][d] != null ? props.matrix[r][d].toFixed(2) : 'No Data'}</td>`).join('');
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
          <line x1="${labelWidth}" y1="${headerHeight - 2}" x2="${totalWidth}" y2="${headerHeight - 2}" stroke="var(--color-border-subtle)" stroke-width="1" />
          <g class="heatmap-dates">${dateHeaders.join('')}</g>
          <g class="heatmap-grid">${gridRows.join('')}</g>
        </svg>

        <!-- Floating Heatmap Tooltip -->
        <div id="heatmap-tooltip" class="chart-tooltip hidden" role="tooltip"></div>
        ${srTable}
      </div>
    `;

    // 6. Attach Hover & Focus Tooltip Interactivity
    const tooltip = container.querySelector('#heatmap-tooltip');
    const cells = container.querySelectorAll('.heatmap-cell');

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

        const rect = cell.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        const left = Math.max(100, Math.min(containerRect.width - 100, rect.left - containerRect.left + rect.width / 2));
        const top = Math.max(20, rect.top - containerRect.top - 8);

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

    const labels = container.querySelectorAll('.heatmap-row-group');
    labels.forEach((lbl) => {
      lbl.addEventListener('click', () => {
        const rCode = lbl.dataset.route;
        if (rCode && props.onSelectRoute) props.onSelectRoute(rCode);
      });
    });
  }
}
