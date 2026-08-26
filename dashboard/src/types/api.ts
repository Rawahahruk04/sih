/**
 * AIPI Backend API Contract Type Definitions
 * 
 * Strict TypeScript types derived directly from backend Pydantic models (aipi/api/schemas.py).
 * Single Source of Truth for all API data models and network envelopes.
 */

export interface ErrorResponse {
  error: string;
  detail: string;
}

export interface PipelineRunModel {
  run_id: string;
  code_version: string;
  git_sha: string;
  config_hash: string;
  input_row_count: number;
  index_eligible_rows: number;
  created_at: string;
}

export interface BasePeriod {
  start: string | null;
  end: string | null;
  n_days: number;
}

export interface IndexPoint {
  date: string;
  value: number;
  n_obs: number;
  coverage_pct: number;
  matched_n?: number | null;
  n_days?: number | null;
  expected_days?: number | null;
  is_complete?: boolean | null;
}

export interface DataModeSummary {
  counts: Record<string, number>;
  total_rows: number;
  real_share: number;
  synthetic_share: number;
  is_demo_data: boolean;
  banner: string | null;
}

export interface HealthResponse {
  status: string;
  data_available: boolean;
  latest_index_date: string | null;
  code_version: string;
  hours_since_latest_index: number | null;
  data_mode?: DataModeSummary | null;
}

export interface HeadlineResponse {
  series: string;
  freq: 'daily' | 'weekly' | 'monthly';
  dow_adjusted: boolean;
  base_period: BasePeriod;
  pipeline_run: PipelineRunModel;
  data_mode: DataModeSummary;
  count: number;
  points: IndexPoint[];
}

export interface RouteMetadata {
  route_code: string;
  origin: string;
  destination: string;
  display_name: string;
  weight: number;
  in_index: boolean;
}

export interface RouteMetadataResponse {
  count: number;
  routes: RouteMetadata[];
}

export interface HeatmapResponse {
  routes: string[];
  route_names: string[];
  dates: string[];
  matrix: (number | null)[][];
  value_min: number | null;
  value_max: number | null;
  baseline: number;
  note: string;
  data_mode: DataModeSummary;
}

export interface RouteSummary {
  route_code: string;
  display_name: string;
  weight: number;
  latest_date: string;
  latest_value: number;
}

export interface RoutesResponse {
  pipeline_run: PipelineRunModel;
  count: number;
  routes: RouteSummary[];
}

export interface RouteResponse {
  route_code: string;
  display_name: string;
  weight: number;
  pipeline_run: PipelineRunModel;
  count: number;
  points: IndexPoint[];
}

export interface LeadtimeWindow {
  advance_days: number;
  points: IndexPoint[];
}

export interface LeadtimeIndexResponse {
  note: string;
  pipeline_run: PipelineRunModel;
  windows: LeadtimeWindow[];
}

export interface LeadtimeCurvePoint {
  advance_days: number;
  relative_level: number;
}

export interface LeadtimeCurveResponse {
  as_of: string | null;
  reference_window: number | null;
  note?: string | null;
  curve: LeadtimeCurvePoint[];
}

export interface ValidationBacktest {
  comparison: string;
  n: number;
  pearson_r: number | null;
  spearman_rho: number | null;
  mape_pct: number | null;
  directional_accuracy: number | null;
  insufficient_n: boolean;
  months?: string[];
  routes?: string[];
  notes?: string[];
}

export interface ValidationResponse {
  generated_at: string;
  data_mode_breakdown: Record<string, number>;
  reference_is_placeholder: boolean;
  caveat: string;
  series: Array<{ period: string; aipi_index: number; dgca_index: number }>;
  pearson_r: number | null;
  mape: number | null;
  directional_accuracy: number | null;
  primary_comparison: string;
  national_monthly: ValidationBacktest;
  route_month_panel: ValidationBacktest;
  construct_validity: Record<string, any>;
  notes: string[];
}

export interface VolatilitySamplingError {
  headline?: string;
  one_day_per_month?: {
    days_per_month: number;
    mae_pct: number;
    rmse_pct: number;
    p95_abs_pct: number;
    max_abs_pct: number;
    direction_error_rate: number;
    n_direction_comparisons: number;
  };
  curve?: Array<{
    days_per_month: number;
    mae_pct: number;
    p95_abs_pct: number;
    direction_error_rate: number;
  }>;
  required_days_for_1pct_mae?: {
    target_mae_pct: number;
    required_days_per_month: number | null;
    achieved: boolean;
    curve?: Array<{ days_per_month: number; mae_pct: number }>;
  };
  available?: boolean;
  reason?: string;
}

export interface VolatilityResponse {
  daily: {
    daily_volatility_pct: number | null;
    max_daily_move_pct: number | null;
    suspiciously_flat: boolean | null;
  };
  intraday: {
    available: boolean;
    offer_days_with_multiple_slots?: number;
    mean_intraday_cv_pct?: number | null;
    p95_intraday_cv_pct?: number | null;
    by_advance_window?: Record<string, number>;
    note?: string;
  };
  sampling_error?: VolatilitySamplingError;
}

export interface MethodologyResponse {
  title: string;
  disclaimer: string;
  index_number: {
    elementary_aggregate: string;
    multilateral: string;
    upper_aggregation: string;
    base_period: string;
    seasonal: string;
  };
  fingerprint: {
    base_period_days: number;
    geks_window_days: number;
    min_matched_items: number;
    min_n_for_trim: number;
    mad_trim_k: number;
    basket: {
      brand_family: string;
      advance_windows: number[];
      routes: string[];
      index_capture_slot_ist: string;
      nonstop_only: boolean;
      exclude_codeshare: boolean;
    };
  };
  base_period: BasePeriod;
  diagnostics: {
    dow_amplitude_pct: number;
    chain_drift: {
      end_gap_pct?: number;
      max_abs_gap_pct?: number;
    };
    composition_bias_pct: number;
  };
  route_weights: Record<string, number>;
  cleaning: {
    rows_in: number;
    rows_quarantined: number;
    quarantine_reasons: Record<string, number>;
    rows_off_capture_slot: number;
    basket_exclusions: Record<string, number>;
    rows_deduplicated: number;
    rows_soldout: number;
    split_imputation: Record<string, number>;
    split_model: Record<string, any>;
    outliers: Record<string, any>;
    outlier_sensitivity: Record<string, any>;
    rows_index_eligible: number;
    retention_pct: number;
    data_mode_breakdown: Record<string, number>;
  };
  notes: string[];
}
