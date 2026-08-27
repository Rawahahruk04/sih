/**
 * AIPI Reusable Page Content Container Component
 * 
 * Enforces 1440px bounding box, responsive gutters, vertical rhythm,
 * and standard header/action layout for all feature screens.
 */

import { escapeHtml, htmlToElement } from '../utils/dom.js';

export interface PageHeaderConfig {
  title: string;
  subtitle?: string;
  badge?: { label: string; variant?: 'neutral' | 'success' | 'warning' | 'danger' };
  actionsHtml?: string;
}

export class ContentContainer {
  private element: HTMLElement | null = null;

  public render(headerConfig?: PageHeaderConfig): HTMLElement {
    const container = htmlToElement(`
      <div class="page-container">
        ${
          headerConfig
            ? `
          <div class="page-header-row">
            <div class="page-title-group">
              <div class="title-with-badge">
                <h1 class="text-h1 page-title" tabindex="-1">${escapeHtml(headerConfig.title)}</h1>
                ${
                  headerConfig.badge
                    ? `<span class="badge badge-${headerConfig.badge.variant || 'neutral'}">${escapeHtml(headerConfig.badge.label)}</span>`
                    : ''
                }
              </div>
              ${
                headerConfig.subtitle
                  ? `<p class="text-body-muted page-subtitle">${escapeHtml(headerConfig.subtitle)}</p>`
                  : ''
              }
            </div>
            <div class="page-actions-slot" id="page-actions-slot">
              ${headerConfig.actionsHtml || ''}
            </div>
          </div>
        `
            : ''
        }
        <div class="page-body-slot" id="page-body-slot"></div>
      </div>
    `);

    this.element = container;
    return container;
  }

  public setBodyContent(content: HTMLElement | string): void {
    const slot = this.element?.querySelector('#page-body-slot');
    if (!slot) return;

    if (typeof content === 'string') {
      slot.innerHTML = content;
    } else {
      slot.innerHTML = '';
      slot.appendChild(content);
    }
  }

  public setActions(actionsHtml: string): void {
    const slot = this.element?.querySelector('#page-actions-slot');
    if (slot) {
      slot.innerHTML = actionsHtml;
    }
  }

  /** Updates the header badge text in place once a live backend value is known. */
  public setBadge(label: string): void {
    const badge = this.element?.querySelector('.title-with-badge .badge');
    if (badge) badge.textContent = label;
  }
}
