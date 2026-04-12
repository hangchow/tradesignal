from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from tradesignal import daily_history


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
    def test_daily_history_refresh_window_bootstraps_when_any_symbol_missing_local_history(self) -> None:
        latest_completed_trade_date = date(2026, 4, 10)
        with TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            _write_history(data_root, "US.MSFT", latest_completed_trade_date)

            with (
                patch.object(daily_history, "expected_latest_trade_date", lambda code, now: latest_completed_trade_date),
                patch.object(daily_history, "next_trade_date", lambda code, current_date: current_date + timedelta(days=1)),
            ):
                start_date, end_date = daily_history.resolve_refresh_window(
                    data_root,
                    [("US.MSFT", "MSFT"), ("US.AVGO", "AVGO")],
                )

        self.assertEqual(end_date, latest_completed_trade_date)
        self.assertEqual(start_date, latest_completed_trade_date - timedelta(days=daily_history.DEFAULT_BOOTSTRAP_DAYS))

if __name__ == "__main__":
    unittest.main()
