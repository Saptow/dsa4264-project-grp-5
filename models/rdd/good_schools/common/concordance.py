from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from models.rdd.paths import project_root


LOCAL_CRS = "EPSG:3414"
SOURCE_CRS = "EPSG:4326"
ONE_KM_M = 1000.0
MAX_BANDWIDTH_M = 150.0
BUFFER_LIMIT_M = ONE_KM_M + MAX_BANDWIDTH_M
DISTANCE_TOLERANCE_M = 1e-9
GOOD_SCHOOL_NAME_OVERRIDES = {
    "NAN HUA PRIMARY SCHOO": "NAN HUA PRIMARY SCHOOL",
}
BANDWIDTHS_M = (50, 100, 150)


def normalise_school_name(name: str) -> str:
    """Standardize school names before concordance matching."""

    return " ".join(str(name).upper().split())


def load_school_frames() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Load school boundary geometries and audit basic coverage metadata."""

    root = project_root()
    school_master = pd.read_csv(root / "data" / "processed" / "schools" / "final_primary_schools.csv")
    school_boundary_gdf = gpd.read_file(
        root / "data" / "processed" / "schools" / "final_primary_schools_with_school_boundaries.geojson"
    ).to_crs(LOCAL_CRS)

    good_raw = pd.read_csv(root / "data" / "processed" / "schools" / "school_admissions_no_gep_sap.csv")
    school_lookup = {
        normalise_school_name(name): name
        for name in school_master["school_name"].dropna()
    }

    good_school_names: set[str] = set()
    mapping_rows: list[dict[str, object]] = []
    for raw_name in good_raw["School"].dropna():
        overridden_name = GOOD_SCHOOL_NAME_OVERRIDES.get(raw_name, raw_name)
        matched_name = school_lookup.get(normalise_school_name(overridden_name))
        mapping_rows.append(
            {
                "raw_good_school_name": raw_name,
                "overridden_good_school_name": overridden_name,
                "matched_school_name": matched_name,
                "match_status": "matched" if matched_name else "unmatched",
            }
        )
        if matched_name:
            good_school_names.add(matched_name)

    mapping_df = pd.DataFrame(mapping_rows)
    unmatched = mapping_df.loc[mapping_df["match_status"] != "matched"]
    if not unmatched.empty:
        raise ValueError(
            "Unmatched good schools in concordance audit: "
            f"{unmatched['raw_good_school_name'].tolist()}"
        )

    school_boundary_gdf["start_year"] = pd.to_numeric(school_boundary_gdf["start_year"], errors="coerce").astype(int)
    school_boundary_gdf["end_year"] = pd.to_numeric(school_boundary_gdf["end_year"], errors="coerce").astype(int)
    school_boundary_gdf["good_school"] = school_boundary_gdf["school_name"].isin(good_school_names)
    school_boundary_gdf["point_geom"] = gpd.points_from_xy(school_boundary_gdf["X"], school_boundary_gdf["Y"], crs=LOCAL_CRS)
    school_boundary_gdf["polygon_geom"] = school_boundary_gdf.geometry

    missing_in_boundary = sorted(set(school_master["school_name"]) - set(school_boundary_gdf["school_name"]))
    boundary_metadata = pd.DataFrame(
        {
            "metric": [
                "schools_in_master",
                "schools_in_boundary_geojson",
                "schools_missing_polygon_boundary",
                "good_schools_in_boundary_geojson",
            ],
            "value": [
                len(school_master),
                len(school_boundary_gdf),
                len(missing_in_boundary),
                int(school_boundary_gdf["good_school"].sum()),
            ],
        }
    )
    return school_boundary_gdf, boundary_metadata


def load_resale_gdf() -> gpd.GeoDataFrame:
    """Load resale transactions as a projected GeoDataFrame."""

    root = project_root()
    resale_df = pd.read_csv(
        root / "data" / "processed" / "final_resale_data.csv",
        usecols=["year", "Date", "town", "address", "latitude", "longitude"],
    )
    resale_df = resale_df.copy()
    resale_df["transaction_id"] = np.arange(len(resale_df))
    resale_df["year"] = pd.to_numeric(resale_df["year"], errors="coerce").astype(int)
    return gpd.GeoDataFrame(
        resale_df,
        geometry=gpd.points_from_xy(resale_df["longitude"], resale_df["latitude"]),
        crs=SOURCE_CRS,
    ).to_crs(LOCAL_CRS)


def build_union_nearby_pairs(resale_gdf: gpd.GeoDataFrame, school_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Create the transaction-school candidate table within the search buffer."""

    resale_points = resale_gdf[["transaction_id", "year", "Date", "town", "address", "geometry"]].copy()

    point_buffer_gdf = gpd.GeoDataFrame(
        school_gdf[["school_name"]].copy(),
        geometry=gpd.GeoSeries(school_gdf["point_geom"], crs=LOCAL_CRS).buffer(BUFFER_LIMIT_M),
        crs=LOCAL_CRS,
    )
    polygon_buffer_gdf = gpd.GeoDataFrame(
        school_gdf[["school_name"]].copy(),
        geometry=gpd.GeoSeries(school_gdf["polygon_geom"], crs=LOCAL_CRS).buffer(BUFFER_LIMIT_M),
        crs=LOCAL_CRS,
    )

    point_hits = gpd.sjoin(resale_points, point_buffer_gdf, how="inner", predicate="within")[["transaction_id", "school_name"]].drop_duplicates()
    point_hits["point_buffer_hit"] = True

    polygon_hits = gpd.sjoin(resale_points, polygon_buffer_gdf, how="inner", predicate="within")[["transaction_id", "school_name"]].drop_duplicates()
    polygon_hits["polygon_buffer_hit"] = True

    union_pairs = point_hits.merge(polygon_hits, on=["transaction_id", "school_name"], how="outer").fillna(False)
    property_cols = resale_points.rename(columns={"geometry": "property_geom"})
    school_cols = school_gdf[
        ["school_name", "good_school", "start_year", "end_year", "point_geom", "polygon_geom"]
    ].copy()

    union_pairs = union_pairs.merge(property_cols, on="transaction_id", how="left")
    union_pairs = union_pairs.merge(school_cols, on="school_name", how="left")
    union_pairs = union_pairs[
        (union_pairs["year"] >= union_pairs["start_year"])
        & (union_pairs["year"] <= union_pairs["end_year"])
    ].copy()

    property_geoms = gpd.GeoSeries(union_pairs["property_geom"].array, index=union_pairs.index, crs=LOCAL_CRS)
    point_geoms = gpd.GeoSeries(union_pairs["point_geom"].array, index=union_pairs.index, crs=LOCAL_CRS)
    polygon_geoms = gpd.GeoSeries(union_pairs["polygon_geom"].array, index=union_pairs.index, crs=LOCAL_CRS)

    union_pairs["dist_xy_m"] = property_geoms.distance(point_geoms)
    union_pairs["dist_polygon_m"] = property_geoms.distance(polygon_geoms)
    union_pairs["inside_xy"] = (
        (union_pairs["dist_xy_m"] > 0)
        & (union_pairs["dist_xy_m"] <= ONE_KM_M + DISTANCE_TOLERANCE_M)
    ).astype(int)
    union_pairs["inside_polygon"] = (
        (union_pairs["dist_polygon_m"] > 0)
        & (union_pairs["dist_polygon_m"] <= ONE_KM_M + DISTANCE_TOLERANCE_M)
    ).astype(int)
    return union_pairs


