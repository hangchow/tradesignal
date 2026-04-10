from __future__ import annotations

from datetime import date
import time as sleep_time
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


DEFAULT_FETCH_RETRIES = 3
DEFAULT_FETCH_RETRY_DELAY_SECONDS = 5.0
LOCAL_COLUMNS = ["time_key", "open", "close", "high", "low", "volume"]


class YFinanceDailyProvider:
    def __init__(self, *, fetch_retries: int = DEFAULT_FETCH_RETRIES, retry_delay_seconds: float = DEFAULT_FETCH_RETRY_DELAY_SECONDS):
        self.fetch_retries = fetch_retries
        self.retry_delay_seconds = retry_delay_seconds

    def fetch_history(self, *, code: str, symbol: str, start_date: date, end_date_exclusive: date) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(1, self.fetch_retries + 1):
            try:
                history = yf.Ticker(symbol).history(
                    start=start_date.isoformat(),
                    end=end_date_exclusive.isoformat(),
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                    raise_errors=True,
                )
                return convert_to_local_layout(history, timezone=market_timezone(code))
            except Exception as exc:
                last_error = exc
                if attempt >= self.fetch_retries:
                    break
                delay = self.retry_delay_seconds * attempt
                print(
                    "FETCH_RETRY "
                    f"code={code} attempt={attempt}/{self.fetch_retries} "
                    f"delay_seconds={delay:.1f} detail={exc}",
                    flush=True,
                )
                sleep_time.sleep(delay)

        assert last_error is not None
        raise RuntimeError(
            "yfinance daily fetch failed "
            f"code={code} start={start_date.isoformat()} end={end_date_exclusive.isoformat()} "
            f"after_attempts={self.fetch_retries} detail={last_error}"
        ) from last_error


def market_timezone(code: str) -> ZoneInfo:
    if str(code).upper().startswith("HK."):
        return ZoneInfo("Asia/Hong_Kong")
    return ZoneInfo("America/New_York")


def convert_to_local_layout(history: pd.DataFrame, *, timezone: ZoneInfo) -> pd.DataFrame:
    if history.empty:
        return pd.DataFrame(columns=LOCAL_COLUMNS)

    normalized = history.reset_index().rename(columns=str.lower)
    if "date" in normalized.columns:
        normalized = normalized.rename(columns={"date": "time_key"})
    elif "datetime" in normalized.columns:
        normalized = normalized.rename(columns={"datetime": "time_key"})
    required_columns = {"time_key", "open", "close", "high", "low", "volume"}
    missing = sorted(required_columns - set(normalized.columns))
    if missing:
        raise ValueError(f"yfinance response missing required columns: {', '.join(missing)}")

    timestamps = pd.to_datetime(normalized["time_key"])
    if getattr(timestamps.dt, "tz", None) is not None:
        timestamps = timestamps.dt.tz_convert(timezone).dt.tz_localize(None)
    rows = pd.DataFrame(
        {
            "time_key": timestamps.dt.strftime("%Y-%m-%d 00:00:00"),
            "open": pd.to_numeric(normalized["open"], errors="coerce"),
            "close": pd.to_numeric(normalized["close"], errors="coerce"),
            "high": pd.to_numeric(normalized["high"], errors="coerce"),
            "low": pd.to_numeric(normalized["low"], errors="coerce"),
            "volume": pd.to_numeric(normalized["volume"], errors="coerce").fillna(0).astype(int),
        }
    )
    rows = rows.dropna(subset=["open", "close", "high", "low"]).drop_duplicates(subset=["time_key"], keep="last")
    return rows.loc[:, LOCAL_COLUMNS].reset_index(drop=True)
