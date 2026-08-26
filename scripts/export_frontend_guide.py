"""Generate FRONTEND_API_GUIDE.md in the root and docs/ folders."""
from pathlib import Path

content = """# AIPI API — Frontend Integration Guide & Contract

> **Target Audience:** Frontend Engineering Team  
> **Base URL:** `http://localhost:8000`  
> **Swagger UI:** `http://localhost:8000/docs`  
> **OpenAPI Schema File:** [`openapi.json`](openapi.json)  
> **Auth:** None (all endpoints are public read-only `GET` requests)

---

## 🚀 1. Quick Start & Client Codegen

### Option A: Run Backend via Docker (Recommended)
```bash
docker compose up
```
* Backend starts at `http://localhost:8000`
* Automatically warms up the in-memory data store with 75+ days of index points
* Ready immediately (no manual seeding or DB migrations needed)

### Option B: Auto-generate TypeScript Types
You don't need to manually type the fetch calls. Run this in your frontend project using the committed `openapi.json`:
```bash
# Using openapi-typescript:
npx openapi-typescript ./openapi.json -o src/types/api.ts

# Or using orval / openapi-generator:
npx orval --input ./openapi.json --output src/api/generated.ts
```

### 🌐 CORS Configuration
By default, CORS allows all origins (`*`) for local dev. If your frontend dev server runs on `http://localhost:5173` or `http://localhost:3000`, it works out of the box. To whitelist specific domains in production, configure the `FRONTEND_ORIGINS` environment variable:
```env
FRONTEND_ORIGINS=http://localhost:5173,https://your-dashboard.vercel.app
```

---

## ⚠️ 2. Core UI & Data Rules (Must-Read)

1. **Persistent Data Mode Banner:**
   * Every data endpoint includes a `data_mode` object.
   * If `data_mode.is_demo_data === true` (or `data_mode.banner` is not null), show the banner text at the top of the dashboard:
     > *"Contains simulated data — not a measurement of real airfares."*
2. **Missing Data in Heatmap:**
   * In `/api/v1/index/routes/heatmap`, missing data points in `matrix[i][j]` are `null`, **never `0`**. (A `0` would render as price collapse). Treat `null` as gray/no-data in your color scales.
3. **Partial Periods on Weekly / Monthly Charts:**
   * On `freq=weekly` or `freq=monthly`, items carry `is_complete: boolean`. Render incomplete periods distinctly (e.g., dotted line or grayed bar) so users don't compare a 14-day month to a 31-day month.
4. **Day-of-Week Adjustment:**
   * `dow_adjusted=true` is **only valid** with `freq=daily`. Sending it with `weekly` or `monthly` returns `422 Unprocessable Entity`.
5. **Uniform Error Envelope:**
   * All 4xx and 5xx responses always follow this shape:
     ```json
     {
       "error": "invalid_request",
       "detail": "freq must be one of ('daily', 'weekly', 'monthly'), got 'hourly'"
     }
     ```

---

## 📊 3. UI View to Endpoint Mapping

| Problem Statement Required View | API Endpoint | Primary Chart Type |
|---|---|---|
| **1. Headline Price Trend** | `GET /api/v1/index` | Multi-frequency Line / Area Chart (`daily`, `weekly`, `monthly`) + DoW toggle |
| **2. Sector-wise Route Heatmap** | `GET /api/v1/index/routes/heatmap` | 2D Matrix Heatmap (Routes × Dates) |
| **3. Lead-time Elasticity Curve** | `GET /api/v1/index/leadtime/curve` | Monotonically decreasing Step / Line Curve (Price vs T+1..T+45) |
| **4. DGCA Validation Overlay** | `GET /api/v1/validation/dgca` | Dual-line comparison series (AIPI vs DGCA) + Correlation KPI cards |
| **Route Filter Dropdowns** | `GET /api/v1/routes` | Dropdown Select options |
| **Single Route Analysis** | `GET /api/v1/index/routes/{route_code}` | Detailed route trend & weights |
| **System Status & Health** | `GET /health` | Header status pills & last updated timer |
| **Methodology Explainer** | `GET /api/v1/methodology` | "About the Index" modal / side-drawer |

---

## 📡 4. Complete Endpoint Reference

### 1. `GET /health`
*Use for topbar status indicator and global demo banner.*

* **Response (200 OK):**
```json
{
  "status": "ok",
  "data_available": true,
  "latest_index_date": "2026-08-14",
  "code_version": "0.1.0",
  "hours_since_latest_index": 288.0,
  "data_mode": {
    "counts": { "real": 0, "synthetic": 21035 },
    "total_rows": 21035,
    "real_share": 0.0,
    "synthetic_share": 1.0,
    "is_demo_data": true,
    "banner": "Contains simulated data — not a measurement of real airfares."
  }
}
```

---

### 2. `GET /api/v1/index`
*The primary headline inflation index.*

* **Query Parameters:**
  * `freq` *(string, optional, default: `"daily"`)*: `"daily"` | `"weekly"` | `"monthly"`
  * `dow_adjusted` *(boolean, optional, default: `false`)*: Day-of-week adjusted (daily only).
  * `from` *(string, optional, format: `YYYY-MM-DD`)*: Inclusive start date.
  * `to` *(string, optional, format: `YYYY-MM-DD`)*: Inclusive end date.

* **Response (200 OK):**
```json
{
  "series": "headline",
  "freq": "daily",
  "dow_adjusted": false,
  "count": 75,
  "base_period": {
    "start": "2026-06-01",
    "end": "2026-06-14",
    "n_days": 14
  },
  "pipeline_run": {
    "run_id": "b3f07a9e12c4d5e6",
    "code_version": "0.1.0",
    "git_sha": "e4aaac4",
    "config_hash": "c73d9e8...",
    "input_row_count": 21035,
    "index_eligible_rows": 19540,
    "created_at": "2026-08-26T14:41:29Z"
  },
  "data_mode": {
    "is_demo_data": true,
    "real_share": 0.0,
    "synthetic_share": 1.0,
    "banner": "Contains simulated data — not a measurement of real airfares."
  },
  "points": [
    {
      "date": "2026-06-01",
      "value": 100.0,
      "n_obs": 280,
      "coverage_pct": 93.3,
      "matched_n": 260
    },
    {
      "date": "2026-06-02",
      "value": 101.42,
      "n_obs": 284,
      "coverage_pct": 94.7,
      "matched_n": 265
    }
  ]
}
```
*Note on weekly/monthly:* Each item in `points` will also include `n_days`, `expected_days`, and `is_complete`.

---

### 3. `GET /api/v1/index/routes/heatmap`
*Sector-wise route matrix for the Heatmap component.*

* **Query Parameters:**
  * `from` *(string, optional, format: `YYYY-MM-DD`)*
  * `to` *(string, optional, format: `YYYY-MM-DD`)*

* **Response (200 OK):**
```json
{
  "routes": ["DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "BLR-HYD", "MAA-DEL"],
  "route_names": ["Delhi – Mumbai", "Delhi – Bengaluru", "Mumbai – Bengaluru", "Delhi – Kolkata", "Bengaluru – Hyderabad", "Chennai – Delhi"],
  "dates": ["2026-06-01", "2026-06-02", "2026-06-03"],
  "matrix": [
    [100.0, 101.2, 99.8],
    [100.0, null, 102.1],
    [100.0, 98.4, 99.1],
    [100.0, 103.5, 104.2],
    [100.0, 100.1, 100.4],
    [100.0, 102.0, 101.8]
  ],
  "value_min": 94.2,
  "value_max": 112.8,
  "baseline": 100.0,
  "note": "matrix[i][j] is index for routes[i] on dates[j]. null = no index.",
  "data_mode": { "is_demo_data": true }
}
```

---

### 4. `GET /api/v1/index/leadtime/curve`
*Lead-time Price Elasticity curve (Relative Fare Level vs Advance Days).*

* **Query Parameters:**
  * `as_of` *(string, optional, format: `YYYY-MM-DD`)*: Defaults to latest available date.

* **Response (200 OK):**
```json
{
  "as_of": "2026-08-14",
  "reference_window": 15,
  "note": "Relative fare LEVEL by advance window (15-day window = 100).",
  "curve": [
    { "advance_days": 1, "relative_level": 162.84 },
    { "advance_days": 7, "relative_level": 112.18 },
    { "advance_days": 15, "relative_level": 100.0 },
    { "advance_days": 30, "relative_level": 94.32 },
    { "advance_days": 45, "relative_level": 90.50 }
  ]
}
```
*Property:* This curve is guaranteed **monotonically decreasing** (booking 1 day out is more expensive than 15 days out, which is more expensive than 45 days out).

---

### 5. `GET /api/v1/validation/dgca`
*DGCA validation metrics and comparison panel.*

* **Response (200 OK):**
```json
{
  "generated_at": "2026-08-26T14:41:29Z",
  "data_mode_breakdown": { "real": 0.0, "synthetic": 1.0, "unknown": 0.0 },
  "reference_is_placeholder": true,
  "caveat": "EVERY figure in this report is computed from SYNTHETIC fares validated against a SYNTHETIC reference.",
  "primary_comparison": "route_month_panel",
  "national_monthly": {
    "n": 1,
    "insufficient_n": true,
    "pearson_r": null,
    "spearman_rho": null,
    "notes": [
      "n = 1 paired observations is below the reporting threshold of 8. Pearson r is not reported."
    ]
  },
  "route_month_panel": {
    "n": 12,
    "insufficient_n": false,
    "pearson_r": 0.0414,
    "spearman_rho": -0.2168,
    "mape_pct": 147.38,
    "directional_accuracy": 0.5833,
    "months": ["2026-07"],
    "routes": ["DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "BLR-HYD", "MAA-DEL"]
  },
  "construct_validity": {
    "leadtime_monotone_decreasing": true,
    "leadtime_spread_pct": 79.94,
    "daily_volatility_pct": 2.37,
    "suspiciously_flat": false
  }
}
```
*UI Advice:* 
* When `insufficient_n === true`, show *"Sample accumulating (needs ≥8 months)"* instead of `null` or `0`.
* Use `route_month_panel` for the KPI cards (Directional Accuracy %, MAPE %, Spearman Rho).

---

### 6. `GET /api/v1/routes`
*Route directory metadata for dropdown selectors.*

* **Response (200 OK):**
```json
{
  "count": 12,
  "routes": [
    {
      "route_code": "DEL-BOM",
      "origin": "DEL",
      "destination": "BOM",
      "display_name": "Delhi – Mumbai",
      "weight": 0.1842,
      "in_index": true
    },
    {
      "route_code": "DEL-BLR",
      "origin": "DEL",
      "destination": "BLR",
      "display_name": "Delhi – Bengaluru",
      "weight": 0.1421,
      "in_index": true
    }
  ]
}
```

---

### 7. `GET /api/v1/index/routes/{route_code}`
*Single route detailed time series.*

* **Example:** `GET /api/v1/index/routes/DEL-BOM`
* **Response (200 OK):**
```json
{
  "route_code": "DEL-BOM",
  "display_name": "Delhi – Mumbai",
  "weight": 0.1842,
  "count": 75,
  "points": [
    { "date": "2026-06-01", "value": 100.0, "n_obs": 42, "coverage_pct": 95.0 },
    { "date": "2026-06-02", "value": 101.8, "n_obs": 44, "coverage_pct": 97.5 }
  ]
}
```
*Note:* Returns `404 Not Found` if route code does not exist.

---

### 8. `GET /api/v1/index/leadtime`
*Inflation index for each advance booking window (T+1, T+7, T+15, T+30, T+45) over time.*

* **Response (200 OK):**
```json
{
  "note": "Index per advance window (base period = 100). Inflation by window, not fare level.",
  "windows": [
    {
      "advance_days": 1,
      "points": [ { "date": "2026-06-01", "value": 100.0, "n_obs": 56, "coverage_pct": 93.3 } ]
    },
    {
      "advance_days": 7,
      "points": [ { "date": "2026-06-01", "value": 100.0, "n_obs": 58, "coverage_pct": 96.6 } ]
    },
    {
      "advance_days": 15,
      "points": [ { "date": "2026-06-01", "value": 100.0, "n_obs": 55, "coverage_pct": 91.6 } ]
    },
    {
      "advance_days": 30,
      "points": [ { "date": "2026-06-01", "value": 100.0, "n_obs": 54, "coverage_pct": 90.0 } ]
    },
    {
      "advance_days": 45,
      "points": [ { "date": "2026-06-01", "value": 100.0, "n_obs": 57, "coverage_pct": 95.0 } ]
    }
  ]
}
```

---

### 9. `GET /api/v1/index/volatility`
*Sampling frequency & volatility analysis (evidence for MoSPI).*

* **Response (200 OK):**
```json
{
  "daily": {
    "mean_daily_return_pct": 0.04,
    "daily_volatility_pct": 2.37,
    "max_single_day_pct": 5.76
  },
  "sampling_error_simulation": {
    "summary": "Sampling 1 day/month introduces 1.65% MAE and reports the wrong direction 27.8% of the time.",
    "curve": [
      { "days_per_month": 1, "mae_pct": 1.649, "p95_error_pct": 3.684, "wrong_direction_pct": 27.8 },
      { "days_per_month": 3, "mae_pct": 0.849, "p95_error_pct": 2.078, "wrong_direction_pct": 11.6 },
      { "days_per_month": 7, "mae_pct": 0.523, "p95_error_pct": 1.258, "wrong_direction_pct": 2.6 },
      { "days_per_month": 15, "mae_pct": 0.286, "p95_error_pct": 0.703, "wrong_direction_pct": 0.0 }
    ],
    "recommended_days": 3
  }
}
```

---

### 10. `GET /api/v1/methodology`
*Index formula specs, Laspeyres weights, and cleaning parameters.*

* **Response (200 OK):**
```json
{
  "index_number": {
    "elementary_aggregate": "Jevons (geometric mean of price RELATIVES) on matched items",
    "multilateral": "GEKS-Jevons on a rolling window with movement splice (no revision)",
    "upper_aggregation": "Laspeyres over base-period EXPENDITURE shares",
    "base_period": "geometric mean of the base window (=100), not a single day"
  },
  "fingerprint": {
    "config_hash": "c73d9e8a...",
    "base_period_days": 14,
    "geks_window_days": 25
  },
  "routes": ["DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "BLR-HYD", "MAA-DEL"]
}
```

---

### 11. `GET /api/v1/pipeline-run`
*Audit & reproducibility stamp for footer/diagnostics.*

* **Response (200 OK):**
```json
{
  "run_id": "b3f07a9e12c4d5e6",
  "code_version": "0.1.0",
  "git_sha": "e4aaac4",
  "config_hash": "c73d9e8...",
  "input_row_count": 21035,
  "index_eligible_rows": 19540,
  "created_at": "2026-08-26T14:41:29Z"
}
```

---

## 🛠️ Need help or have schema questions?
* The backend OpenAPI contract is live at `http://localhost:8000/docs` (Swagger UI).
* Every response in this document is validated against live running backend code.
"""

Path("FRONTEND_API_GUIDE.md").write_text(content.strip(), encoding="utf-8")
Path("docs/FRONTEND_API_GUIDE.md").write_text(content.strip(), encoding="utf-8")
print("FRONTEND_API_GUIDE.md written to root and docs/")
