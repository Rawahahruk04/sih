/**
 * AIPI Frontend Application Bootstrap
 * 
 * Boots the AppShell and orchestrates feature page navigation.
 */

import { api } from './api/client.js';
import { AppShell } from './layouts/AppShell.js';
import { ApiExplorerPage } from './pages/ApiExplorerPage.js';
import { LeadTimePage } from './pages/LeadTimePage.js';
import { MethodologyPage } from './pages/MethodologyPage.js';
import { OverviewPage } from './pages/OverviewPage.js';
import { RouteAnalyticsPage } from './pages/RouteAnalyticsPage.js';
import { RouteDetailPage } from './pages/RouteDetailPage.js';
import { ValidationPage } from './pages/ValidationPage.js';
import { VolatilityPage } from './pages/VolatilityPage.js';
import { NavigationKey } from './types/navigation.js';

class Application {
  private shell: AppShell;
  private rootElement: HTMLElement;
  private overviewPage: OverviewPage;
  private routeAnalyticsPage: RouteAnalyticsPage;
  private routeDetailPage: RouteDetailPage | null = null;
  private leadTimePage: LeadTimePage;
  private validationPage: ValidationPage;
  private volatilityPage: VolatilityPage;
  private methodologyPage: MethodologyPage;
  private apiExplorerPage: ApiExplorerPage;
  private currentActiveRoute: string | null = null;

  constructor(rootId: string) {
    const el = document.getElementById(rootId);
    if (!el) throw new Error(`Root element #${rootId} not found`);
    this.rootElement = el;

    this.overviewPage = new OverviewPage({
      onNotify: (type, title, message) => this.shell.notify(type, title, message)
    });

    this.routeAnalyticsPage = new RouteAnalyticsPage({
      onNotify: (type, title, message) => this.shell.notify(type, title, message),
      onNavigateToRoute: (routeCode) => this.navigateToRouteDetail(routeCode)
    });

    this.leadTimePage = new LeadTimePage({
      onNotify: (type, title, message) => this.shell.notify(type, title, message)
    });

    this.validationPage = new ValidationPage({
      onNotify: (type, title, message) => this.shell.notify(type, title, message)
    });

    this.volatilityPage = new VolatilityPage({
      onNotify: (type, title, message) => this.shell.notify(type, title, message)
    });

    this.methodologyPage = new MethodologyPage({
      onNotify: (type, title, message) => this.shell.notify(type, title, message)
    });

    this.apiExplorerPage = new ApiExplorerPage({
      onNotify: (type, title, message) => this.shell.notify(type, title, message)
    });

    this.shell = new AppShell({
      onNavigate: (viewId: NavigationKey) => {
        this.currentActiveRoute = null;
        this.handleNavigation(viewId);
      }
    });
  }

  public async init(): Promise<void> {
    // 1. Render AppShell Layout
    this.shell.render(this.rootElement);

    // 2. Mount Initial Screen (Overview)
    this.handleNavigation('overview');

    // 3. Synchronize Health & Provenance
    try {
      const [health, pipelineRun] = await Promise.all([
        api.getHealth().catch(() => null),
        api.getPipelineRun().catch(() => null)
      ]);

      if (health) {
        if (health.data_mode) {
          this.shell.setDemoBanner(health.data_mode.is_demo_data, health.data_mode.banner);
        }
        this.shell.setDataAge(health.hours_since_latest_index, health.latest_index_date);
        const statusLabel = health.status === 'ok'
          ? (health.data_mode?.is_demo_data ? 'SIMULATED DATA' : 'LIVE MARKET')
          : 'DEGRADED';
        this.shell.setHealthStatus(health.status === 'ok', statusLabel);
      } else {
        this.shell.setHealthStatus(false, 'OFFLINE');
      }

      if (pipelineRun) {
        this.shell.setProvenance(pipelineRun.run_id, pipelineRun.git_sha);
      }
    } catch (err) {
      this.shell.setHealthStatus(false, 'OFFLINE');
      console.warn('Initial health sync failed:', err);
    }
  }

