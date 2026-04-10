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
        try:
            return self.primary.fetch_history(
                code=code,
                symbol=symbol,
                start_date=start_date,
                end_date_exclusive=end_date_exclusive,
            )
        except Exception as exc:
            if not code.upper().startswith("HK."):
                raise
            print(f"FETCH_FALLBACK code={code} source=sina reason={exc}", flush=True)
            return self.fallback.fetch_history(
                code=code,
                symbol=symbol,
                start_date=start_date,
                end_date_exclusive=end_date_exclusive,
            )
