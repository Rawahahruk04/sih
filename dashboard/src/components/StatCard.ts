/**
 * AIPI Institutional StatCard Component
 * 
 * High-density enterprise metric card displaying label, primary tabular figure,
 * delta pill with signed delta, context hint, and status indicators.
 */

import { htmlToElement } from '../utils/dom.js';

export interface StatCardProps {
  id?: string;
  label: string;
  value: string | number;
  unit?: string;
  delta?: {
    value: number;
    isPercent?: boolean;
    label?: string;
  };
  hint?: string;
  status?: 'neutral' | 'success' | 'warning' | 'danger';
  tooltip?: string;
  size?: 'normal' | 'large';
}

export class StatCard {
  public static render(props: StatCardProps): HTMLElement {
    const isLarge = props.size === 'large';
    const status = props.status || 'neutral';

    let deltaHtml = '';
    if (props.delta != null) {
      const isPositive = props.delta.value >= 0;
      const deltaSign = isPositive ? '+' : '';
      const formattedDelta = props.delta.isPercent
        ? `${deltaSign}${props.delta.value.toFixed(2)}%`
        : `${deltaSign}${props.delta.value.toFixed(2)} pts`;

      const deltaClass = isPositive ? 'delta-positive' : 'delta-negative';
      deltaHtml = `
        <span class="stat-delta ${deltaClass}" title="${props.delta.label || 'Change'}">
          ${formattedDelta}
        </span>
      `;
    }

    const card = htmlToElement(`
      <div class="stat-card stat-${status} ${isLarge ? 'stat-large' : ''}" 
           ${props.id ? `id="${props.id}"` : ''} 
           role="region" 
           aria-label="${props.label}">
        <div class="stat-header">
          <span class="stat-label text-label" ${props.tooltip ? `title="${props.tooltip}"` : ''}>
            ${props.label}
          </span>
          ${deltaHtml}
        </div>
        
        <div class="stat-value-group">
          <span class="stat-value ${isLarge ? 'metric-large' : 'metric-medium'}">
            ${props.value}
          </span>
          ${props.unit ? `<span class="stat-unit text-small">${props.unit}</span>` : ''}
        </div>

        ${props.hint ? `<div class="stat-hint text-small">${props.hint}</div>` : ''}
      </div>
    `);

    return card;
  }

  public static renderSkeleton(size: 'normal' | 'large' = 'normal'): HTMLElement {
    return htmlToElement(`
      <div class="stat-card skeleton-shimmer ${size === 'large' ? 'stat-large' : ''}" style="min-height: ${size === 'large' ? '120px' : '96px'};"></div>
    `);
  }
}
