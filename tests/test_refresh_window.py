from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from tradesignal import polygon_day, yfinance_day


def _write_history(root: Path, code: str, trade_date: date) -> None:
    output_dir = root / code
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "time_key": f"{trade_date.isoformat()} 00:00:00",
                "open": 1.0,
                "close": 1.0,
                "high": 1.0,
                "low": 1.0,
                "volume": 1,
            }
        ]
    ).to_csv(output_dir / "2026-W15.csv", index=False)


class RefreshWindowTests(unittest.TestCase):
    def test_yfinance_refresh_window_bootstraps_when_any_symbol_missing_local_history(self) -> None:
        latest_completed_trade_date = date(2026, 4, 10)
        with TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            _write_history(data_root, "US.MSFT", latest_completed_trade_date)

            with (
                patch.object(yfinance_day, "expected_latest_trade_date", lambda code, now: latest_completed_trade_date),
                patch.object(yfinance_day, "next_trade_date", lambda code, current_date: current_date + timedelta(days=1)),
            ):
                start_date, end_date = yfinance_day.resolve_refresh_window(
                    data_root,
                    [("US.MSFT", "MSFT"), ("US.AVGO", "AVGO")],
                )

        self.assertEqual(end_date, latest_completed_trade_date)
        self.assertEqual(start_date, latest_completed_trade_date - timedelta(days=yfinance_day.DEFAULT_BOOTSTRAP_DAYS))

    def test_polygon_refresh_window_bootstraps_when_any_symbol_missing_local_history(self) -> None:
        latest_completed_trade_date = date(2026, 4, 10)
        with TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            _write_history(data_root, "US.MSFT", latest_completed_trade_date)

            with (
                patch.object(polygon_day, "expected_latest_us_trade_date", lambda now: latest_completed_trade_date),
                patch.object(polygon_day, "next_us_trade_date", lambda current_date: current_date + timedelta(days=1)),
            ):
                start_date, end_date = polygon_day.resolve_refresh_window(data_root, ["MSFT", "AVGO"])

        self.assertEqual(end_date, latest_completed_trade_date)
        self.assertEqual(start_date, latest_completed_trade_date - timedelta(days=polygon_day.DEFAULT_BOOTSTRAP_DAYS))

    def test_polygon_fetch_uses_symbol_specific_start_dates(self) -> None:
        fallback_start_date = date(2024, 4, 10)
        end_date = date(2026, 4, 10)
        existing_latest_date = end_date - timedelta(days=1)
        observed_calls: list[tuple[str, date]] = []

        def fake_fetch_history(*, symbol: str, start_date: date, end_date: date, adjusted: bool, api_key: str, insecure: bool):
            observed_calls.append((symbol, start_date))
            return pd.DataFrame(
                [
                    {
                        "time_key": f"{start_date.isoformat()} 00:00:00",
                        "open": 1.0,
                        "close": 1.0,
                        "high": 1.0,
                        "low": 1.0,
                        "volume": 1,
                    }
                ]
            )

        with TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            _write_history(data_root, "US.MSFT", existing_latest_date)

            with (
                patch.object(polygon_day, "next_us_trade_date", lambda current_date: current_date + timedelta(days=1)),
                patch.object(polygon_day, "fetch_history", fake_fetch_history),
                patch.object(polygon_day, "save_weekly_files", lambda **kwargs: (1, [])),
            ):
                polygon_day.fetch_and_store_history(
                    data_root=data_root,
                    symbols=["MSFT", "AVGO"],
                    start_date=fallback_start_date,
                    end_date=end_date,
                    api_key="test",
                    rate_limit_seconds=0,
                    insecure=False,
                )

        self.assertEqual(
            observed_calls,
            [
                ("MSFT", end_date),
                ("AVGO", fallback_start_date),
            ],
        )


if __name__ == "__main__":
    unittest.main()
