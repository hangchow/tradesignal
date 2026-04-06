from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .volume import compute_relative_volume, validate_volume_filter


DEFAULT_LOOKBACK_DAYS = 90
DEFAULT_LONG_LOOKBACK_DAYS = 180
DEFAULT_LONG_LOOKBACK_WEIGHT = 0.25
DEFAULT_TOP_N = 1
DEFAULT_VOLUME_WINDOW = 20
DEFAULT_MIN_VOLUME_RATIO = 1.3
MAX_VOLUME_BOOST_RATIO = 1.5
DEFAULT_MARKET_FILTER_WINDOW = 120
DEFAULT_VOLATILITY_WINDOW = 20
DEFAULT_TARGET_ANNUAL_VOL = 0.30
DEFAULT_MAX_GROSS_EXPOSURE = 1.0


@dataclass(frozen=True)
class DualMomentumParams:
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    long_lookback_days: int = DEFAULT_LONG_LOOKBACK_DAYS
    long_lookback_weight: float = DEFAULT_LONG_LOOKBACK_WEIGHT
    top_n: int = DEFAULT_TOP_N
    volume_window: int = DEFAULT_VOLUME_WINDOW
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO
    market_filter_window: int = DEFAULT_MARKET_FILTER_WINDOW
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW
    target_annual_vol: float = DEFAULT_TARGET_ANNUAL_VOL
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE

    @classmethod
    def from_mapping(cls, values: Mapping[str, object] | None = None) -> DualMomentumParams:
        raw = values or {}
        return cls(
            lookback_days=int(raw.get("lookback_days", DEFAULT_LOOKBACK_DAYS)),
            long_lookback_days=int(raw.get("long_lookback_days", DEFAULT_LONG_LOOKBACK_DAYS)),
            long_lookback_weight=float(raw.get("long_lookback_weight", DEFAULT_LONG_LOOKBACK_WEIGHT)),
            top_n=int(raw.get("top_n", DEFAULT_TOP_N)),
            volume_window=int(raw.get("volume_window", DEFAULT_VOLUME_WINDOW)),
            min_volume_ratio=float(raw.get("min_volume_ratio", DEFAULT_MIN_VOLUME_RATIO)),
            market_filter_window=int(raw.get("market_filter_window", DEFAULT_MARKET_FILTER_WINDOW)),
            volatility_window=int(raw.get("volatility_window", DEFAULT_VOLATILITY_WINDOW)),
            target_annual_vol=float(raw.get("target_annual_vol", DEFAULT_TARGET_ANNUAL_VOL)),
            max_gross_exposure=float(raw.get("max_gross_exposure", DEFAULT_MAX_GROSS_EXPOSURE)),
        )

    def validate(self) -> None:
        validate_dual_momentum_params(
            lookback_days=self.lookback_days,
            long_lookback_days=self.long_lookback_days,
            long_lookback_weight=self.long_lookback_weight,
            top_n=self.top_n,
            volume_window=self.volume_window,
            min_volume_ratio=self.min_volume_ratio,
            market_filter_window=self.market_filter_window,
            volatility_window=self.volatility_window,
            target_annual_vol=self.target_annual_vol,
            max_gross_exposure=self.max_gross_exposure,
        )

    def required_warmup_bars(self) -> int:
        return required_dual_momentum_warmup_bars(params=self)


@dataclass(frozen=True)
class DualMomentumSignal:
    completed_trade_date: Any
    target_codes: tuple[str, ...]
    target_weights: dict[str, float]
    gross_exposure: float
    market_is_risk_on: bool
    candidate_codes: tuple[str, ...]


def select_target_codes(momentum: pd.Series, top_n: int) -> list[str]:
    eligible = momentum.dropna()
    eligible = eligible[eligible > 0]
    if eligible.empty:
        return []
    return eligible.sort_values(ascending=False).head(top_n).index.tolist()


def compute_volume_boost(volume_ratio: pd.Series, min_volume_ratio: float) -> pd.Series:
    capped_ratio = volume_ratio.clip(upper=MAX_VOLUME_BOOST_RATIO)
    volume_boost = pd.Series(1.0, index=volume_ratio.index, dtype=float)
    boosted = capped_ratio >= min_volume_ratio
    volume_boost.loc[boosted] = capped_ratio.loc[boosted] / min_volume_ratio
    return volume_boost.where(volume_ratio.notna())


