/**
 * AIPI Enterprise Fixed Sidebar Component
 * 
 * Implements strict categorized navigation:
 * - Overview
 * - Market Intelligence (Route Analytics, Lead-Time Analysis)
 * - Quality & Validation (Statistical Validation, Volatility)
 * - Governance (Methodology)
 * - Developer (API Explorer)
 */

import { Icons } from '../icons/index.js';
import { NavigationCategory, NavigationItem, NavigationKey } from '../types/navigation.js';
import { htmlToElement } from '../utils/dom.js';

export const SIDEBAR_ITEMS: NavigationItem[] = [
  // Overview
  {
    id: 'overview',
    label: 'Overview',
    category: 'Overview',
    iconName: 'overview',
    description: 'Executive overview, composite inflation index, and macro summary'
  },
  // Market Intelligence
  {
    id: 'route-analytics',
    label: 'Route Analytics',
    category: 'Market Intelligence',
    iconName: 'routeAnalytics',
    description: '2D Sector heatmap matrix, route dispersion, and single-sector inspector'
  },
  {
    id: 'lead-time',
    label: 'Lead-Time Analysis',
    category: 'Market Intelligence',
    iconName: 'leadTime',
    description: 'Booking elasticity curve (T+1 to T+45) and advance window inflation'
  },
  // Quality & Validation
  {
    id: 'validation',
    label: 'Statistical Validation',
    category: 'Quality & Validation',
    iconName: 'validation',
    description: 'DGCA benchmark correlation, Pearson r, and accuracy diagnostics'
  },
  {
    id: 'volatility',
    label: 'Volatility',
    category: 'Quality & Validation',
    iconName: 'volatility',
    description: 'Intraday fare dispersion and Monte Carlo sparse-sampling error simulation'
  },
  // Governance
  {
    id: 'methodology',
    label: 'Methodology',
    category: 'Governance',
    iconName: 'methodology',
    description: 'Index formulae, route expenditure weights, and cleaning row accounting'
  },
  // Developer
  {
    id: 'api-explorer',
    label: 'API Explorer',
    category: 'Developer',
    iconName: 'apiExplorer',
    description: 'Live contract inspector and schema browser for all 12 backend endpoints'
  }
];

export interface SidebarCallbacks {
  onSelectView: (viewId: NavigationKey) => void;
  onCloseDrawer?: () => void;
}

export class Sidebar {
  private activeView: NavigationKey = 'overview';
  private callbacks: SidebarCallbacks;
  private element: HTMLElement | null = null;

  constructor(callbacks: SidebarCallbacks) {
    this.callbacks = callbacks;
  }

  public render(): HTMLElement {
    const categories: NavigationCategory[] = [
      'Overview',
      'Market Intelligence',
      'Quality & Validation',
      'Governance',
      'Developer'
    ];

    const sidebar = htmlToElement(`
      <aside class="app-sidebar" id="app-sidebar-nav" role="navigation" aria-label="Primary Navigation">
        <div class="sidebar-header-mobile">
          <div class="topbar-branding">
            ${Icons.crest()}
            <span class="text-h3" style="color: var(--color-brand-primary);">Navigation</span>
          </div>
          <button class="drawer-close-btn" id="sidebar-drawer-close" aria-label="Close navigation drawer">
            ${Icons.close()}
          </button>
        </div>

        <div class="sidebar-scrollable">
          ${categories.map((cat) => this.renderCategoryGroup(cat)).join('')}
        </div>

        <div class="sidebar-footer" id="sidebar-provenance-tray">
          <div class="provenance-label">ACTIVE PROVENANCE</div>
          <div class="provenance-val" id="provenance-run-id">run: connecting…</div>
          <div class="text-mono" id="provenance-sha" style="color: var(--color-text-secondary); margin-top: 2px;">sha: —</div>
        </div>
      </aside>
    `);

    // Attach click listeners
    const buttons = sidebar.querySelectorAll<HTMLButtonElement>('.sidebar-nav-item');
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetId = btn.dataset.navId as NavigationKey;
        if (targetId) {
          this.setActiveView(targetId);
          this.callbacks.onSelectView(targetId);
          if (this.callbacks.onCloseDrawer) this.callbacks.onCloseDrawer();
        }
      });
    });

    const closeBtn = sidebar.querySelector('#sidebar-drawer-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        if (this.callbacks.onCloseDrawer) this.callbacks.onCloseDrawer();
      });
    }

    this.element = sidebar;
    return sidebar;
  }

  private renderCategoryGroup(category: NavigationCategory): string {
    const items = SIDEBAR_ITEMS.filter((i) => i.category === category);
    if (items.length === 0) return '';

    return `
      <div class="sidebar-nav-group">
        ${category !== 'Overview' ? `<div class="sidebar-group-title">${category}</div>` : ''}
        <ul class="sidebar-nav-list" role="menubar" aria-label="${category}">
          ${items.map((item) => this.renderNavItem(item)).join('')}
        </ul>
      </div>
    `;
  }

  private renderNavItem(item: NavigationItem): string {
    const isActive = item.id === this.activeView;
    const iconFunc = Icons[item.iconName as keyof typeof Icons] || Icons.overview;

    return `
      <li role="none">
        <button class="sidebar-nav-item ${isActive ? 'active' : ''}" 
                data-nav-id="${item.id}" 
                role="menuitem"
                title="${item.description}"
                aria-current="${isActive ? 'page' : 'false'}">
          ${iconFunc()}
          <span class="nav-label">${item.label}</span>
          ${item.badge ? `<span class="badge badge-neutral">${item.badge}</span>` : ''}
        </button>
      </li>
    `;
  }

  public setActiveView(viewId: NavigationKey): void {
    this.activeView = viewId;
    if (!this.element) return;

    this.element.querySelectorAll<HTMLButtonElement>('.sidebar-nav-item').forEach((btn) => {
      const match = btn.dataset.navId === viewId;
      btn.classList.toggle('active', match);
      btn.setAttribute('aria-current', match ? 'page' : 'false');
    });
  }

  public setProvenance(runId: string, gitSha: string): void {
    const runEl = this.element?.querySelector('#provenance-run-id');
    const shaEl = this.element?.querySelector('#provenance-sha');
    if (runEl && runId) runEl.textContent = `run: ${runId.slice(0, 10)}`;
    if (shaEl && gitSha) shaEl.textContent = `sha: ${gitSha.slice(0, 8)}`;
  }
}
