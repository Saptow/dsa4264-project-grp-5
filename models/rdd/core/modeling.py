"""Shared modeling helpers used across the RDD specifications."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from models.rdd.core.features import (
    AMENITY_CONTROLS,
    CATEGORICAL_CONTROLS,
    CONTINUOUS_CONTROLS,
    COARSE_HOUSING_CONTROLS,
    available_categorical_levels,
)


MIN_TOTAL_OBS = 50
MIN_SIDE_OBS = 20

DEFAULT_NUMERIC_BALANCE_COLS = [
    "year",
    "floor_area_sqm",
    "remaining_lease",
    "num_nearby_malls",
    "num_nearby_mrt",
    "num_unique_mrt_lines",
]
DEFAULT_CATEGORICAL_BALANCE_COLS = [
    "quadrant",
    "flat_type",
    "storey_range",
    "flat_model",
    "year_quarter",
    "floor_area_global_tercile",
    "remaining_lease_tercile",
]


def stars(p: float) -> str:
    """Return significance stars for a p-value."""

    if pd.isna(p):
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return ""


def get_included_controls(
    df: pd.DataFrame,
    *,
    include_quadrant_control: bool,
    exclude_categoricals: list[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Keep only controls that vary in the current estimation sample."""

    included_continuous: list[str] = []
    included_categorical: list[str] = []
    dropped: list[str] = []
    exclude_set = set(exclude_categoricals or [])

    for col in CONTINUOUS_CONTROLS:
        nonmissing = pd.to_numeric(df[col], errors="coerce").dropna()
        if nonmissing.nunique() <= 1:
            dropped.append(f"{col}:constant")
            continue
        included_continuous.append(col)

    categorical_candidates = list(CATEGORICAL_CONTROLS) + list(AMENITY_CONTROLS) + list(COARSE_HOUSING_CONTROLS)
    if include_quadrant_control:
        categorical_candidates = ["quadrant"] + categorical_candidates

    for col in categorical_candidates:
        if col in exclude_set:
            dropped.append(f"{col}:excluded_by_design")
            continue
        if available_categorical_levels(df[col]) <= 1:
            dropped.append(f"{col}:constant")
            continue
        included_categorical.append(col)

    return included_continuous, included_categorical, dropped


def build_school_formula(
    df: pd.DataFrame,
    *,
    include_quadrant_control: bool,
    exclude_categoricals: list[str] | None = None,
) -> tuple[str, list[str], list[str], list[str]]:
    """Build the school-level RDD formula for a single focal school sample."""

    included_continuous, included_categorical, dropped = get_included_controls(
        df,
        include_quadrant_control=include_quadrant_control,
        exclude_categoricals=exclude_categoricals,
    )
    formula_parts = ["log_resale_price ~ inside_focal", "r_km", "inside_focal:r_km"]
    formula_parts.extend(included_continuous)
    formula_parts.extend([f"C({col})" for col in included_categorical])
    return " + ".join(formula_parts), included_continuous, included_categorical, dropped


def build_pooled_formula(
    df: pd.DataFrame,
    *,
    continuous_controls: list[str] | None = None,
    categorical_controls: list[str] | None = None,
    exclude_categoricals: list[str] | None = None,
) -> tuple[str, list[str], list[str], list[str]]:
    """Build the pooled RDD formula with school-specific slope adjustments."""

    included_continuous, included_categorical, dropped = get_included_controls(
        df,
        include_quadrant_control=False,
        exclude_categoricals=exclude_categoricals,
    )
    if continuous_controls is not None:
        included_continuous = [col for col in included_continuous if col in continuous_controls]
    if categorical_controls is not None:
        included_categorical = [col for col in included_categorical if col in categorical_controls]

    formula_parts = [
        "log_resale_price ~ inside_focal",
        "r_km",
        "inside_focal:r_km",
        "C(focal_school_name):r_km",
        "C(focal_school_name):inside_focal:r_km",
        "C(school_quadrant)",
    ]
    formula_parts.extend(included_continuous)
    formula_parts.extend([f"C({col})" for col in included_categorical])
    return " + ".join(formula_parts), included_continuous, included_categorical, dropped


