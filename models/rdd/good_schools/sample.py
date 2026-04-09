"""Shared sample builders for the focal good-school specifications."""

from __future__ import annotations

import pandas as pd

from models.rdd.core.features import add_common_bins, add_mrt_access_bucket, add_quadrant, compute_global_cutoffs
from models.rdd.good_schools.common.pilot import build_selected_sample
from models.rdd.paths import good_schools_data_root


REFERENCE_PERIOD_CUTOFF_YEAR = 2022
SUPPORTED_BANDWIDTHS = {25, 100}
SUPPORTED_MARGINS = {"0_to_1", "1_to_2"}


def output_dir(margin: str, bandwidth_m: int) -> pd.io.common.FilePath | object:
    """Return the processed-output folder for one margin and bandwidth."""

    out = good_schools_data_root() / margin / f"{bandwidth_m}m"
    out.mkdir(parents=True, exist_ok=True)
    return out


def load_good_school_names() -> list[str]:
    """Load the list of focal schools flagged as good schools."""

    school_df = pd.read_csv(
        good_schools_data_root() / "school_master_with_good_flags.csv",
        usecols=["school_name", "good_school"],
    )
    good_mask = school_df["good_school"].astype(str).str.lower().eq("true")
    return sorted(school_df.loc[good_mask, "school_name"].tolist())


def validate_config(margin: str, bandwidth_m: int) -> None:
    """Validate the supported margin and bandwidth combinations."""

    if margin not in SUPPORTED_MARGINS:
        raise ValueError(f"Unsupported margin: {margin}")
    if bandwidth_m not in SUPPORTED_BANDWIDTHS:
        raise ValueError(f"Unsupported bandwidth: {bandwidth_m}")


def _base_selected_bandwidth(bandwidth_m: int) -> int:
    """Map the period-aware 25m run back to its 50m selection backbone."""

    return 50 if bandwidth_m == 25 else bandwidth_m


def build_period_aware_selected_sample(margin: str, bandwidth_m: int) -> pd.DataFrame:
    """Build the period-aware estimation sample before adding model controls."""

    validate_config(margin, bandwidth_m)
    schools = load_good_school_names()
    base_bandwidth_m = _base_selected_bandwidth(bandwidth_m)

    xy = build_selected_sample(
        selected_schools=schools,
        selected_metric="xy",
        selected_bandwidth_m=base_bandwidth_m,
        selected_margins=(margin,),
    ).copy()
    xy = xy.loc[xy["year"].lt(REFERENCE_PERIOD_CUTOFF_YEAR)].copy()
    xy["metric_rule"] = "xy_before_2022"

    polygon = build_selected_sample(
        selected_schools=schools,
        selected_metric="polygon",
        selected_bandwidth_m=base_bandwidth_m,
        selected_margins=(margin,),
    ).copy()
    polygon = polygon.loc[polygon["year"].ge(REFERENCE_PERIOD_CUTOFF_YEAR)].copy()
    polygon["metric_rule"] = "polygon_from_2022"

    combined = pd.concat([xy, polygon], ignore_index=True)
    if bandwidth_m == 25:
        combined = combined.loc[combined["r_m"].abs().le(bandwidth_m + 1e-9)].copy()
        combined["triangular_weight"] = 1.0 - (
            combined["r_m"].abs().to_numpy(dtype=float) / float(bandwidth_m)
        )
    combined["selected_bandwidth_m"] = bandwidth_m
    combined["final_sample_spec"] = "period_aware_controls_only"
    return combined


def build_period_aware_controls_sample(margin: str, bandwidth_m: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the final controls-ready sample and the cutoffs audit table."""

    selected = build_period_aware_selected_sample(margin, bandwidth_m)
    cutoffs, cutoffs_df = compute_global_cutoffs(selected)
    controls = add_mrt_access_bucket(add_common_bins(add_quadrant(selected), cutoffs)).copy()
    controls["sample_spec"] = "final_pooled_period_aware"
    return controls, cutoffs_df
