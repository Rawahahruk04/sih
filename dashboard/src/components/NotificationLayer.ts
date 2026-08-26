/**
 * AIPI Global Notification Layer Component
 * 
 * Manages institutional, non-blocking toast notifications and alerts.
 * Fully WCAG 2.1 AA accessible via aria-live="polite" region.
 */

import { Icons } from '../icons/index.js';
import { Notification, NotificationType } from '../types/notification.js';
import { htmlToElement } from '../utils/dom.js';

export class NotificationLayer {
  private container: HTMLElement | null = null;
  private notifications: Map<string, Notification> = new Map();

  public mount(root: HTMLElement): void {
    const layer = htmlToElement(`
      <div class="notification-container" id="global-notification-layer" role="region" aria-label="Notifications" aria-live="polite"></div>
    `);
    root.appendChild(layer);
    this.container = layer;
  }

  public show(notification: Omit<Notification, 'id'>): string {
    const id = `notif-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const fullNotification: Notification = {
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

  public dismiss(id: string): void {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('fade-out');
      setTimeout(() => {
        el.remove();
        this.notifications.delete(id);
      }, 150);
    }
  }

  private renderNotification(notif: Notification): void {
    if (!this.container) return;

    let iconSvg = Icons.info();
    let badgeClass = 'badge-neutral';

    if (notif.type === 'success') {
      iconSvg = Icons.success();
      badgeClass = 'badge-success';
    } else if (notif.type === 'warning') {
      iconSvg = Icons.warning();
      badgeClass = 'badge-warning';
    } else if (notif.type === 'error') {
      iconSvg = Icons.danger();
      badgeClass = 'badge-danger';
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
