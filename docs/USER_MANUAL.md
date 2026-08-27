# AIPI Institutional User Manual

**Airfare Price Index for India (AIPI)**  
*Operational Decision Support Manual for Ministry of Statistics and Programme Implementation (MoSPI) Economists & Statistical Officers*

---

## 1. System Introduction & Navigation

The AIPI Intelligence Platform is a real-time decision support system designed to monitor, analyze, and publish high-frequency price indices for Indian domestic airfares.

### 1.1 Persistent Institutional Header
At the top of every screen, the global header provides real-time operational context:
- **MoSPI Emblem & Title**: Confirms platform identity.
- **Live Status Pill (`LIVE 06:30 IST`)**: Indicates synchronization with the daily morning calculation run.
- **Data Age Indicator**: Displays the timestamp and elapsed hours since the last published observation.
- **User Role Badge (`Officer (MoSPI)`)**: Denotes authenticated analytical access.

### 1.2 Sidebar Navigation
The left sidebar is organized into five operational domains:
- **Overview**: Executive inflation monitor and national macro summary.
- **Market Intelligence**: Route Analytics (2D Heatmap) and Booking Lead-Time analysis.
- **Quality & Validation**: Statistical Validation (DGCA backtest) and Volatility diagnostics.
- **Governance**: Official Methodology specification and cleaning row accounting.
- **Developer**: Interactive API Explorer and contract schema inspector.
- **Active Provenance Tray (Footer)**: Displays the active `run_id` and git SHA hash.

---

## 2. Screen 1: Executive Overview (Headline Monitor)

### Purpose
Provides a macro-level overview of domestic airfare inflation across India, updating daily based on Laspeyres expenditure aggregation of rolling GEKS-Jevons elementary indices.

### Key Visual Elements
1. **Headline Metric Card**:
   - **Current Index Level**: Current composite index value in points (e.g. `104.28 pts`).
   - **vs Base Window Delta**: Percentage movement relative to the base period geometric mean ($100.0$).
   - **Base Window Stamp**: Exact dates defining the 14-day base window (e.g. `2026-07-01 … 2026-07-14`).
2. **Primary KPI Strip**:
   - `Current Index Level`: Point value with Day-on-Day period change.
   - `Net Inflation vs Base`: Cumulative price change percentage.
   - `Sample Coverage`: Percentage of basket routes observed (target: $\ge 90\%$).
   - `Matched Pair Purity`: Number of flight numbers successfully linked via Jevons price relatives.
3. **Interactive Time-Series Canvas**:
   - **Frequency Selector**: Switch between `Daily`, `Weekly`, and `Monthly` index frequencies.
   - **Day-of-Week (DoW) Adjustment**: Toggle the 7-day seasonal adjustment curve on the daily series. *(Note: Disabled for Weekly and Monthly frequencies as seasonal weekday bias averages out over multi-day periods)*.
   - **Date Range Slicers (`From` / `To`)**: Slice the time-series between specific calendar dates.
   - **Crosshair Hover Tooltip**: Hover over any date to inspect exact index points, coverage percentage, and quotation counts.
4. **Quality & Provenance Dossier**:
   - Detailed accounting of observation counts, resampling completeness, and cryptographic run lineage (`run_id`, git SHA, config hash).

---

## 3. Screen 2: Route Analytics & 2D Sector Heatmap

### Purpose
Examines price dispersion, expenditure weights, and sector-level inflation spikes across all 12 primary domestic routes.

### How to Use
1. **Inspect Sector Summary Cards**:
   - View `Highest Inflation Sector` and `Lowest Inflation Sector` along with current index divergence.
   - Review `Cross-Sector Spread` (the point gap between the highest and lowest inflating sector).