def make_transition_labels(
    outside_good: pd.Series,
    outside_normal: pd.Series,
    inside_good: pd.Series,
    inside_normal: pd.Series,
) -> pd.Series:
    """Format outside-to-inside school-count transitions as readable labels."""

    return (
        "("
        + outside_good.astype(int).astype(str)
        + ","
        + outside_normal.astype(int).astype(str)
        + ")->("
        + inside_good.astype(int).astype(str)
        + ","
        + inside_normal.astype(int).astype(str)
        + ")"
    )


def classify_labels(
    baseline_clean: pd.Series,
    clean_other: pd.Series,
    ambiguous_good: pd.Series,
    ambiguous_normal: pd.Series,
) -> pd.Series:
    """Summarize each candidate row's contamination status into one label."""

    out = pd.Series("unclassified", index=baseline_clean.index, dtype=object)
    out.loc[baseline_clean] = "clean_baseline_0_0_to_1_0"
    out.loc[clean_other] = "clean_other_good_margin"
    out.loc[(ambiguous_good > 0) & (ambiguous_normal == 0)] = "contaminated_other_good_boundary"
    out.loc[(ambiguous_good == 0) & (ambiguous_normal > 0)] = "contaminated_normal_boundary"
    out.loc[(ambiguous_good > 0) & (ambiguous_normal > 0)] = "contaminated_good_and_normal_boundary"
    return out


