from __future__ import annotations

import unittest

import pandas as pd

from tradesignal.strategy.mean_reversion import MeanReversionParams, build_mean_reversion_signal


class MeanReversionSignalTests(unittest.TestCase):
    def _build_frames(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        idx = pd.date_range("2026-01-01", periods=80, freq="B").date
        stable = [100.0] * 79 + [95.0]
        trending = [100.0 + i * 0.4 for i in range(80)]
        prices = pd.DataFrame(
            {
                "US.REVERT": stable,
                "US.TREND": trending,
            },
            index=idx,
        )
        volumes = pd.DataFrame({"US.REVERT": [1_000_000.0] * 80, "US.TREND": [1_000_000.0] * 80}, index=idx)
        return prices, volumes

    def test_selects_oversold_code_with_rsi_filter_enabled(self) -> None:
        prices, volumes = self._build_frames()
        params = MeanReversionParams(
            mr_window=20,
            entry_z=1.0,
            top_n=1,
            use_rsi_filter=True,
            rsi_window=14,
            rsi_oversold=40,
            use_adf_filter=False,
            min_volume_ratio=0.1,
            market_filter_window=1,
        )

        signal = build_mean_reversion_signal(prices, volumes, params=params)
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.target_codes, ("US.REVERT",))

    def test_returns_none_when_warmup_bars_not_enough(self) -> None:
        idx = pd.date_range("2026-01-01", periods=10, freq="B").date
        prices = pd.DataFrame({"US.A": [100.0] * 10}, index=idx)
        volumes = pd.DataFrame({"US.A": [1_000_000.0] * 10}, index=idx)
        params = MeanReversionParams(mr_window=20)

        signal = build_mean_reversion_signal(prices, volumes, params=params)
        self.assertIsNone(signal)

    def test_market_filter_blocks_targets_to_cash(self) -> None:
        idx = pd.date_range("2026-01-01", periods=80, freq="B").date
        downtrend = [100.0 - i * 0.2 for i in range(80)]
        prices = pd.DataFrame({"US.REVERT": downtrend}, index=idx)
        prices.iloc[-1, 0] = prices.iloc[-1, 0] - 2.0
        volumes = pd.DataFrame({"US.REVERT": [1_000_000.0] * 80}, index=idx)
        params = MeanReversionParams(
            mr_window=20,
            entry_z=0.8,
            use_rsi_filter=False,
            use_adf_filter=False,
            market_filter_window=60,
            min_volume_ratio=0.1,
        )

        signal = build_mean_reversion_signal(prices, volumes, params=params)
        self.assertIsNotNone(signal)
        assert signal is not None
        self.assertEqual(signal.candidate_codes, ("US.REVERT",))
        self.assertEqual(signal.target_codes, ())


    def test_rejects_exit_z_greater_than_entry_z(self) -> None:
        with self.assertRaises(ValueError):
            MeanReversionParams(entry_z=1.0, exit_z=1.2).validate()


if __name__ == "__main__":
    unittest.main()