2. **Explore the 2D Sector Heatmap Matrix**:
   - **X-Axis**: Observation dates.
   - **Y-Axis**: 12 Domestic Routes (e.g., `DEL-BOM`, `BOM-BLR`, `DEL-CCU`).
   - **Color Scale**:
     - **Teal (#356C7B)**: Fares below base period ($< 100.0$).
     - **Cream (#F2EFD9)**: Fares near base period benchmark ($100.0$).
     - **Crimson (#B54848)**: Elevated inflation spikes ($> 100.0$).
     - **Hatched Pattern**: Missing/uncollected observations (`null`).
   - **Cell Inspection**: Hover or focus on any cell to reveal sector name, date, index points, and deviation from base.
   - **Direct Navigation**: Click on any route label or heatmap row to open the dedicated **Sector Inspector**.
3. **Filter the Master Route Table**:
   - Use the `Search Sectors` input to filter routes by city name or airport code (e.g., "Mumbai" or "BLR").
   - Click column headers (`Route Code`, `Sector Name`, `Basket Weight`, `Latest Index`, `vs Base`) to sort ascending or descending.

---

## 4. Screen 3: Sector Inspector (Route Deep-Dive)

### Purpose
Performs forensic audit of a single domestic city pair, displaying historical trajectory curves and chronological quotation records.

### Features
- **Breadcrumb Navigation**: Click `← Back to Route Analytics` to return to the sector master.
- **Expenditure Share Badge**: Shows the route's Laspeyres weight $w_r$ derived from DGCA base traffic.
- **Trajectory Time Series**: Isolated SVG time series with a reference baseline at $100.0$.
- **Chronological Observation Table**: Full tabular ledger listing every observation date, index value, quotation counts, sample coverage, and data health status.

---

## 5. Screen 4: Booking Lead-Time Analysis

### Purpose
Quantifies dynamic yield management and airline advance-purchase price curves, separating advance booking discounts from walk-up premiums.

### Understanding the Visualizations
1. **Advance Purchase Elasticity Yield Curve**:
   - Displays relative price levels across advance horizons from **T+1** (departure tomorrow) to **T+45** (45 days in advance).
   - **Baseline ($100.0$)**: Normalized to the standard 14-day advance window ($T+14$).
   - **Walk-Up Premium**: Identifies the percentage premium demanded for last-minute bookings.
2. **Inflation by Advance Purchase Window**:
   - Multi-series time-series tracking how inflation rates vary over time across different booking horizons ($T+1$, $T+7$, $T+14$, $T+30$).
   - Use the segmented control to isolate specific horizons or view all simultaneously.
3. **Horizon Metrics Grid**:
   - Detailed table comparing relative fare multipliers, point changes vs $T+14$, latest inflation indices, and observation sample sizes.

---

## 6. Screen 5: Statistical Validation & Quality Assurance

### Purpose
Evaluates construct validity and back-tests the AIPI daily index against official monthly DGCA statistics.

### Interpreting Statistical Metrics
1. **DGCA Back-Test Comparison Table**:
   - **Pearson Correlation ($r$)**: Measures linear co-movement with official DGCA airline statistics.
   - **Spearman Rank Correlation ($\rho$)**: Measures monotonic ranking consistency.
   - **Mean Absolute Percentage Error (MAPE)**: Quantifies percentage deviation.
   - **Directional Accuracy**: Measures the proportion of months where AIPI and DGCA agreed on the direction of price movement (inflation vs deflation).
   - **$N \ge 8$ Statistical Discipline**: When sample months are fewer than 8 ($N < 8$), correlation values are suppressed with the label `"Below N=8 Threshold"` to prevent statistically invalid claims.
2. **Construct Validity Checks**:
   - `Lead-Time Monotonicity`: Confirms whether average fares strictly decrease as advance days increase ($T+1 > T+7 > T+14 > T+30$).
   - `Lead-Time Spread`: Measures the total dynamic pricing elasticity spread across the market.

---

## 7. Screen 6: Volatility & Sampling Error Diagnostics

### Purpose
Quantifies the measurement error introduced by sparse collection designs and establishes the minimum sampling frequency required for official CPI publication.

### Key Insights
1. **Daily Index Volatility**:
   - Standard deviation of day-on-day relative price movements.
   - Maximum single-day price movement recorded in the dataset.
   - **Amadeus Flat Cache Check**: Alerts if index variations are suspiciously flat due to cached travel agency feeds.
2. **Intraday Fare Dispersion**:
   - Measures the Coefficient of Variation (CV) across multiple capture slots within the same day.
3. **Monte Carlo Sparse-Sampling Simulation**:
   - Demonstrates that collecting **1 day per month** produces an average error of **1.57% MAE** and **27.1% direction error**.
   - Identifies the exact collection frequency required to achieve $\le 1.0\%$ MAE (proven to be **3 days per month**).

---

## 8. Screen 7: Methodology Specification & Governance Dossier

### Purpose
Provides statistical auditors and government review committees with full transparency into index construction, mathematical formulae, and data cleaning row accounting.

### Sections
1. **Formula Specifications**:
   - Exact mathematical formulations for elementary Jevons matching, multilateral GEKS transitivity, movement splicing, and upper-level Laspeyres expenditure aggregation.
2. **11-Stage Data Cleaning Accounting**:
   - Full input row vs accepted row ledger.
   - Itemized breakdown of quarantined records (codeshares, currency anomalies, non-stop exclusions, and MAD outlier trims).
3. **DGCA Expenditure Weights ($w_r$)**:
   - Transparent table of all 12 sector weights calculated as $p_0 q_0 / \sum p_0 q_0$.
4. **Cryptographic Lineage Inspector**:
   - Interactive JSON inspector allowing raw cryptographic audit of the active pipeline run.

---

## 9. Screen 8: Live API Explorer & Technical Console

### Purpose
Allows technical teams and integrators to inspect live OpenAPI schemas, test REST requests in real-time, and verify JSON response contracts.

### How to Use
1. **Endpoint Selector**: Choose from all 12 verified backend routes organized by category (`Operations`, `Reference`, `Index`, `Validation`).
2. **Contract Block**: Review required path/query parameters, parameter locations, and expected return types.
3. **Live Request Console**:
   - Adjust query parameters in real time (e.g. `freq`, `dow_adjusted`, `from`, `to`).
   - Click `Send Request` to execute a non-mutating live fetch.
   - Inspect response status (`200 OK`), round-trip latency (ms), response payload size (KB), and formatted JSON syntax.
   - Click `Copy JSON` to copy the backend payload directly to the clipboard.
