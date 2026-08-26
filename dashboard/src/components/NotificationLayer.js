/**
 * AIPI Global Notification Layer Component (ES Module)
 */

import { Icons } from '../icons/index.js';
import { htmlToElement } from '../utils/dom.js';

export class NotificationLayer {
  constructor() {
    this.container = null;
    this.notifications = new Map();
  }

  mount(root) {
    const layer = htmlToElement(`
      <div class="notification-container" id="global-notification-layer" role="region" aria-label="Notifications" aria-live="polite"></div>
    `);
    root.appendChild(layer);
    this.container = layer;
  }

  show(notification) {
    const id = `notif-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const fullNotification = {
      ...notification,
      id,
      dismissible: notification.dismissible !== false,
      durationMs: notification.durationMs ?? (notification.type === 'error' ? 8000 : 5000)
    };

    this.notifications.set(id, fullNotification);
    this.renderNotification(fullNotification);

    if (fullNotification.durationMs && fullNotification.durationMs > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, fullNotification.durationMs);
    }

    return id;
  }

  dismiss(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('fade-out');
      setTimeout(() => {
        el.remove();
        this.notifications.delete(id);
      }, 150);
    }
  }

  renderNotification(notif) {
    if (!this.container) return;

    let iconSvg = Icons.info();

    if (notif.type === 'success') {
      iconSvg = Icons.success();
    } else if (notif.type === 'warning') {
      iconSvg = Icons.warning();
    } else if (notif.type === 'error') {
      iconSvg = Icons.danger();
    }

    const toast = htmlToElement(`
      <div class="notification-toast notification-${notif.type}" id="${notif.id}" role="status">
        <div class="toast-icon">${iconSvg}</div>
        <div class="toast-content">
          <div class="toast-title text-h3">${notif.title}</div>
          ${notif.message ? `<div class="toast-message text-small">${notif.message}</div>` : ''}
        </div>
        ${
          notif.dismissible
            ? `<button class="toast-close" aria-label="Close notification">${Icons.close()}</button>`
            : ''
        }
      </div>
    `);

    const closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.dismiss(notif.id));
    }

    this.container.appendChild(toast);
  }
}

export const notifications = new NotificationLayer();
