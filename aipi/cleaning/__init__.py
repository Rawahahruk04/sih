"""Cleaning pipeline: raw quotes to index-eligible fares."""

from aipi.cleaning.contract import RULES, basket_filter, coerce_types, map_brand_family, validate
from aipi.cleaning.decomposition import apply_fare_split, calibrate_fare_split
from aipi.cleaning.outliers import flag_outliers_iqr, flag_outliers_log_mad, sensitivity_report
from aipi.cleaning.pipeline import DEDUP_KEY, CleaningReport, CleanResult, clean

__all__ = [
    "DEDUP_KEY",
    "RULES",
    "CleanResult",
    "CleaningReport",
    "apply_fare_split",
    "basket_filter",
    "calibrate_fare_split",
    "clean",
    "coerce_types",
    "flag_outliers_iqr",
    "flag_outliers_log_mad",
    "map_brand_family",
    "sensitivity_report",
    "validate",
]
