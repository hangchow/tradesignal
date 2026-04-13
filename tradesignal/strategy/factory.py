from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .dual_momentum import DualMomentumParams, build_dual_momentum_signal
from .mean_reversion import MeanReversionParams, build_mean_reversion_signal


@dataclass(frozen=True)
class StrategyRuntime:
    params: Any
    signal: Any


def run_strategy_signal(
    strategy_name: str,
    strategy_params: Mapping[str, object],
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
) -> StrategyRuntime:
    if strategy_name == "dual_momentum":
        params = DualMomentumParams.from_mapping(strategy_params)
        params.validate()
        signal = build_dual_momentum_signal(prices, volumes, params=params)
        return StrategyRuntime(params=params, signal=signal)

    if strategy_name == "mean_reversion":
        params = MeanReversionParams.from_mapping(strategy_params)
        params.validate()
        signal = build_mean_reversion_signal(prices, volumes, params=params)
        return StrategyRuntime(params=params, signal=signal)

    raise ValueError(f"unsupported strategy.name: {strategy_name}")
