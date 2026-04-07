from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
import time as sleep_time
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd
import yfinance as yf


DEFAULT_RATE_LIMIT_SECONDS = 1.0
DEFAULT_BOOTSTRAP_DAYS = 730
NEW_YORK = ZoneInfo("America/New_York")
HONG_KONG = ZoneInfo("Asia/Hong_Kong")
LOCAL_COLUMNS = ["time_key", "open", "close", "high", "low", "volume"]


def refresh_daily_data(
    data_root: Path,
    codes: list[str] | tuple[str, ...],
    *,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
) -> None:
    symbols = normalize_symbols(codes)
    if not symbols:
        raise ValueError("no supported US/HK symbols found in stock_pool.codes")

    start_date, end_date = resolve_refresh_window(data_root, symbols)
    if start_date > end_date:
        print(f"FETCH_SKIPPED start={start_date.isoformat()} end={end_date.isoformat()} reason=up_to_date", flush=True)
        return

    print(
        f"FETCHING_YFINANCE start={start_date.isoformat()} end={end_date.isoformat()} symbols={len(symbols)} data_root={data_root}",
        flush=True,
    )
    fetch_and_store_history(
        data_root=data_root,
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        rate_limit_seconds=rate_limit_seconds,
    )


def normalize_symbols(codes: list[str] | tuple[str, ...]) -> list[tuple[str, str]]:
    symbols: list[tuple[str, str]] = []
    for code in codes:
        value = str(code).strip().upper()
        if not value:
            continue
        if value.startswith("US."):
            symbol = value.removeprefix("US.")
            if symbol:
                symbols.append((value, symbol))
            continue
        if value.startswith("HK."):
            raw_symbol = value.removeprefix("HK.")
            if raw_symbol.isdigit():
                symbols.append((value, f"{int(raw_symbol):04d}.HK"))
    return symbols


def resolve_refresh_window(data_root: Path, symbols: list[tuple[str, str]]) -> tuple[date, date]:
    latest_dates: list[tuple[str, date]] = []
    latest_completed_trade_dates: list[date] = []
    for code, _ in symbols:
        latest_date = get_latest_local_trade_date(data_root / code)
        if latest_date is not None:
            latest_dates.append((code, latest_date))
        latest_completed_trade_dates.append(expected_latest_trade_date(code, datetime.now(market_timezone(code))))

    latest_completed_trade_date = min(latest_completed_trade_dates)
    if latest_dates:
        start_date = min(next_trade_date(code, latest_date) for code, latest_date in latest_dates)
    else:
        start_date = latest_completed_trade_date - timedelta(days=DEFAULT_BOOTSTRAP_DAYS)
    return start_date, latest_completed_trade_date


@lru_cache(maxsize=1)
def us_market_calendar():
    return xcals.get_calendar("XNYS")


@lru_cache(maxsize=1)
def hk_market_calendar():
    return xcals.get_calendar("XHKG")


def market_calendar(code: str):
    if str(code).upper().startswith("HK."):
        return hk_market_calendar()
    return us_market_calendar()


def market_timezone(code: str) -> ZoneInfo:
    if str(code).upper().startswith("HK."):
        return HONG_KONG
    return NEW_YORK


def expected_latest_trade_date(code: str, now: datetime) -> date:
    calendar = market_calendar(code)
    timezone = market_timezone(code)
    current = now.astimezone(timezone)
    current_session_label = pd.Timestamp(current.date())
    if calendar.is_session(current_session_label):
        current_session_open = calendar.session_open(current_session_label).tz_convert(timezone)
        if current >= current_session_open:
            return pd.Timestamp(calendar.previous_session(current_session_label)).date()
        previous_session = calendar.previous_session(current_session_label)
        return pd.Timestamp(calendar.previous_session(previous_session)).date()

    next_session = calendar.date_to_session(current_session_label, direction="next")
    previous_session = calendar.previous_session(next_session)
    return pd.Timestamp(calendar.previous_session(previous_session)).date()


def next_trade_date(code: str, current_date: date) -> date:
    calendar = market_calendar(code)
    current_session_label = pd.Timestamp(current_date)
    if calendar.is_session(current_session_label):
        return pd.Timestamp(calendar.next_session(current_session_label)).date()
    return pd.Timestamp(calendar.date_to_session(current_session_label, direction="next")).date()


def next_calendar_date(current_date: date) -> date:
    return current_date + timedelta(days=1)