  private abortAllPendingRequests(): void {
    (this.overviewPage as any)?.abortController?.abort();
    (this.routeAnalyticsPage as any)?.abortController?.abort();
    (this.routeDetailPage as any)?.abortController?.abort();
    (this.leadTimePage as any)?.abortController?.abort();
    (this.validationPage as any)?.abortController?.abort();
    (this.volatilityPage as any)?.abortController?.abort();
    (this.methodologyPage as any)?.abortController?.abort();
    (this.apiExplorerPage as any)?.abortController?.abort();
  }

  private navigateToRouteDetail(routeCode: string): void {
    this.abortAllPendingRequests();
    this.currentActiveRoute = routeCode;

    this.shell.setPageHeader({
      title: `Sector Inspector: ${routeCode}`,
      subtitle: `Deep-dive price trajectory and observation history for sector ${routeCode}.`,
      badge: { label: 'Route Detail Active', variant: 'neutral' },
      actionsHtml: `
        <button class="empty-state-action-btn" id="detail-refresh-btn" style="padding: 6px 12px; font-size: 12px;">
          <span>Refresh Sector</span>
        </button>
      `
    });

    const bodySlot = document.getElementById('page-body-slot');
    if (bodySlot) {
      this.routeDetailPage = new RouteDetailPage(routeCode, {
        onBackToRoutes: () => {
          this.currentActiveRoute = null;
          this.handleNavigation('route-analytics');
        },
        onNotify: (type, title, message) => this.shell.notify(type, title, message)
      });
      this.routeDetailPage.render(bodySlot);
    }

    const refreshBtn = document.getElementById('detail-refresh-btn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        if (this.routeDetailPage) {
          this.routeDetailPage.fetchData();
          this.shell.notify('info', 'Refreshing Sector', `Reloading series for ${routeCode}…`);
        }
      });
    }
  }

  private handleNavigation(viewId: NavigationKey): void {
    this.abortAllPendingRequests();

    if (viewId === 'overview') {
      this.shell.setPageHeader({
        title: 'Executive Overview',
        subtitle: 'National composite Laspeyres airfare price index and macroeconomic indicator monitor.',
        badge: { label: 'MoSPI Official Methodology', variant: 'neutral' },
        actionsHtml: `
          <button class="empty-state-action-btn" id="header-refresh-btn" style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px;">
            <span>Refresh Series</span>
          </button>
        `
      });

      const bodySlot = document.getElementById('page-body-slot');
      if (bodySlot) {
        this.overviewPage.render(bodySlot);
      }

      const refreshBtn = document.getElementById('header-refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          this.overviewPage.fetchData();
          this.shell.notify('info', 'Refreshing Series', 'Connecting to index calculation engine…');
        });
      }
      return;
    }

    if (viewId === 'route-analytics') {
      this.shell.setPageHeader({
        title: 'Route Analytics & Sector Intelligence',
        subtitle: '2D sector-date matrix, route price dispersion, and individual sector trajectory inspector.',
        badge: { label: '12 Primary Sectors Tracked', variant: 'neutral' },
        actionsHtml: `
          <button class="empty-state-action-btn" id="header-refresh-btn" style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px;">
            <span>Refresh Heatmap</span>
          </button>
        `
      });

      const bodySlot = document.getElementById('page-body-slot');
      if (bodySlot) {
        this.routeAnalyticsPage.render(bodySlot);
      }

      const refreshBtn = document.getElementById('header-refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          this.routeAnalyticsPage.fetchData();
          this.shell.notify('info', 'Refreshing Sectors', 'Reloading 2D heatmap matrix…');
        });
      }
      return;
    }

    if (viewId === 'lead-time') {
      this.shell.setPageHeader({
        title: 'Booking Lead-Time Elasticity',
        subtitle: 'Advance purchase pricing curves (T+1 to T+45) and walk-up booking premium analysis.',
        badge: { label: 'T+14 Reference Horizon (=100.0)', variant: 'neutral' },
        actionsHtml: `
          <button class="empty-state-action-btn" id="header-refresh-btn" style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px;">
            <span>Refresh Curve</span>
          </button>
        `
      });

      const bodySlot = document.getElementById('page-body-slot');
      if (bodySlot) {
        this.leadTimePage.render(bodySlot);
      }

      const refreshBtn = document.getElementById('header-refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          this.leadTimePage.fetchData();
          this.shell.notify('info', 'Refreshing Curve', 'Recalculating lead-time elasticity matrix…');
        });
      }
      return;
    }

    if (viewId === 'validation') {
      this.shell.setPageHeader({
        title: 'Statistical Validation & Quality Assurance',
        subtitle: 'Econometric cross-validation against official DGCA monthly fare statistics and Monte Carlo error bounds.',
        badge: { label: 'DGCA Benchmark & Monte Carlo Audit', variant: 'neutral' },
        actionsHtml: `
          <button class="empty-state-action-btn" id="header-refresh-btn" style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px;">
            <span>Refresh Validation</span>
          </button>
        `
      });

      const bodySlot = document.getElementById('page-body-slot');
      if (bodySlot) {
        this.validationPage.render(bodySlot);
      }

      const refreshBtn = document.getElementById('header-refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          this.validationPage.fetchData();
          this.shell.notify('info', 'Refreshing Validation', 'Recalculating econometric backtests…');
        });
      }
      return;
    }

    if (viewId === 'volatility') {
      this.shell.setPageHeader({
        title: 'Volatility & Sampling Error',
        subtitle: 'Intraday capture dispersion and Monte Carlo sparse-sampling error simulations.',
        badge: { label: 'Monte Carlo Measurement Error', variant: 'neutral' },
        actionsHtml: `
          <button class="empty-state-action-btn" id="header-refresh-btn" style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px;">
            <span>Refresh Volatility</span>
          </button>
        `
      });

      const bodySlot = document.getElementById('page-body-slot');
      if (bodySlot) {
        this.volatilityPage.render(bodySlot);
      }

      const refreshBtn = document.getElementById('header-refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          this.volatilityPage.fetchData();
          this.shell.notify('info', 'Refreshing Volatility', 'Recalculating volatility and sampling-error diagnostics…');
        });
      }
      return;
    }

    if (viewId === 'methodology') {
      this.shell.setPageHeader({
        title: 'Methodology & Governance Dossier',
        subtitle: 'Mathematical formulae specification, route expenditure weights, and 11-stage cleaning row accounting.',
        badge: { label: 'MoSPI Candidate Methodology', variant: 'neutral' },
        actionsHtml: `
          <button class="empty-state-action-btn" id="header-refresh-btn" style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px;">
            <span>Refresh Dossier</span>
          </button>
        `
      });

      const bodySlot = document.getElementById('page-body-slot');
      if (bodySlot) {
        this.methodologyPage.render(bodySlot);
      }

      const refreshBtn = document.getElementById('header-refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          this.methodologyPage.fetchData();
          this.shell.notify('info', 'Refreshing Dossier', 'Reloading methodology specification…');
        });
      }
      return;
    }

    if (viewId === 'api-explorer') {
      this.shell.setPageHeader({
        title: 'API Explorer & Contract Inspector',
        subtitle: 'Institutional read-only inspection console for verified backend endpoints, live GET requests, response schemas, and error envelopes.',
        badge: { label: 'Read-Only API Console', variant: 'neutral' },
        actionsHtml: `
          <button class="empty-state-action-btn" id="header-refresh-btn" style="padding: 6px 12px; font-size: 12px; display: inline-flex; align-items: center; gap: 6px;">
            <span>Refresh Health</span>
          </button>
        `
      });

      const bodySlot = document.getElementById('page-body-slot');
      if (bodySlot) {
        this.apiExplorerPage.render(bodySlot);
      }

      const refreshBtn = document.getElementById('header-refresh-btn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
          this.apiExplorerPage.refreshHealth();
          this.shell.notify('info', 'Refreshing API Health', 'Pinging backend health endpoint...');
        });
      }
      return;
    }
  }
}

// Start application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new Application('app-root');
  app.init();
});