def validate_dual_momentum_params(
    *,
    lookback_days: int,
    long_lookback_days: int,
    long_lookback_weight: float,
    top_n: int,
    volume_window: int,
    min_volume_ratio: float,
    market_filter_window: int,
    volatility_window: int,
    target_annual_vol: float,
    max_gross_exposure: float,
) -> None:
    if lookback_days <= 0:
        raise ValueError("lookback-days must be positive")
    if long_lookback_days <= 0:
        raise ValueError("long-lookback-days must be positive")
    if not 0 <= long_lookback_weight <= 1:
        raise ValueError("long-lookback-weight must be within [0, 1]")
    if top_n <= 0:
        raise ValueError("top-n must be positive")
    validate_volume_filter(volume_window, min_volume_ratio)
    if market_filter_window <= 0:
        raise ValueError("market-filter-window must be positive")
    if volatility_window <= 1:
        raise ValueError("volatility-window must be > 1")
    if target_annual_vol <= 0:
        raise ValueError("target-annual-vol must be positive")
    if max_gross_exposure < 1:
        raise ValueError("max-gross-exposure must be >= 1")


def _resolve_dual_momentum_params(
    *,
    params: DualMomentumParams | None,
    lookback_days: int,
    long_lookback_days: int,
    long_lookback_weight: float,
    top_n: int,
    volume_window: int,
    min_volume_ratio: float,
    market_filter_window: int,
    volatility_window: int,
    target_annual_vol: float,
    max_gross_exposure: float,
) -> DualMomentumParams:
    resolved = params or DualMomentumParams(
        lookback_days=lookback_days,
        long_lookback_days=long_lookback_days,
        long_lookback_weight=long_lookback_weight,
        top_n=top_n,
        volume_window=volume_window,
        min_volume_ratio=min_volume_ratio,
        market_filter_window=market_filter_window,
        volatility_window=volatility_window,
        target_annual_vol=target_annual_vol,
        max_gross_exposure=max_gross_exposure,
    )
    resolved.validate()
    return resolved


def required_dual_momentum_signal_bars(
    *,
    params: DualMomentumParams | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    long_lookback_days: int = DEFAULT_LONG_LOOKBACK_DAYS,
    long_lookback_weight: float = DEFAULT_LONG_LOOKBACK_WEIGHT,
    top_n: int = DEFAULT_TOP_N,
    volume_window: int = DEFAULT_VOLUME_WINDOW,
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO,
    market_filter_window: int = DEFAULT_MARKET_FILTER_WINDOW,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    target_annual_vol: float = DEFAULT_TARGET_ANNUAL_VOL,
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE,
) -> int:
    resolved = _resolve_dual_momentum_params(
        params=params,
        lookback_days=lookback_days,
        long_lookback_days=long_lookback_days,
        long_lookback_weight=long_lookback_weight,
        top_n=top_n,
        volume_window=volume_window,
        min_volume_ratio=min_volume_ratio,
        market_filter_window=market_filter_window,
        volatility_window=volatility_window,
        target_annual_vol=target_annual_vol,
        max_gross_exposure=max_gross_exposure,
    )
    return max(
        resolved.lookback_days + 1,
        resolved.long_lookback_days + 1 if resolved.long_lookback_weight > 0 else resolved.lookback_days + 1,
        resolved.market_filter_window,
        resolved.volatility_window + 1,
        resolved.volume_window + 1,
    )


def required_dual_momentum_warmup_bars(
    *,
    params: DualMomentumParams | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    long_lookback_days: int = DEFAULT_LONG_LOOKBACK_DAYS,
    long_lookback_weight: float = DEFAULT_LONG_LOOKBACK_WEIGHT,
    top_n: int = DEFAULT_TOP_N,
    volume_window: int = DEFAULT_VOLUME_WINDOW,
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO,
    market_filter_window: int = DEFAULT_MARKET_FILTER_WINDOW,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    target_annual_vol: float = DEFAULT_TARGET_ANNUAL_VOL,
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE,
) -> int:
    signal_bars = required_dual_momentum_signal_bars(
        params=params,
        lookback_days=lookback_days,
        long_lookback_days=long_lookback_days,
        long_lookback_weight=long_lookback_weight,
        top_n=top_n,
        volume_window=volume_window,
        min_volume_ratio=min_volume_ratio,
        market_filter_window=market_filter_window,
        volatility_window=volatility_window,
        target_annual_vol=target_annual_vol,
        max_gross_exposure=max_gross_exposure,
    )
    return max(signal_bars, 30) + 5


