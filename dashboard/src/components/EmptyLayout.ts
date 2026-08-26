/**
 * AIPI Reusable Empty & Error Layout Component
 * 
 * Supports:
 * - 'no_content' (Empty dataset or filtered date range)
 * - 'not_found' (Unknown route / invalid URL)
 * - 'unauthorized' (Access restricted / authenticated token required)
 * - 'error' (500 / 503 backend service error)
 * - 'offline' (Network disconnected)
 */

import { Icons } from '../icons/index.js';
import { htmlToElement } from '../utils/dom.js';

export type EmptyStateVariant = 'no_content' | 'not_found' | 'unauthorized' | 'error' | 'offline';

export interface EmptyLayoutOptions {
  variant?: EmptyStateVariant;
  title: string;
  description: string;
  actionButton?: {
    label: string;
    onClick: () => void;
  };
}

export class EmptyLayout {
  public static render(options: EmptyLayoutOptions): HTMLElement {
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
        <h3 class="text-h2 empty-state-title">${options.title}</h3>
        <p class="text-body-muted empty-state-desc">${options.description}</p>
        ${
          options.actionButton
            ? `<button class="empty-state-action-btn" id="empty-action-btn">${options.actionButton.label}</button>`
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
