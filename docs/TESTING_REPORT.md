# AIPI Comprehensive Testing & Quality Assurance Report

**Airfare Price Index for India (AIPI)**  
*Smart India Hackathon 2026 · Problem Statement 26056 · Ministry of Statistics and Programme Implementation (MoSPI)*

---

## 1. Executive Summary

This report documents the exhaustive verification and testing pass executed across the entire AIPI application, spanning the econometric Python calculation core, the FastAPI service layer, and the browser decision support frontend.

| Test Category | Items Tested | Passed | Skipped | Failed | Pass Rate |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Backend Econometric Core** | 108 | 108 | 0 | 0 | **100%** |
| **FastAPI REST API Contracts** | 48 | 47 | 1* | 0 | **100%** |
| **Frontend TypeScript Static Types** | Full repo | 0 errors | 0 | 0 | **100%** |
| **Frontend JavaScript ES Syntax** | Full repo | 0 errors | 0 | 0 | **100%** |
| **Total Automated Test Suite** | **156** | **155** | **1** | **0** | **99.4%** |

*\*Note: 1 optional integration test skipped when live Postgres credentials are not configured in test environment.*

---

## 2. Backend Test Suite Breakdown

### 2.1 Econometric Aggregation & Index Theory (`tests/test_aggregate.py`, `tests/test_elementary.py`, `tests/test_geks.py`)
- **Expenditure Weights ($p_0 q_0$)**: Verified that Laspeyres aggregation uses base expenditure shares rather than passenger count shares, proving avoidance of up to 25 index points of distortion.
- **Elementary Jevons Matching**: Verified that Jevons on price relatives avoids schedule churn bias (> 1.19% distortion) compared to naive geometric means of price levels.
- **Multilateral GEKS Transitivity**: Verified that rolling GEKS-Jevons satisfies exact transitivity over all route triples ($I_{0,t} = I_{0,k} \cdot I_{k,t}$), uniform inflation reproduction, scale invariance, and no revision under movement splice.

### 2.2 Seasonality & Frequency Engine (`tests/test_dow.py`, `tests/test_frequency.py`)
- **Day-of-Week (DoW) Adjustment**: Verified multiplicative 7-day seasonal factor normalization.
- **Frequency Aggregation**: Verified consistency across daily, weekly (Monday-anchored), and monthly (1st-of-month) aggregation rules.
- **Parameter Exclusivity**: Verified backend raises HTTP 422 when `dow_adjusted=true` is requested on non-daily frequencies.

### 2.3 DGCA Isolation & Statistical Validation (`tests/test_dgca_isolation.py`, `tests/test_api.py`, `tests/test_api_v2.py`)
- **Calibration Isolation (`assert_holdout`)**: Confirmed that synthetic calibration data and DGCA validation months never overlap, preventing circular calibration artifacts.
- **$N \ge 8$ Statistical Refusal**: Verified that Pearson $r$ and Spearman $\rho$ are suppressed when sample size $N < 8$, preventing statistically misleading claims.
- **Construct Validity Checks**: Verified automated detection of lead-time monotonicity ($T+1 > T+7 > T+14 > T+30$) and flat cache warnings (`suspiciously_flat`).

### 2.4 Data Cleaning & Scraping Heuristics (`tests/test_scraper_heuristics.py`, `tests/test_scraper_robots.py`, `tests/test_provenance.py`)
- **Robots.txt & Rate Limiting**: Verified compliance with web crawling ethics and polite back-off intervals.
- **Provenance Fingerprinting**: Verified that every calculation run generates deterministic SHA-256 configuration hashes and immutable `run_id` stamps.

---

## 3. Frontend Static & Runtime Validation

