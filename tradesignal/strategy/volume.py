from __future__ import annotations

import pandas as pd


def validate_volume_filter(volume_window: int, min_volume_ratio: float) -> None:
    if volume_window <= 0:
        raise ValueError("volume-window must be positive")
    if min_volume_ratio <= 0:
        raise ValueError("min-volume-ratio must be positive")


def compute_relative_volume(volume: pd.Series, volume_window: int) -> pd.Series:
    validate_volume_filter(volume_window, 1e-9)
    baseline = volume.shift(1).rolling(window=volume_window, min_periods=1).mean()
    relative_volume = (volume / baseline).replace([float("inf"), float("-inf")], pd.NA)
    relative_volume = relative_volume.where(volume.notna(), pd.NA)
    relative_volume = relative_volume.mask(volume.notna() & baseline.isna(), 1.0)
    return pd.to_numeric(relative_volume, errors="coerce")
