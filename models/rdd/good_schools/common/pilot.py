from __future__ import annotations

import numpy as np
import pandas as pd

from models.rdd.paths import project_root
from models.rdd.good_schools.common.concordance import (
    build_metric_candidate_rows,
    build_union_nearby_pairs,
    load_resale_gdf,
    load_school_frames,
)
from models.rdd.good_schools.common.contamination import add_metric_specific_contamination, expand_metric_bandwidth_rows


DEFAULT_SELECTED_SCHOOLS = [
    "NORTHLAND PRIMARY SCHOOL",
    "PEI CHUN PUBLIC SCHOOL",
    "CATHOLIC HIGH SCHOOL",
]
DEFAULT_SELECTED_METRIC = "polygon"
DEFAULT_SELECTED_BANDWIDTH_M = 100.0
DEFAULT_SELECTED_MARGINS = ("0_to_1", "1_to_2")


def load_model_controls() -> pd.DataFrame:
    """Load the transaction-level controls merged into selected RDD samples."""

    df = pd.read_csv(
        project_root() / "data" / "processed" / "final_resale_data.csv",
        usecols=[
            "year",
            "town",
            "flat_type",
            "storey_range",
            "floor_area_sqm",
            "flat_model",
            "remaining_lease",
            "resale_price",
            "num_nearby_malls",
            "num_nearby_mrt",
            "num_unique_mrt_lines",
            "num_schools_1_2km_polygon",
            "num_good_schools_1_2km_polygon",
        ],
    ).copy()
    df["transaction_id"] = np.arange(len(df))
    df["log_resale_price"] = np.log(df["resale_price"])
    return df


def build_selected_sample(
    selected_schools: list[str] | tuple[str, ...] | None = None,
    selected_metric: str = DEFAULT_SELECTED_METRIC,
    selected_bandwidth_m: float = DEFAULT_SELECTED_BANDWIDTH_M,
    selected_margins: tuple[str, ...] = DEFAULT_SELECTED_MARGINS,
) -> pd.DataFrame:
    """Build the cleaned focal-school sample for one metric, bandwidth, and margin set."""

    if selected_schools is None:
        selected_schools = DEFAULT_SELECTED_SCHOOLS

    school_gdf, _ = load_school_frames()
    resale_gdf = load_resale_gdf()
    union_pairs = build_union_nearby_pairs(resale_gdf=resale_gdf, school_gdf=school_gdf)
    focal = build_metric_candidate_rows(union_pairs)
    enriched = add_metric_specific_contamination(focal=focal, union_pairs=union_pairs)
    stacked = expand_metric_bandwidth_rows(enriched)

    selected = stacked.loc[
        stacked["metric"].eq(selected_metric)
        & stacked["bandwidth_m"].eq(selected_bandwidth_m)
        & stacked["keep_clean_or_semiclean"]
        & stacked["broad_margin_group"].isin(selected_margins)
        & stacked["focal_school_name"].isin(selected_schools)
    ].copy()

    controls = load_model_controls()
    selected = selected.merge(controls, on="transaction_id", how="left", validate="many_to_one")

    if "year_x" in selected.columns:
        selected["year"] = selected["year_x"]
    elif "year_y" in selected.columns:
        selected["year"] = selected["year_y"]

    selected["Date"] = pd.to_datetime(selected["Date"])
    selected["year_quarter"] = selected["Date"].dt.to_period("Q").astype(str)
    selected["inside_focal"] = selected["inside_focal_metric"].astype(int)
    selected["r_m"] = selected[f"r_{selected_metric}_m"]
    selected["r_km"] = selected["r_m"] / 1000.0
    selected["triangular_weight"] = 1.0 - (np.abs(selected["r_m"].to_numpy(dtype=float)) / selected_bandwidth_m)
    selected["selected_metric"] = selected_metric
    selected["selected_bandwidth_m"] = selected_bandwidth_m
    return selected
