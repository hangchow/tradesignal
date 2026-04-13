from __future__ import annotations

import unittest

import pandas as pd

from tradesignal.strategy.factory import run_strategy_signal


class StrategyFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        idx = pd.date_range("2026-01-01", periods=100, freq="B").date
        self.prices = pd.DataFrame(
            {
                "US.A": [100.0 + i * 0.2 for i in range(100)],
                "US.B": [100.0] * 99 + [96.0],
            },
            index=idx,
        )
        self.volumes = pd.DataFrame({"US.A": [1_000_000.0] * 100, "US.B": [1_000_000.0] * 100}, index=idx)

    def test_runs_dual_momentum(self) -> None:
        runtime = run_strategy_signal("dual_momentum", {}, self.prices, self.volumes)
        self.assertEqual(runtime.params.__class__.__name__, "DualMomentumParams")

    def test_runs_mean_reversion(self) -> None:
        runtime = run_strategy_signal(
            "mean_reversion",
            {"use_rsi_filter": False, "min_volume_ratio": 0.1, "entry_z": 1.0},
            self.prices,
            self.volumes,
        )
        self.assertEqual(runtime.params.__class__.__name__, "MeanReversionParams")

    def test_raises_for_unknown_strategy(self) -> None:
        with self.assertRaises(ValueError):
            run_strategy_signal("unknown", {}, self.prices, self.volumes)


if __name__ == "__main__":
    unittest.main()
