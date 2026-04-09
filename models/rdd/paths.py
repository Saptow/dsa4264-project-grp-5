from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[2]


def good_schools_data_root() -> Path:
    """Return the processed-data folder used by the good-school specifications."""

    return project_root() / "data" / "processed" / "rdd_a"
