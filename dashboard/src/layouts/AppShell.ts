/**
 * AIPI Enterprise Application Shell
 * 
 * Orchestrates Header, Sidebar, Breadcrumb, ContentContainer, NotificationLayer,
 * and responsive drawer behavior.
 */

import { Breadcrumb } from '../components/Breadcrumb.js';
import { ContentContainer, PageHeaderConfig } from '../components/ContentContainer.js';
import { EmptyLayout, EmptyLayoutOptions } from '../components/EmptyLayout.js';
import { Header } from '../components/Header.js';
import { LoadingLayout } from '../components/LoadingLayout.js';
import { notifications } from '../components/NotificationLayer.js';
import { Sidebar, SIDEBAR_ITEMS } from '../components/Sidebar.js';
import { Icons } from '../icons/index.js';
import { BreadcrumbItem, NavigationKey } from '../types/navigation.js';
import { htmlToElement } from '../utils/dom.js';

export interface AppShellCallbacks {
  onNavigate: (viewId: NavigationKey) => void;
}

export class AppShell {
  private activeView: NavigationKey = 'overview';
  private callbacks: AppShellCallbacks;
  private header: Header;
  private sidebar: Sidebar;
  private breadcrumb: Breadcrumb;
  private contentContainer: ContentContainer;
  private drawerOpen = false;

  constructor(callbacks: AppShellCallbacks) {
    this.callbacks = callbacks;

    this.header = new Header({
      onToggleSidebar: () => this.toggleDrawer(),
      onRefresh: () => this.callbacks.onNavigate(this.activeView)
    });

    this.sidebar = new Sidebar({
      onSelectView: (viewId) => {
        this.setActiveView(viewId);
        this.callbacks.onNavigate(viewId);
      },
      onCloseDrawer: () => this.closeDrawer()
    });

    this.breadcrumb = new Breadcrumb({
      onNavigate: (viewId) => {
        this.setActiveView(viewId);
        this.callbacks.onNavigate(viewId);
      }
    });

    this.contentContainer = new ContentContainer();
  }

  public render(container: HTMLElement): void {
    const layout = htmlToElement(`
      <div class="app-shell">
        <a href="#main-content" class="skip-link">Skip to main content</a>
        
        <!-- 1. Global Demo Data Alert Banner -->
        <div class="app-banner hidden" id="global-demo-banner" role="alert">
          ${Icons.warning()}
          <span id="demo-banner-text" style="margin-left: 8px;">Contains simulated data — not a measurement of real airfares.</span>
        </div>

        <!-- 2. Institutional Topbar (Mount Point) -->
        <div id="topbar-mount-point"></div>

        <!-- 3. Body: Sidebar + Main Workspace -->
        <div class="app-body">
          <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
          <div id="sidebar-mount-point"></div>

          <main class="app-main" id="main-content" role="main">
            <div id="breadcrumb-mount-point"></div>
            <div id="content-container-mount-point"></div>
          </main>
        </div>
      </div>
    `);

    container.innerHTML = '';
    container.appendChild(layout);

    // Mount subcomponents
    const topbarMount = layout.querySelector('#topbar-mount-point');
    const sidebarMount = layout.querySelector('#sidebar-mount-point');
    const breadcrumbMount = layout.querySelector('#breadcrumb-mount-point');
    const contentMount = layout.querySelector('#content-container-mount-point');

    if (topbarMount) topbarMount.replaceWith(this.header.render());
    if (sidebarMount) sidebarMount.replaceWith(this.sidebar.render());
    if (breadcrumbMount) breadcrumbMount.replaceWith(this.breadcrumb.render());
    if (contentMount) contentMount.replaceWith(this.contentContainer.render());

    // Mount Notification layer
    notifications.mount(layout);

    // Attach backdrop listener
    const backdrop = layout.querySelector('#sidebar-backdrop');
    if (backdrop) {
      backdrop.addEventListener('click', () => this.closeDrawer());
    }

    // Keyboard shortcuts: Escape closes drawer, Ctrl+B toggles drawer
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.drawerOpen) {
        this.closeDrawer();
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        this.toggleDrawer();
      }
    });

    this.updateBreadcrumbs();
  }

  public setActiveView(viewId: NavigationKey): void {
    this.activeView = viewId;
    this.sidebar.setActiveView(viewId);
    this.updateBreadcrumbs();
  }

  private updateBreadcrumbs(): void {
    const item = SIDEBAR_ITEMS.find((i) => i.id === this.activeView);
    if (!item) return;

    const trail: BreadcrumbItem[] = [
      { label: 'Intelligence Platform', id: 'overview' },
      { label: item.category },
      { label: item.label, id: item.id, isCurrent: true }
    ];

    this.breadcrumb.setTrail(trail);
    const breadcrumbMount = document.querySelector('.breadcrumbs');
    if (breadcrumbMount) {
      breadcrumbMount.replaceWith(this.breadcrumb.render());
    }
  }

  public setPageHeader(config: PageHeaderConfig): void {
    const mainSlot = document.querySelector('.page-container');
    if (mainSlot) {
      mainSlot.replaceWith(this.contentContainer.render(config));
    }
  }

  public setPageContent(content: HTMLElement | string): void {
    this.contentContainer.setBodyContent(content);
  }

  public showLoading(): void {
    this.setPageContent(LoadingLayout.renderSkeletonPage());
  }

  public showEmpty(options: EmptyLayoutOptions): void {
    this.setPageContent(EmptyLayout.render(options));
  }

  public toggleDrawer(): void {
    if (this.drawerOpen) {
      this.closeDrawer();
    } else {
      this.openDrawer();
    }
  }

  public openDrawer(): void {
    this.drawerOpen = true;
    const sidebarEl = document.getElementById('app-sidebar-nav');
    const backdropEl = document.getElementById('sidebar-backdrop');
    if (sidebarEl) sidebarEl.classList.add('drawer-open');
    if (backdropEl) backdropEl.classList.add('active');
  }

  public closeDrawer(): void {
    this.drawerOpen = false;
    const sidebarEl = document.getElementById('app-sidebar-nav');
    const backdropEl = document.getElementById('sidebar-backdrop');
    if (sidebarEl) sidebarEl.classList.remove('drawer-open');
    if (backdropEl) backdropEl.classList.remove('active');
  }

  public setDemoBanner(isDemo: boolean, bannerText?: string | null): void {
    const banner = document.getElementById('global-demo-banner');
    const text = document.getElementById('demo-banner-text');
    if (banner && text) {
      banner.classList.toggle('hidden', !isDemo);
      if (bannerText) text.textContent = bannerText;
    }
  }

  public setProvenance(runId: string, gitSha: string): void {
    this.sidebar.setProvenance(runId, gitSha);
  }

  public setDataAge(hoursAgo: number | null, latestDate: string | null): void {
    if (latestDate && hoursAgo != null) {
      this.header.setDataAge(`Latest: ${latestDate} (${hoursAgo.toFixed(1)}h ago)`);
    } else {
      this.header.setDataAge('Data unpopulated');
    }
  }

  public notify(type: 'success' | 'warning' | 'error' | 'info', title: string, message?: string): string {
    return notifications.show({ type, title, message });
  }
}
