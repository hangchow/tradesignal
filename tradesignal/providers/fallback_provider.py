from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd


class HistoryProvider(Protocol):
    def fetch_history(self, *, code: str, symbol: str, start_date: date, end_date_exclusive: date) -> pd.DataFrame: ...


@dataclass(slots=True)
class FallbackHistoryProvider:
    primary: HistoryProvider
    fallback: HistoryProvider

    def fetch_history(self, *, code: str, symbol: str, start_date: date, end_date_exclusive: date) -> pd.DataFrame:
        primary_error: Exception | None = None
        try:
            return self.primary.fetch_history(
                code=code,
                symbol=symbol,
                start_date=start_date,
                end_date_exclusive=end_date_exclusive,
            )
        except Exception as primary_exc:
            primary_error = primary_exc
            print(
                "FETCH_FALLBACK "
                f"code={code} primary={type(self.primary).__name__} fallback={type(self.fallback).__name__} "
                f"reason={primary_exc}",
                flush=True,
            )

        try:
            return self.fallback.fetch_history(
                code=code,
                symbol=symbol,
                start_date=start_date,
                end_date_exclusive=end_date_exclusive,
            )
        except Exception as fallback_exc:
            primary_detail = str(primary_error) if primary_error is not None else "unknown"
            raise RuntimeError(
                "history fetch failed after fallback "
                f"code={code} symbol={symbol} start={start_date.isoformat()} end={end_date_exclusive.isoformat()} "
                f"primary_detail={primary_detail} fallback_detail={fallback_exc}"
            ) from fallback_exc