def build_metric_candidate_rows(union_pairs: pd.DataFrame) -> pd.DataFrame:
    """Construct focal-school candidate rows with xy and polygon metrics side by side."""

    point_good_counts = (
        union_pairs.loc[union_pairs["inside_xy"].eq(1) & union_pairs["good_school"]]
        .groupby("transaction_id")
        .size()
    )
    point_normal_counts = (
        union_pairs.loc[union_pairs["inside_xy"].eq(1) & (~union_pairs["good_school"])]
        .groupby("transaction_id")
        .size()
    )
    polygon_good_counts = (
        union_pairs.loc[union_pairs["inside_polygon"].eq(1) & union_pairs["good_school"]]
        .groupby("transaction_id")
        .size()
    )
    polygon_normal_counts = (
        union_pairs.loc[union_pairs["inside_polygon"].eq(1) & (~union_pairs["good_school"])]
        .groupby("transaction_id")
        .size()
    )

    focal = union_pairs.loc[
        union_pairs["good_school"]
        & (
            union_pairs["dist_xy_m"].sub(ONE_KM_M).abs().le(MAX_BANDWIDTH_M + DISTANCE_TOLERANCE_M)
            | union_pairs["dist_polygon_m"].sub(ONE_KM_M).abs().le(MAX_BANDWIDTH_M + DISTANCE_TOLERANCE_M)
        )
    ].copy()
    focal = focal.rename(
        columns={
            "school_name": "focal_school_name",
            "good_school": "focal_good_school",
            "dist_xy_m": "focal_dist_xy_m",
            "dist_polygon_m": "focal_dist_polygon_m",
            "inside_xy": "inside_focal_xy",
            "inside_polygon": "inside_focal_polygon",
        }
    )
    focal["candidate_id"] = np.arange(len(focal))
    for bandwidth in BANDWIDTHS_M:
        focal[f"xy_in_bw_{bandwidth}m"] = focal["focal_dist_xy_m"].sub(ONE_KM_M).abs().le(bandwidth + DISTANCE_TOLERANCE_M)
        focal[f"polygon_in_bw_{bandwidth}m"] = focal["focal_dist_polygon_m"].sub(ONE_KM_M).abs().le(bandwidth + DISTANCE_TOLERANCE_M)

    focal["observed_good_count_xy"] = focal["transaction_id"].map(point_good_counts).fillna(0).astype(int)
    focal["observed_normal_count_xy"] = focal["transaction_id"].map(point_normal_counts).fillna(0).astype(int)
    focal["observed_good_count_polygon"] = focal["transaction_id"].map(polygon_good_counts).fillna(0).astype(int)
    focal["observed_normal_count_polygon"] = focal["transaction_id"].map(polygon_normal_counts).fillna(0).astype(int)
    focal["r_xy_m"] = focal["focal_dist_xy_m"] - ONE_KM_M
    focal["r_polygon_m"] = focal["focal_dist_polygon_m"] - ONE_KM_M

    focal["outside_good_count_xy"] = focal["observed_good_count_xy"] - focal["inside_focal_xy"]
    focal["outside_normal_count_xy"] = focal["observed_normal_count_xy"]
    focal["inside_good_count_xy"] = focal["observed_good_count_xy"] + (1 - focal["inside_focal_xy"])
    focal["inside_normal_count_xy"] = focal["observed_normal_count_xy"]

    focal["outside_good_count_polygon"] = focal["observed_good_count_polygon"] - focal["inside_focal_polygon"]
    focal["outside_normal_count_polygon"] = focal["observed_normal_count_polygon"]
    focal["inside_good_count_polygon"] = focal["observed_good_count_polygon"] + (1 - focal["inside_focal_polygon"])
    focal["inside_normal_count_polygon"] = focal["observed_normal_count_polygon"]

    other_pairs = focal[
        ["candidate_id", "transaction_id", "focal_school_name", "r_xy_m", "r_polygon_m"]
    ].merge(
        union_pairs[["transaction_id", "school_name", "good_school", "dist_xy_m", "dist_polygon_m"]],
        on="transaction_id",
        how="left",
    )
    other_pairs = other_pairs.loc[other_pairs["school_name"] != other_pairs["focal_school_name"]].copy()
    other_pairs["xy_ambiguous"] = (
        other_pairs["dist_xy_m"].sub(ONE_KM_M).abs() <= other_pairs["r_xy_m"].abs() + DISTANCE_TOLERANCE_M
    )
    other_pairs["polygon_ambiguous"] = (
        other_pairs["dist_polygon_m"].sub(ONE_KM_M).abs() <= other_pairs["r_polygon_m"].abs() + DISTANCE_TOLERANCE_M
    )

    xy_amb_good = other_pairs.loc[other_pairs["xy_ambiguous"] & other_pairs["good_school"]].groupby("candidate_id").size()
    xy_amb_normal = other_pairs.loc[other_pairs["xy_ambiguous"] & (~other_pairs["good_school"])].groupby("candidate_id").size()
    polygon_amb_good = other_pairs.loc[other_pairs["polygon_ambiguous"] & other_pairs["good_school"]].groupby("candidate_id").size()
    polygon_amb_normal = other_pairs.loc[other_pairs["polygon_ambiguous"] & (~other_pairs["good_school"])].groupby("candidate_id").size()

    focal["ambiguous_good_count_xy"] = focal["candidate_id"].map(xy_amb_good).fillna(0).astype(int)
    focal["ambiguous_normal_count_xy"] = focal["candidate_id"].map(xy_amb_normal).fillna(0).astype(int)
    focal["ambiguous_good_count_polygon"] = focal["candidate_id"].map(polygon_amb_good).fillna(0).astype(int)
    focal["ambiguous_normal_count_polygon"] = focal["candidate_id"].map(polygon_amb_normal).fillna(0).astype(int)

    focal["stable_other_status_xy"] = focal["ambiguous_good_count_xy"].eq(0) & focal["ambiguous_normal_count_xy"].eq(0)
    focal["stable_other_status_polygon"] = focal["ambiguous_good_count_polygon"].eq(0) & focal["ambiguous_normal_count_polygon"].eq(0)

    focal["transition_label_xy"] = make_transition_labels(
        focal["outside_good_count_xy"],
        focal["outside_normal_count_xy"],
        focal["inside_good_count_xy"],
        focal["inside_normal_count_xy"],
    )
    focal["transition_label_polygon"] = make_transition_labels(
        focal["outside_good_count_polygon"],
        focal["outside_normal_count_polygon"],
        focal["inside_good_count_polygon"],
        focal["inside_normal_count_polygon"],
    )

    focal["baseline_clean_xy"] = (
        focal["stable_other_status_xy"]
        & focal["outside_good_count_xy"].eq(0)
        & focal["outside_normal_count_xy"].eq(0)
        & focal["inside_good_count_xy"].eq(1)
        & focal["inside_normal_count_xy"].eq(0)
    )
    focal["baseline_clean_polygon"] = (
        focal["stable_other_status_polygon"]
        & focal["outside_good_count_polygon"].eq(0)
        & focal["outside_normal_count_polygon"].eq(0)
        & focal["inside_good_count_polygon"].eq(1)
        & focal["inside_normal_count_polygon"].eq(0)
    )
    focal["clean_other_xy"] = focal["stable_other_status_xy"] & (~focal["baseline_clean_xy"])
    focal["clean_other_polygon"] = focal["stable_other_status_polygon"] & (~focal["baseline_clean_polygon"])

    focal["classification_xy"] = classify_labels(
        focal["baseline_clean_xy"],
        focal["clean_other_xy"],
        focal["ambiguous_good_count_xy"],
        focal["ambiguous_normal_count_xy"],
    )
    focal["classification_polygon"] = classify_labels(
        focal["baseline_clean_polygon"],
        focal["clean_other_polygon"],
        focal["ambiguous_good_count_polygon"],
        focal["ambiguous_normal_count_polygon"],
    )
    focal["inside_same"] = focal["inside_focal_xy"] == focal["inside_focal_polygon"]
    focal["transition_same"] = focal["transition_label_xy"] == focal["transition_label_polygon"]
    focal["classification_same"] = focal["classification_xy"] == focal["classification_polygon"]
    return focal
