from __future__ import annotations

import numpy as np
import pandas as pd


QUADRANTS = ["NE", "NW", "SE", "SW"]

CONTINUOUS_CONTROLS = ["floor_area_sqm", "remaining_lease"]
CATEGORICAL_CONTROLS = ["flat_type", "storey_range", "flat_model", "year_quarter"]
AMENITY_CONTROLS = ["num_nearby_malls", "num_nearby_mrt", "num_unique_mrt_lines"]
COARSE_HOUSING_CONTROLS = ["floor_area_global_tercile", "remaining_lease_tercile"]


def assign_quadrant(dx: pd.Series, dy: pd.Series) -> pd.Series:
    """Label each property's relative position around the focal school."""

    labels = np.where(
        dx >= 0,
        np.where(dy >= 0, "NE", "SE"),
        np.where(dy >= 0, "NW", "SW"),
    )
    return pd.Series(labels, index=dx.index, dtype="object")


def compute_global_cutoffs(reference_df: pd.DataFrame) -> tuple[dict[str, float], pd.DataFrame]:
    """Compute tercile cutoffs used to coarsen housing controls."""

    floor_q1 = float(reference_df["floor_area_sqm"].quantile(1 / 3))
    floor_q2 = float(reference_df["floor_area_sqm"].quantile(2 / 3))
    lease_q1 = float(reference_df["remaining_lease"].quantile(1 / 3))
    lease_q2 = float(reference_df["remaining_lease"].quantile(2 / 3))
    cutoffs = {
        "floor_q1": floor_q1,
        "floor_q2": floor_q2,
        "lease_q1": lease_q1,
        "lease_q2": lease_q2,
    }
    cutoffs_df = pd.DataFrame(
        [
            {"coarsened_variable": "floor_area_global_tercile", "q33": floor_q1, "q67": floor_q2},
            {"coarsened_variable": "remaining_lease_tercile", "q33": lease_q1, "q67": lease_q2},
        ]
    )
    return cutoffs, cutoffs_df


def assign_tercile(series: pd.Series, q1: float, q2: float) -> pd.Series:
    """Map a numeric series into small, medium, and large tercile bins."""

    labels = np.where(series <= q1, "small", np.where(series <= q2, "medium", "large"))
    return pd.Series(labels, index=series.index, dtype="object")


def add_common_bins(df: pd.DataFrame, cutoffs: dict[str, float]) -> pd.DataFrame:
    """Attach shared coarsened housing bins to an RDD sample."""

    out = df.copy()
    out["floor_area_global_tercile"] = assign_tercile(
        out["floor_area_sqm"],
        cutoffs["floor_q1"],
        cutoffs["floor_q2"],
    )
    out["remaining_lease_tercile"] = assign_tercile(
        out["remaining_lease"],
        cutoffs["lease_q1"],
        cutoffs["lease_q2"],
    )
    return out


def add_quadrant(sample: pd.DataFrame) -> pd.DataFrame:
    """Add school-centered quadrant labels using property and school coordinates."""

    out = sample.copy()
    out["property_x"] = out["property_geom"].map(lambda geom: geom.x)
    out["property_y"] = out["property_geom"].map(lambda geom: geom.y)
    out["school_x"] = out["point_geom"].map(lambda geom: geom.x)
    out["school_y"] = out["point_geom"].map(lambda geom: geom.y)
    out["dx_from_school_m"] = out["property_x"] - out["school_x"]
    out["dy_from_school_m"] = out["property_y"] - out["school_y"]
    out["quadrant"] = assign_quadrant(out["dx_from_school_m"], out["dy_from_school_m"])
    out["school_quadrant"] = out["focal_school_name"] + " | " + out["quadrant"].astype(str)
    return out


def add_mrt_access_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """Bucket MRT access into coarse categories used by some specifications."""

    out = df.copy()
    mrt_count = pd.to_numeric(out["num_nearby_mrt"], errors="coerce")
    labels = np.where(mrt_count <= 0, "0_mrt", np.where(mrt_count == 1, "1_mrt", "2plus_mrt"))
    out["mrt_access_bucket"] = pd.Series(labels, index=out.index, dtype="object")
    return out


def available_categorical_levels(series: pd.Series) -> int:
    """Count the observed non-missing levels in a categorical control."""

    return int(series.dropna().nunique())