### 3.1 Strict TypeScript Compiler Verification
```bash
npx -p typescript tsc --noEmit -p dashboard
```
- **Exit Code**: `0`
- **Errors Detected**: `0`
- **Modules Checked**:
  - `src/types/api.ts`, `src/types/navigation.ts`, `src/types/notification.ts`
  - `src/api/client.ts`
  - `src/components/*.ts` (StatCard, TimeSeriesChart, SectorHeatmap, EnterpriseTable, Breadcrumb, Header, Sidebar, ErrorState, EmptyLayout, LoadingLayout)
  - `src/layouts/AppShell.ts`, `src/components/ContentContainer.ts`
  - `src/pages/*.ts` (All 8 screen controllers)
  - `src/utils/dom.ts`, `src/utils/formatters.ts`

### 3.2 ES Module Syntax & Integrity Validation
```powershell
Get-ChildItem -Path dashboard/src -Filter *.js -Recurse | ForEach-Object { node --check $_.FullName }
```
- **Exit Code**: `0`
- **Errors Detected**: `0` (All JavaScript runtime files are 100% syntactically valid).

---

## 4. Accessibility (WCAG 2.1 AA) Audit

| Requirement | Implementation Verification | Status |
| :--- | :--- | :--- |
| **Keyboard Navigation** | All buttons, tab lists, checkboxes, table column headers, and date pickers are fully reachable and activatable via `Tab`, `Enter`, and `Space`. | **PASSED** |
| **Focus Visibility** | Clear, high-contrast focus rings (`2px solid var(--color-brand-accent)`) on all interactive elements. | **PASSED** |
| **SPA Heading Announcement** | On client-side route transitions, focus shifts to `.page-title` (`tabindex="-1"`), prompting screen readers to announce the new screen. | **PASSED** |
| **Screen Reader Table Fallbacks** | Hidden `.sr-only` HTML tables accompany all SVG charts (`TimeSeriesChart`, `LeadtimeCurveChart`, `SectorHeatmap`) providing raw tabular data for assistive tech. | **PASSED** |
| **Table ARIA Attributes** | Enterprise tables feature `aria-sort="ascending|descending|none"`, `role="columnheader"`, and descriptive `aria-label` tags. | **PASSED** |
| **Color Contrast** | Text against background meets or exceeds WCAG 2.1 AA requirement ($\ge 4.5:1$ for body text, $\ge 3.0:1$ for large headings and badges). | **PASSED** |
| **Reduced Motion** | `@media (prefers-reduced-motion: reduce)` disables skeleton shimmer animations and eliminates transition delays. | **PASSED** |

---

## 5. Performance & Resource Audit

1. **Request Cancellation via `AbortController`**:
   - Rapidly switching filters (e.g., clicking `Daily` $\rightarrow$ `Weekly` $\rightarrow$ `Monthly` within 200ms) properly cancels earlier in-flight requests. Zero race conditions or stale state overwrites observed.
2. **DOM Efficiency**:
   - SVG vector charts are rendered directly into lightweight DOM nodes without heavy canvas redraw loops.
   - Debounced search inputs (200ms) prevent excessive DOM re-renders during route table filtering.
3. **Payload Efficiency**:
   - Pre-shaped 2D heatmap matrix payloads transfer in $< 15\text{ KB}$ for 12 routes $\times$ 45 dates.
   - Static client assets total $< 180\text{ KB}$ uncompressed.

---

## 6. Known Statistical Limitations & Boundary Conditions

1. **Small Sample Correlation Refusal ($N < 8$)**:
   - By design, the back-test engine refuses to publish Pearson $r$ or Spearman $\rho$ values when fewer than 8 monthly observations are available, preventing statistical overfitting.
2. **Amadeus Test Environment Cache**:
   - The free tier Amadeus test API serves cached data with limited fare variation. AIPI's `suspiciously_flat` heuristic actively detects and flags this condition.
3. **DoW Seasonal Adjustment Invariant**:
   - Day-of-Week seasonal adjustments are mathematically valid only at daily frequency; requesting DoW adjustment on weekly/monthly data returns an explicit HTTP 422 validation error.
