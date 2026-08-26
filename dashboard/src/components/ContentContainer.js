/**
 * AIPI Reusable Page Content Container Component (ES Module)
 */

import { escapeHtml, htmlToElement } from '../utils/dom.js';

export class ContentContainer {
  constructor() {
    this.element = null;
  }

  render(headerConfig) {
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

  setBodyContent(content) {
    const slot = this.element?.querySelector('#page-body-slot');
    if (!slot) return;

    if (typeof content === 'string') {
      slot.innerHTML = content;
    } else {
      slot.innerHTML = '';
      slot.appendChild(content);
    }
  }

  setActions(actionsHtml) {
    const slot = this.element?.querySelector('#page-actions-slot');
    if (slot) {
      slot.innerHTML = actionsHtml;
    }
  }

  /** Updates the header badge text in place once a live backend value is known. */
  setBadge(label) {
    const badge = this.element?.querySelector('.title-with-badge .badge');
    if (badge) badge.textContent = label;
  }
}