def build_dual_momentum_signal(
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    *,
    params: DualMomentumParams | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    long_lookback_days: int = DEFAULT_LONG_LOOKBACK_DAYS,
    long_lookback_weight: float = DEFAULT_LONG_LOOKBACK_WEIGHT,
    top_n: int = DEFAULT_TOP_N,
    volume_window: int = DEFAULT_VOLUME_WINDOW,
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO,
    market_filter_window: int = DEFAULT_MARKET_FILTER_WINDOW,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    target_annual_vol: float = DEFAULT_TARGET_ANNUAL_VOL,
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE,
) -> DualMomentumSignal | None:
    resolved = _resolve_dual_momentum_params(
        params=params,
        lookback_days=lookback_days,
        long_lookback_days=long_lookback_days,
        long_lookback_weight=long_lookback_weight,
        top_n=top_n,
        volume_window=volume_window,
        min_volume_ratio=min_volume_ratio,
        market_filter_window=market_filter_window,
        volatility_window=volatility_window,
        target_annual_vol=target_annual_vol,
        max_gross_exposure=max_gross_exposure,
    )
    signals = build_dual_momentum_signal_history(prices, volumes, params=resolved)
    if signals.empty:
        return None
    return signals.iloc[-1]


def build_dual_momentum_signal_history(
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    *,
    params: DualMomentumParams | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    long_lookback_days: int = DEFAULT_LONG_LOOKBACK_DAYS,
    long_lookback_weight: float = DEFAULT_LONG_LOOKBACK_WEIGHT,
    top_n: int = DEFAULT_TOP_N,
    volume_window: int = DEFAULT_VOLUME_WINDOW,
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO,
    market_filter_window: int = DEFAULT_MARKET_FILTER_WINDOW,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    target_annual_vol: float = DEFAULT_TARGET_ANNUAL_VOL,
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE,
) -> pd.Series:
    resolved = _resolve_dual_momentum_params(
        params=params,
        lookback_days=lookback_days,
        long_lookback_days=long_lookback_days,
        long_lookback_weight=long_lookback_weight,
        top_n=top_n,
        volume_window=volume_window,
        min_volume_ratio=min_volume_ratio,
        market_filter_window=market_filter_window,
        volatility_window=volatility_window,
        target_annual_vol=target_annual_vol,
        max_gross_exposure=max_gross_exposure,
    )
    if prices.empty or volumes.empty:
        return pd.Series(dtype=object)
    if not prices.index.equals(volumes.index) or not prices.columns.equals(volumes.columns):
        raise ValueError("prices and volumes must share the same index and columns")

    required_bars = required_dual_momentum_signal_bars(params=resolved)
    top_n = min(resolved.top_n, len(prices.columns))
    relative_volume = volumes.apply(lambda column: compute_relative_volume(column, resolved.volume_window))
    short_momentum = prices.divide(prices.shift(resolved.lookback_days)) - 1
    if resolved.long_lookback_weight > 0:
        long_momentum = prices.divide(prices.shift(resolved.long_lookback_days)) - 1
    else:
        long_momentum = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    blended_momentum = short_momentum * (1 - resolved.long_lookback_weight) + long_momentum * resolved.long_lookback_weight
    weighted_momentum = blended_momentum.where(blended_momentum > 0) * relative_volume.apply(
        lambda row: compute_volume_boost(row, resolved.min_volume_ratio),
        axis=1,
    )

    pool_close = prices.mean(axis=1)
    pool_ma = pool_close.rolling(
        window=resolved.market_filter_window,
        min_periods=resolved.market_filter_window,
    ).mean()
    daily_pool_returns = pool_close.pct_change()
    realized_daily_vol = daily_pool_returns.rolling(
        window=resolved.volatility_window,
        min_periods=resolved.volatility_window,
    ).std()
    target_vol_multiplier = pd.Series(1.0, index=prices.index, dtype=float)
    positive_vol_mask = realized_daily_vol > 0
    annualized_vol = realized_daily_vol.loc[positive_vol_mask] * (252**0.5)
    target_vol_multiplier.loc[positive_vol_mask] = (
        resolved.target_annual_vol / annualized_vol
    ).clip(upper=1.0)

    signals: list[DualMomentumSignal | None] = []
    for index, trade_date in enumerate(prices.index):
        if index + 1 < required_bars:
            signals.append(None)
            continue

        candidate_codes = tuple(select_target_codes(weighted_momentum.iloc[index], top_n))
        market_is_risk_on = bool(pd.notna(pool_ma.iloc[index]) and pool_close.iloc[index] >= pool_ma.iloc[index])
        target_codes = candidate_codes if market_is_risk_on else ()
        gross_exposure = float(target_vol_multiplier.iloc[index] * resolved.max_gross_exposure) if target_codes else 0.0
        weight_per_code = gross_exposure / len(target_codes) if target_codes else 0.0
        signals.append(
            DualMomentumSignal(
                completed_trade_date=trade_date,
                target_codes=target_codes,
                target_weights={code: weight_per_code for code in target_codes},
                gross_exposure=gross_exposure,
                market_is_risk_on=market_is_risk_on,
                candidate_codes=candidate_codes,
            )
        )

    return pd.Series(signals, index=prices.index, dtype=object)