def get_latest_local_trade_date(output_root: Path) -> date | None:
    latest: date | None = None
    for path in sorted(output_root.glob("*.csv")):
        try:
            history = pd.read_csv(path, usecols=["time_key"])
        except (FileNotFoundError, pd.errors.EmptyDataError):
            continue
        if history.empty:
            continue
        candidate = pd.to_datetime(history["time_key"]).max().date()
        if latest is None or candidate > latest:
            latest = candidate
    return latest


def fetch_and_store_history(
    *,
    data_root: Path,
    symbols: list[tuple[str, str]],
    start_date: date,
    end_date: date,
    rate_limit_seconds: float,
) -> None:
    end_exclusive = next_calendar_date(end_date)
    for index, (code, symbol) in enumerate(symbols):
        output_root = data_root / code
        history = fetch_history(code=code, symbol=symbol, start_date=start_date, end_date_exclusive=end_exclusive)
        if history.empty:
            raise RuntimeError(
                f"yfinance daily fetch returned no rows code={code} start={start_date.isoformat()} end={end_date.isoformat()}"
            )

        file_count, _ = save_weekly_files(
            history=history,
            output_root=output_root,
            code=code,
            keep_existing=True,
        )
        print(
            "FETCHED "
            f"code={code} rows={len(history)} start={history.iloc[0]['time_key'][:10]} "
            f"end={history.iloc[-1]['time_key'][:10]} weekly_files={file_count}",
            flush=True,
        )

        if index + 1 < len(symbols):
            sleep_time.sleep(rate_limit_seconds)


def fetch_history(code: str, symbol: str, start_date: date, end_date_exclusive: date) -> pd.DataFrame:
    try:
        history = yf.Ticker(symbol).history(
            start=start_date.isoformat(),
            end=end_date_exclusive.isoformat(),
            interval="1d",
            auto_adjust=True,
            actions=False,
            raise_errors=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "yfinance daily fetch failed "
            f"code={code} start={start_date.isoformat()} end={end_date_exclusive.isoformat()} detail={exc}"
        ) from exc
    return convert_to_local_layout(history, timezone=market_timezone(code))


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


def merge_weekly_payload(file_path: Path, weekly: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    incoming = weekly.loc[:, columns].copy()
    if not file_path.exists():
        return incoming

    try:
        existing = pd.read_csv(file_path, usecols=lambda column: column in columns)
    except pd.errors.EmptyDataError:
        existing = pd.DataFrame(columns=columns)

    if existing.empty:
        return incoming

    merged = pd.concat([existing, incoming], ignore_index=True)
    merged["time_key"] = pd.to_datetime(merged["time_key"])
    merged = merged.sort_values("time_key").drop_duplicates(subset=["time_key"], keep="last").reset_index(drop=True)
    merged["time_key"] = merged["time_key"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return merged.loc[:, columns]


def save_weekly_files(history: pd.DataFrame, output_root: Path, code: str, keep_existing: bool) -> tuple[int, int]:
    output_root.mkdir(parents=True, exist_ok=True)
    dated = history.copy()
    dated["trade_date"] = pd.to_datetime(dated["time_key"]).dt.normalize()
    dated["week_start"] = dated["trade_date"] - pd.to_timedelta(dated["trade_date"].dt.weekday, unit="D")

    written_names: set[str] = set()
    file_count = 0
    for week_start, weekly in dated.groupby("week_start", sort=True):
        weekly_path = output_root / f"{code}_{week_start.date().isoformat()}.csv"
        merged_weekly = merge_weekly_payload(weekly_path, weekly, LOCAL_COLUMNS)
        merged_weekly.to_csv(weekly_path, index=False)
        print(
            "KLINE_WRITTEN "
            f"code={code} path={weekly_path} rows={len(merged_weekly)} "
            f"start={merged_weekly.iloc[0]['time_key'][:10]} end={merged_weekly.iloc[-1]['time_key'][:10]}",
            flush=True,
        )
        written_names.add(weekly_path.name)
        file_count += 1

    removed_count = 0 if keep_existing else remove_stale_weekly_files(output_root, code, written_names)
    return file_count, removed_count


def remove_stale_weekly_files(output_root: Path, code: str, keep_names: set[str]) -> int:
    removed_count = 0
    for path in output_root.glob(f"{code}_*.csv"):
        if path.name in keep_names:
            continue
        path.unlink()
        removed_count += 1
    return removed_count
