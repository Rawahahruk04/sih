/**
 * AIPI Reusable Error State Component
 *
 * Single source of truth for the "failed to load" card every page renders
 * when its fetchData() call rejects.
 */

import { Icons } from '../icons/index.js';
import { escapeHtml } from '../utils/dom.js';

export interface ErrorStateOptions {
  title: string;
  message?: string;
  retryLabel?: string;
  onRetry?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
}

export class ErrorState {
  static render(container: HTMLElement | null, options: ErrorStateOptions): void {
    if (!container) return;

    const message = options.message || 'An unexpected error occurred while communicating with the backend.';
    const retryLabel = options.retryLabel || 'Retry Connection';

    container.innerHTML = `
      <div class="card-container" style="border-left: 4px solid var(--color-status-danger); padding: 32px 24px; text-align: center;" role="alert">
        <div style="color: var(--color-status-danger); margin-bottom: 12px;">${Icons.danger()}</div>
        <h2 class="text-h2" style="margin-bottom: 8px;">${escapeHtml(options.title)}</h2>
        <p class="text-body-muted" style="max-width: 480px; margin: 0 auto 16px;">
          ${escapeHtml(message)}
        </p>
        <div style="display: inline-flex; gap: 10px;">
          ${options.onSecondary ? `<button class="empty-state-action-btn" id="error-state-secondary-btn">${escapeHtml(options.secondaryLabel || 'Back')}</button>` : ''}
          ${options.onRetry ? `<button class="${options.onSecondary ? 'breadcrumb-link' : 'empty-state-action-btn'}" id="error-state-retry-btn" style="${options.onSecondary ? 'font-size: 13px;' : ''}">${escapeHtml(retryLabel)}</button>` : ''}
        </div>
      </div>
    `;

    if (options.onSecondary) {
      const secondaryBtn = container.querySelector('#error-state-secondary-btn');
      if (secondaryBtn) secondaryBtn.addEventListener('click', options.onSecondary);
    }

    if (options.onRetry) {
      const retryBtn = container.querySelector('#error-state-retry-btn');
      if (retryBtn) retryBtn.addEventListener('click', options.onRetry);
    }
  }
}
