from __future__ import annotations

from datetime import date
import importlib

import pandas as pd


LOCAL_COLUMNS = ["time_key", "open", "close", "high", "low", "volume"]
MARKET_FETCHERS = {
    "HK": "stock_hk_daily",
    "US": "stock_us_daily",
}


class SinaDailyProvider:
    def fetch_history(self, *, code: str, symbol: str, start_date: date, end_date_exclusive: date) -> pd.DataFrame:
        try:
            ak_module = importlib.import_module("akshare")
        except ModuleNotFoundError:
            raise RuntimeError(
                "sina fallback unavailable because akshare is not installed "
                f"code={code} start={start_date.isoformat()} end={end_date_exclusive.isoformat()}"
            )

        target_symbol, fetcher_name = resolve_sina_symbol_and_fetcher(code=code, symbol=symbol)
        try:
            fetcher = getattr(ak_module, fetcher_name, None)
            if fetcher is None or not callable(fetcher):
                raise RuntimeError(f"akshare missing expected api={fetcher_name}")
            history = fetcher(symbol=target_symbol, adjust="")
        except Exception as exc:
            raise RuntimeError(
                "sina daily fetch failed "
                f"code={code} symbol={target_symbol} start={start_date.isoformat()} end={end_date_exclusive.isoformat()} detail={exc}"
            ) from exc

        if history.empty:
            return pd.DataFrame(columns=LOCAL_COLUMNS)

        history = history.rename(columns={"date": "time_key"})
        history["time_key"] = pd.to_datetime(history["time_key"]).dt.strftime("%Y-%m-%d 00:00:00")
        filtered = history.loc[
            (pd.to_datetime(history["time_key"]).dt.date >= start_date)
            & (pd.to_datetime(history["time_key"]).dt.date < end_date_exclusive),
            ["time_key", "open", "close", "high", "low", "volume"],
        ].copy()
        filtered["volume"] = pd.to_numeric(filtered["volume"], errors="coerce").fillna(0).astype(int)
        return filtered.reset_index(drop=True)


def resolve_sina_symbol_and_fetcher(*, code: str, symbol: str) -> tuple[str, str]:
    normalized_code = str(code).strip().upper()
    if normalized_code.startswith("HK."):
        raw_symbol = normalized_code.removeprefix("HK.")
        if not raw_symbol and symbol:
            raw_symbol = str(symbol).strip().upper().removesuffix(".HK")
        if not raw_symbol.isdigit():
            raise RuntimeError(f"invalid HK symbol for sina fallback code={code}")
        return f"{int(raw_symbol):05d}", MARKET_FETCHERS["HK"]

    if normalized_code.startswith("US."):
        raw_symbol = str(symbol).strip().upper() if symbol else normalized_code.removeprefix("US.").strip().upper()
        if not raw_symbol:
            raise RuntimeError(f"invalid US symbol for sina fallback code={code}")
        return raw_symbol, MARKET_FETCHERS["US"]

    raise RuntimeError(f"unsupported market for sina fallback code={code}")