def fit_one(df: pd.DataFrame, formula: str) -> dict[str, object]:
    """Estimate one weighted RDD regression and return a flat results record."""

    n_obs = int(len(df))
    n_inside = int(df["inside_focal"].eq(1).sum())
    n_outside = int(df["inside_focal"].eq(0).sum())
    result: dict[str, object] = {
        "n_obs": n_obs,
        "n_inside": n_inside,
        "n_outside": n_outside,
        "tau_hat": np.nan,
        "tau_se": np.nan,
        "tau_pvalue": np.nan,
        "tau_ci_low": np.nan,
        "tau_ci_high": np.nan,
        "tau_pct_approx": np.nan,
        "r_squared": np.nan,
        "status": "not_run",
    }
    if n_obs < MIN_TOTAL_OBS or n_inside < MIN_SIDE_OBS or n_outside < MIN_SIDE_OBS:
        result["status"] = "insufficient_sample"
        return result

    try:
        fitted = smf.wls(
            formula=formula,
            data=df,
            weights=df["triangular_weight"],
        ).fit(cov_type="HC1")
        ci = fitted.conf_int().loc["inside_focal"]
        tau_hat = float(fitted.params["inside_focal"])
        result.update(
            {
                "status": "ok",
                "tau_hat": tau_hat,
                "tau_se": float(fitted.bse["inside_focal"]),
                "tau_pvalue": float(fitted.pvalues["inside_focal"]),
                "tau_ci_low": float(ci.iloc[0]),
                "tau_ci_high": float(ci.iloc[1]),
                "tau_pct_approx": float((np.exp(tau_hat) - 1.0) * 100.0),
                "r_squared": float(fitted.rsquared),
            }
        )
    except Exception as exc:  # pragma: no cover
        result["status"] = f"fit_failed: {exc}"
    return result


def finalize_results(df: pd.DataFrame) -> pd.DataFrame:
    """Add common estimability and significance flags to an output table."""

    out = df.copy()
    out["is_estimable"] = out["status"].eq("ok")
    out["significant_10pct"] = out["tau_pvalue"].lt(0.10).fillna(False)
    out["significant_5pct"] = out["tau_pvalue"].lt(0.05).fillna(False)
    out["significant_1pct"] = out["tau_pvalue"].lt(0.01).fillna(False)
    return out


def standardized_mean_diff(group: pd.DataFrame, col: str) -> dict[str, float]:
    """Compute inside-versus-outside balance metrics for one numeric column."""

    inside = pd.to_numeric(group.loc[group["inside_focal"].eq(1), col], errors="coerce").dropna()
    outside = pd.to_numeric(group.loc[group["inside_focal"].eq(0), col], errors="coerce").dropna()
    mean_inside = float(inside.mean()) if len(inside) else np.nan
    mean_outside = float(outside.mean()) if len(outside) else np.nan
    var_inside = float(inside.var(ddof=1)) if len(inside) > 1 else 0.0
    var_outside = float(outside.var(ddof=1)) if len(outside) > 1 else 0.0
    pooled_sd = float(np.sqrt((var_inside + var_outside) / 2.0))
    diff = mean_inside - mean_outside if pd.notna(mean_inside) and pd.notna(mean_outside) else np.nan
    if pd.isna(diff):
        smd = np.nan
    elif pooled_sd <= 0:
        smd = 0.0 if abs(diff) < 1e-12 else np.nan
    else:
        smd = diff / pooled_sd
    return {
        f"mean_inside_{col}": mean_inside,
        f"mean_outside_{col}": mean_outside,
        f"smd_{col}": smd,
    }


def categorical_tvd(group: pd.DataFrame, col: str) -> dict[str, float]:
    """Compute total variation distance for one categorical balance column."""

    inside = group.loc[group["inside_focal"].eq(1), col].fillna("__MISSING__").astype(str)
    outside = group.loc[group["inside_focal"].eq(0), col].fillna("__MISSING__").astype(str)
    p_inside = inside.value_counts(normalize=True, dropna=False)
    p_outside = outside.value_counts(normalize=True, dropna=False)
    labels = p_inside.index.union(p_outside.index)
    tvd = 0.5 * (p_inside.reindex(labels, fill_value=0.0) - p_outside.reindex(labels, fill_value=0.0)).abs().sum()
    return {f"tvd_{col}": float(tvd)}


def build_balance_row(
    group: pd.DataFrame,
    *,
    numeric_cols: list[str] | None = None,
    categorical_cols: list[str] | None = None,
) -> dict[str, object]:
    """Summarize numeric and categorical balance diagnostics for one sample."""

    numeric_cols = numeric_cols or list(DEFAULT_NUMERIC_BALANCE_COLS)
    categorical_cols = categorical_cols or list(DEFAULT_CATEGORICAL_BALANCE_COLS)
    row: dict[str, object] = {}

    for col in numeric_cols:
        if pd.to_numeric(group[col], errors="coerce").dropna().empty:
            continue
        row.update(standardized_mean_diff(group, col))

    for col in categorical_cols:
        if group[col].dropna().empty:
            continue
        row.update(categorical_tvd(group, col))

    smd_cols = [col for col in row if col.startswith("smd_")]
    tvd_cols = [col for col in row if col.startswith("tvd_")]
    row["max_abs_smd_numeric"] = float(
        pd.Series([row.get(col) for col in smd_cols], dtype="float64").abs().max(skipna=True)
    )
    row["max_tvd_categorical"] = float(
        pd.Series([row.get(col) for col in tvd_cols], dtype="float64").max(skipna=True)
    )
    return row
