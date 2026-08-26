/**
 * AIPI Institutional Skeleton Loading Layout Component (ES Module)
 */

import { htmlToElement } from '../utils/dom.js';

export class LoadingLayout {
  static renderSkeletonPage() {
    return htmlToElement(`
      <div class="skeleton-page-layout" role="status" aria-label="Loading page content">
        <!-- 1. Skeleton Header Area -->
        <div class="skeleton-header">
          <div class="skeleton-shimmer skeleton-title"></div>
          <div class="skeleton-shimmer skeleton-subtitle"></div>
        </div>

        <!-- 2. Skeleton KPI Strip -->
        <div class="skeleton-kpi-grid">
          <div class="skeleton-card skeleton-shimmer"></div>
          <div class="skeleton-card skeleton-shimmer"></div>
          <div class="skeleton-card skeleton-shimmer"></div>
          <div class="skeleton-card skeleton-shimmer"></div>
        </div>

        <!-- 3. Skeleton Primary Chart Area -->
        <div class="skeleton-chart-container skeleton-shimmer">
          <div class="skeleton-chart-lines">
            <div class="skeleton-line"></div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line"></div>
          </div>
        </div>

        <!-- 4. Skeleton Data Table Area -->
        <div class="skeleton-table-container skeleton-shimmer">
          <div class="skeleton-table-row header"></div>
          <div class="skeleton-table-row"></div>
          <div class="skeleton-table-row"></div>
          <div class="skeleton-table-row"></div>
        </div>
      </div>
    `);
  }
}
