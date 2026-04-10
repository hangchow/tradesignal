from __future__ import annotations

from datetime import date

import pandas as pd

try:
    import akshare as ak
except Exception:  # pragma: no cover - optional fallback import guard
    ak = None


LOCAL_COLUMNS = ["time_key", "open", "close", "high", "low", "volume"]


class SinaDailyProvider:
    def fetch_history(self, *, code: str, symbol: str, start_date: date, end_date_exclusive: date) -> pd.DataFrame:
        if ak is None:
            raise RuntimeError(
                "sina fallback unavailable because akshare is not installed "
                f"code={code} start={start_date.isoformat()} end={end_date_exclusive.isoformat()}"
            )

        raw_symbol = str(code).upper().removeprefix("HK.")
        if not raw_symbol.isdigit():
            raise RuntimeError(f"invalid HK symbol for sina fallback code={code}")

        target_symbol = f"{int(raw_symbol):05d}"
        try:
            history = ak.stock_hk_daily(symbol=target_symbol, adjust="")
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
