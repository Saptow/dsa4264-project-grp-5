from __future__ import annotations

import pandas as pd

from models.rdd.good_schools.common.concordance import BANDWIDTHS_M, DISTANCE_TOLERANCE_M, ONE_KM_M


def margin_group(outside_good: pd.Series, inside_good: pd.Series) -> pd.Series:
    """Collapse school-count changes into the broad good-school margin label."""

    out = pd.Series("unexpected_margin", index=outside_good.index, dtype=object)
    valid_increment = inside_good.eq(outside_good + 1)
    out.loc[valid_increment & outside_good.eq(0)] = "0_to_1"
    out.loc[valid_increment & outside_good.eq(1)] = "1_to_2"
    out.loc[valid_increment & outside_good.ge(2)] = "2plus_to_next"
    return out


def classify_contamination_tier(
    ambiguous_good_inside: pd.Series,
    ambiguous_normal_inside: pd.Series,
    ambiguous_good_outside: pd.Series,
    ambiguous_normal_outside: pd.Series,
) -> pd.Series:
    """Classify candidates into clean, semi-clean, or hard-contaminated tiers."""

    ambiguous_inside_total = ambiguous_good_inside + ambiguous_normal_inside
    ambiguous_outside_total = ambiguous_good_outside + ambiguous_normal_outside

    out = pd.Series("unclassified", index=ambiguous_inside_total.index, dtype=object)
    out.loc[(ambiguous_inside_total == 0) & (ambiguous_outside_total == 0)] = "clean"
    out.loc[(ambiguous_inside_total == 0) & (ambiguous_outside_total > 0)] = "semi_clean_soft"
    out.loc[ambiguous_inside_total > 0] = "hard_contaminated"
    return out


def classify_contamination_detail(
    ambiguous_good_inside: pd.Series,
    ambiguous_normal_inside: pd.Series,
    ambiguous_good_outside: pd.Series,
    ambiguous_normal_outside: pd.Series,
) -> pd.Series:
    """Add a more specific contamination label for diagnostic output."""

    out = pd.Series("unclassified", index=ambiguous_good_inside.index, dtype=object)

    clean_mask = (
        ambiguous_good_inside.eq(0)
        & ambiguous_normal_inside.eq(0)
        & ambiguous_good_outside.eq(0)
        & ambiguous_normal_outside.eq(0)
    )
    soft_good = (
        ambiguous_good_inside.eq(0)
        & ambiguous_normal_inside.eq(0)
        & ambiguous_good_outside.gt(0)
        & ambiguous_normal_outside.eq(0)
    )
    soft_normal = (
        ambiguous_good_inside.eq(0)
        & ambiguous_normal_inside.eq(0)
        & ambiguous_good_outside.eq(0)
        & ambiguous_normal_outside.gt(0)
    )
    soft_both = (
        ambiguous_good_inside.eq(0)
        & ambiguous_normal_inside.eq(0)
        & ambiguous_good_outside.gt(0)
        & ambiguous_normal_outside.gt(0)
    )
    hard_good = ambiguous_good_inside.gt(0) & ambiguous_normal_inside.eq(0)
    hard_normal = ambiguous_good_inside.eq(0) & ambiguous_normal_inside.gt(0)
    hard_both = ambiguous_good_inside.gt(0) & ambiguous_normal_inside.gt(0)

    out.loc[clean_mask] = "clean"
    out.loc[soft_good] = "semi_clean_soft_other_good_nearby"
    out.loc[soft_normal] = "semi_clean_soft_normal_nearby"
    out.loc[soft_both] = "semi_clean_soft_good_and_normal_nearby"
    out.loc[hard_good] = "hard_contaminated_other_good_inside"
    out.loc[hard_normal] = "hard_contaminated_normal_inside"
    out.loc[hard_both] = "hard_contaminated_good_and_normal_inside"
    return out


