/**
 * AIPI Reusable Empty & Error Layout Component (ES Module)
 */

import { Icons } from '../icons/index.js';
import { escapeHtml, htmlToElement } from '../utils/dom.js';

export class EmptyLayout {
  static render(options) {
    let iconSvg = Icons.inbox();

    if (options.variant === 'offline') {
      iconSvg = Icons.wifiOff();
    } else if (options.variant === 'unauthorized') {
      iconSvg = Icons.lock();
    } else if (options.variant === 'error') {
      iconSvg = Icons.danger();
    } else if (options.variant === 'not_found') {
      iconSvg = Icons.info();
    }

    const container = htmlToElement(`
      <div class="empty-state-container empty-${options.variant || 'no_content'}" role="region">
        <div class="empty-state-icon">${iconSvg}</div>
        <h3 class="text-h2 empty-state-title">${escapeHtml(options.title)}</h3>
        <p class="text-body-muted empty-state-desc">${escapeHtml(options.description)}</p>
        ${
          options.actionButton
            ? `<button class="empty-state-action-btn" id="empty-action-btn">${escapeHtml(options.actionButton.label)}</button>`
            : ''
        }
      </div>
    `);

    if (options.actionButton) {
      const btn = container.querySelector('#empty-action-btn');
      if (btn) {
        btn.addEventListener('click', options.actionButton.onClick);
      }
    }

    return container;
  }
}
