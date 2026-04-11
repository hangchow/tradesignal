from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd

from scripts import explain_weighted_momentum
from tradesignal.config import AppConfig, StockPoolConfig, StrategyConfig


class ExplainWeightedMomentumTests(unittest.TestCase):
    def test_long_lookback_is_not_required_when_weight_is_zero(self) -> None:
        trade_dates = pd.date_range("2026-01-01", periods=130, freq="B").date
        prices = pd.DataFrame({"US.TEST": [100.0 + index for index in range(len(trade_dates))]}, index=trade_dates)
        volumes = pd.DataFrame({"US.TEST": [1_000_000.0] * len(trade_dates)}, index=trade_dates)
        config = AppConfig(
            stock_pool=StockPoolConfig(
                codes=("US.TEST",),
                market="US",
                data_root=Path("/tmp"),
                code_names={"US.TEST": "测试"},
            )
        )
        strategy = StrategyConfig(
            name="dual_momentum",
            params={
                "lookback_days": 90,
                "long_lookback_days": 180,
                "long_lookback_weight": 0.0,
                "top_n": 1,
                "volume_window": 20,
                "min_volume_ratio": 1.3,
                "market_filter_window": 120,
                "volatility_window": 20,
                "target_annual_vol": 0.3,
                "max_gross_exposure": 1.0,
            },
        )

        stdout = StringIO()
        with (
            patch("scripts.explain_weighted_momentum.load_config", return_value=config),
            patch("scripts.explain_weighted_momentum.load_default_strategy_config", return_value=strategy),
            patch("scripts.explain_weighted_momentum.load_daily_data", return_value=(prices, volumes)),
            patch("sys.argv", ["explain_weighted_momentum.py", "--config", "/tmp/config.json", "--code", "US.TEST"]),
            redirect_stdout(stdout),
        ):
            exit_code = explain_weighted_momentum.main()

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("短周期动量 =", output)
        self.assertIn("综合动量 =", output)
        self.assertNotIn("180 日前收盘", output)
        self.assertNotIn("长周期动量 =", output)


if __name__ == "__main__":
    unittest.main()
