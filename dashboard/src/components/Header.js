/**
 * AIPI Institutional Government Header Component (ES Module)
 */

import { Icons } from '../icons/index.js';
import { htmlToElement } from '../utils/dom.js';

export class Header {
  constructor(callbacks) {
    this.callbacks = callbacks;
    this.element = null;
  }

  render() {
    const header = htmlToElement(`
      <header class="app-topbar" role="banner">
        <div class="topbar-left">
          <button class="topbar-menu-btn" id="sidebar-toggle-btn" aria-label="Toggle navigation menu">
            ${Icons.menu()}
          </button>
          <div class="topbar-branding">
            ${Icons.crest()}
            <div class="topbar-title-group">
              <span class="topbar-title">AIPI Intelligence Platform</span>
              <span class="topbar-subtitle">MoSPI · PS 26056</span>
            </div>
          </div>
        </div>

        <div class="topbar-meta">
          <div class="meta-item">
            <span class="status-pill online" id="health-status-pill">CONNECTING…</span>
          </div>
          <div class="meta-item data-age-wrapper">
            <span class="text-small" id="data-age-indicator" style="color: var(--color-brand-accent);">Syncing health…</span>
          </div>
          
          <!-- Government Official Role Indicator -->
          <div class="user-role-badge" title="Authenticated Government Official">
            ${Icons.user()}
            <span class="text-small user-label">Officer (MoSPI)</span>
          </div>
        </div>
      </header>
    `);

    const toggleBtn = header.querySelector('#sidebar-toggle-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => this.callbacks.onToggleSidebar());
    }

    this.element = header;
    return header;
  }

  setStatus(isOnline, label = 'ONLINE') {
    const pill = this.element?.querySelector('#health-status-pill');
    if (pill) {
      pill.className = `status-pill ${isOnline ? 'online' : 'offline'}`;
      pill.textContent = label;
    }
  }

  setDataAge(text) {
    const ageEl = this.element?.querySelector('#data-age-indicator');
    if (ageEl) {
      ageEl.textContent = text;
    }
  }
}