def add_metric_specific_contamination(focal: pd.DataFrame, union_pairs: pd.DataFrame) -> pd.DataFrame:
    """Attach metric-specific contamination counts and keep flags."""

    other_pairs = focal[
        ["candidate_id", "transaction_id", "focal_school_name", "r_xy_m", "r_polygon_m"]
    ].merge(
        union_pairs[
            ["transaction_id", "school_name", "good_school", "inside_xy", "inside_polygon", "dist_xy_m", "dist_polygon_m"]
        ],
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

    def counts_for(metric: str) -> pd.DataFrame:
        ambiguous_col = f"{metric}_ambiguous"
        inside_col = f"inside_{metric}"

        metric_pairs = other_pairs.loc[other_pairs[ambiguous_col]].copy()
        if metric_pairs.empty:
            return pd.DataFrame({"candidate_id": focal["candidate_id"]})

        metric_pairs["ambiguous_inside"] = metric_pairs[inside_col].eq(1)
        metric_pairs["ambiguous_outside"] = ~metric_pairs["ambiguous_inside"]
        metric_pairs[f"ambiguous_good_inside_{metric}"] = (metric_pairs["good_school"] & metric_pairs["ambiguous_inside"]).astype(int)
        metric_pairs[f"ambiguous_normal_inside_{metric}"] = ((~metric_pairs["good_school"]) & metric_pairs["ambiguous_inside"]).astype(int)
        metric_pairs[f"ambiguous_good_outside_{metric}"] = (metric_pairs["good_school"] & metric_pairs["ambiguous_outside"]).astype(int)
        metric_pairs[f"ambiguous_normal_outside_{metric}"] = ((~metric_pairs["good_school"]) & metric_pairs["ambiguous_outside"]).astype(int)

        return (
            metric_pairs.groupby("candidate_id")[
                [
                    f"ambiguous_good_inside_{metric}",
                    f"ambiguous_normal_inside_{metric}",
                    f"ambiguous_good_outside_{metric}",
                    f"ambiguous_normal_outside_{metric}",
                ]
            ]
            .sum()
            .reset_index()
        )

    enriched = focal.copy()
    for metric in ("xy", "polygon"):
        counts = counts_for(metric)
        enriched = enriched.merge(counts, on="candidate_id", how="left")
        for col in [
            f"ambiguous_good_inside_{metric}",
            f"ambiguous_normal_inside_{metric}",
            f"ambiguous_good_outside_{metric}",
            f"ambiguous_normal_outside_{metric}",
        ]:
            enriched[col] = enriched[col].fillna(0).astype(int)

        enriched[f"contamination_tier_{metric}"] = classify_contamination_tier(
            ambiguous_good_inside=enriched[f"ambiguous_good_inside_{metric}"],
            ambiguous_normal_inside=enriched[f"ambiguous_normal_inside_{metric}"],
            ambiguous_good_outside=enriched[f"ambiguous_good_outside_{metric}"],
            ambiguous_normal_outside=enriched[f"ambiguous_normal_outside_{metric}"],
        )
        enriched[f"contamination_detail_{metric}"] = classify_contamination_detail(
            ambiguous_good_inside=enriched[f"ambiguous_good_inside_{metric}"],
            ambiguous_normal_inside=enriched[f"ambiguous_normal_inside_{metric}"],
            ambiguous_good_outside=enriched[f"ambiguous_good_outside_{metric}"],
            ambiguous_normal_outside=enriched[f"ambiguous_normal_outside_{metric}"],
        )
        enriched[f"keep_clean_or_semiclean_{metric}"] = enriched[f"contamination_tier_{metric}"].isin(["clean", "semi_clean_soft"])
    return enriched


def expand_metric_bandwidth_rows(enriched: pd.DataFrame) -> pd.DataFrame:
    """Expand the wide candidate table into one row per metric-bandwidth pair."""

    pieces: list[pd.DataFrame] = []
    metric_specs = [
        ("xy", "focal_dist_xy_m", "inside_focal_xy"),
        ("polygon", "focal_dist_polygon_m", "inside_focal_polygon"),
    ]
    for metric, dist_col, inside_col in metric_specs:
        for bandwidth in BANDWIDTHS_M:
            in_bw = enriched[dist_col].sub(ONE_KM_M).abs().le(bandwidth + DISTANCE_TOLERANCE_M)
            subset = enriched.loc[in_bw].copy()
            subset["metric"] = metric
            subset["bandwidth_m"] = bandwidth
            subset["inside_focal_metric"] = subset[inside_col].astype(int)
            subset["outside_good_count_metric"] = subset[f"outside_good_count_{metric}"]
            subset["outside_normal_count_metric"] = subset[f"outside_normal_count_{metric}"]
            subset["inside_good_count_metric"] = subset[f"inside_good_count_{metric}"]
            subset["inside_normal_count_metric"] = subset[f"inside_normal_count_{metric}"]
            subset["transition_label_metric"] = subset[f"transition_label_{metric}"]
            subset["contamination_tier"] = subset[f"contamination_tier_{metric}"]
            subset["contamination_detail"] = subset[f"contamination_detail_{metric}"]
            subset["keep_clean_or_semiclean"] = subset[f"keep_clean_or_semiclean_{metric}"]
            subset["broad_margin_group"] = margin_group(
                subset["outside_good_count_metric"],
                subset["inside_good_count_metric"],
            )
            pieces.append(subset)
    return pd.concat(pieces, ignore_index=True)
