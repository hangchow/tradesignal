from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Sequence

import pandas as pd


def load_daily_data(data_root: Path, codes: Sequence[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    price_map: dict[str, pd.Series] = {}
    volume_map: dict[str, pd.Series] = {}
    latest_trade_dates: dict[str, object] = {}

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
        latest_trade_dates[code] = trade_dates.iloc[-1]
        price_map[code] = pd.Series(history["close"].astype(float).to_numpy(), index=trade_dates)
        volume_map[code] = pd.Series(history["volume"].astype(float).to_numpy(), index=trade_dates)

        print(
            f"LOADED code={code} files={len(csv_files)} rows={len(history)} elapsed_seconds={elapsed:.3f}",
            flush=True,
        )

    prices = pd.DataFrame(price_map).sort_index()
    volumes = pd.DataFrame(volume_map).sort_index()
    if prices.empty or volumes.empty:
        raise ValueError("no daily closes loaded")
    validate_latest_trade_dates(latest_trade_dates)
    return prices, volumes


def validate_latest_trade_dates(latest_trade_dates: dict[str, object]) -> None:
    unique_dates = {value for value in latest_trade_dates.values()}
    if len(unique_dates) <= 1:
        return

    details = ", ".join(f"{code}={trade_date}" for code, trade_date in sorted(latest_trade_dates.items()))
    raise ValueError(
        "stock pool latest trade dates are inconsistent; refresh all symbols before running signal. "
        f"latest_dates: {details}"
    )
