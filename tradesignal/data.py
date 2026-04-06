from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Sequence

import pandas as pd


def load_daily_data(data_root: Path, codes: Sequence[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    price_map: dict[str, pd.Series] = {}
    volume_map: dict[str, pd.Series] = {}

    for code in codes:
        history_parts: list[pd.DataFrame] = []
        csv_files = sorted((data_root / code).glob("*.csv"))
        started_at = perf_counter()
        for path in csv_files:
            history = pd.read_csv(path, usecols=["time_key", "close", "volume"])
            if history.empty:
                continue
            history_parts.append(history)
        elapsed = perf_counter() - started_at
        if not history_parts:
            raise FileNotFoundError(f"No CSV files found in {data_root / code}")

        history = pd.concat(history_parts, ignore_index=True)
        history["time_key"] = pd.to_datetime(history["time_key"])
        history = history.sort_values("time_key").drop_duplicates(subset=["time_key"], keep="last").reset_index(drop=True)
        trade_dates = history["time_key"].dt.date
        price_map[code] = pd.Series(history["close"].astype(float).to_numpy(), index=trade_dates)
        volume_map[code] = pd.Series(history["volume"].astype(float).to_numpy(), index=trade_dates)

        print(f"LOADED code={code} files={len(csv_files)} rows={len(history)} elapsed_seconds={elapsed:.3f}")

    prices = pd.DataFrame(price_map).sort_index()
    volumes = pd.DataFrame(volume_map).sort_index()
    if prices.empty or volumes.empty:
        raise ValueError("no daily closes loaded")
    return prices, volumes
