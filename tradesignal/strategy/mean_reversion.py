from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pandas as pd
from .volume import compute_relative_volume, validate_volume_filter


DEFAULT_MR_WINDOW = 20
DEFAULT_ENTRY_Z = 1.5
DEFAULT_EXIT_Z = 0.2
DEFAULT_TOP_N = 1
DEFAULT_VOLUME_WINDOW = 20
DEFAULT_MIN_VOLUME_RATIO = 1.0
DEFAULT_USE_RSI_FILTER = True
DEFAULT_RSI_WINDOW = 14
DEFAULT_RSI_OVERSOLD = 35.0
DEFAULT_USE_ADF_FILTER = False
DEFAULT_ADF_WINDOW = 120
DEFAULT_ADF_PVALUE_MAX = 0.10
DEFAULT_MARKET_FILTER_WINDOW = 60
DEFAULT_VOLATILITY_WINDOW = 20
DEFAULT_TARGET_ANNUAL_VOL = 0.25
DEFAULT_MAX_GROSS_EXPOSURE = 1.0


@dataclass(frozen=True)
class MeanReversionParams:
    mr_window: int = DEFAULT_MR_WINDOW
    entry_z: float = DEFAULT_ENTRY_Z
    exit_z: float = DEFAULT_EXIT_Z
    top_n: int = DEFAULT_TOP_N
    volume_window: int = DEFAULT_VOLUME_WINDOW
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO
    use_rsi_filter: bool = DEFAULT_USE_RSI_FILTER
    rsi_window: int = DEFAULT_RSI_WINDOW
    rsi_oversold: float = DEFAULT_RSI_OVERSOLD
    use_adf_filter: bool = DEFAULT_USE_ADF_FILTER
    adf_window: int = DEFAULT_ADF_WINDOW
    adf_pvalue_max: float = DEFAULT_ADF_PVALUE_MAX
    market_filter_window: int = DEFAULT_MARKET_FILTER_WINDOW
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW
    target_annual_vol: float = DEFAULT_TARGET_ANNUAL_VOL
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE

    @classmethod
    def from_mapping(cls, values: Mapping[str, object] | None = None) -> MeanReversionParams:
        raw = values or {}
        return cls(
            mr_window=int(raw.get("mr_window", DEFAULT_MR_WINDOW)),
            entry_z=float(raw.get("entry_z", DEFAULT_ENTRY_Z)),
            exit_z=float(raw.get("exit_z", DEFAULT_EXIT_Z)),
            top_n=int(raw.get("top_n", DEFAULT_TOP_N)),
            volume_window=int(raw.get("volume_window", DEFAULT_VOLUME_WINDOW)),
            min_volume_ratio=float(raw.get("min_volume_ratio", DEFAULT_MIN_VOLUME_RATIO)),
            use_rsi_filter=bool(raw.get("use_rsi_filter", DEFAULT_USE_RSI_FILTER)),
            rsi_window=int(raw.get("rsi_window", DEFAULT_RSI_WINDOW)),
            rsi_oversold=float(raw.get("rsi_oversold", DEFAULT_RSI_OVERSOLD)),
            use_adf_filter=bool(raw.get("use_adf_filter", DEFAULT_USE_ADF_FILTER)),
            adf_window=int(raw.get("adf_window", DEFAULT_ADF_WINDOW)),
            adf_pvalue_max=float(raw.get("adf_pvalue_max", DEFAULT_ADF_PVALUE_MAX)),
            market_filter_window=int(raw.get("market_filter_window", DEFAULT_MARKET_FILTER_WINDOW)),
            volatility_window=int(raw.get("volatility_window", DEFAULT_VOLATILITY_WINDOW)),
            target_annual_vol=float(raw.get("target_annual_vol", DEFAULT_TARGET_ANNUAL_VOL)),
            max_gross_exposure=float(raw.get("max_gross_exposure", DEFAULT_MAX_GROSS_EXPOSURE)),
        )

    def validate(self) -> None:
        validate_mean_reversion_params(
            mr_window=self.mr_window,
            entry_z=self.entry_z,
            exit_z=self.exit_z,
            top_n=self.top_n,
            volume_window=self.volume_window,
            min_volume_ratio=self.min_volume_ratio,
            use_rsi_filter=self.use_rsi_filter,
            rsi_window=self.rsi_window,
            rsi_oversold=self.rsi_oversold,
            use_adf_filter=self.use_adf_filter,
            adf_window=self.adf_window,
            adf_pvalue_max=self.adf_pvalue_max,
            market_filter_window=self.market_filter_window,
            volatility_window=self.volatility_window,
            target_annual_vol=self.target_annual_vol,
            max_gross_exposure=self.max_gross_exposure,
        )

    def required_warmup_bars(self) -> int:
        return required_mean_reversion_warmup_bars(params=self)


@dataclass(frozen=True)
class MeanReversionSignal:
    completed_trade_date: Any
    target_codes: tuple[str, ...]
    target_weights: dict[str, float]
    gross_exposure: float
    market_is_risk_on: bool
    candidate_codes: tuple[str, ...]
    least_preferred_code: str | None
    recommendation_reason: str
    least_preferred_reason: str


def compute_price_zscore(close: pd.Series, window: int) -> pd.Series:
    ma = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std()
    zscore = (close - ma) / std
    return pd.to_numeric(zscore, errors="coerce")


def compute_rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return pd.to_numeric(rsi, errors="coerce")


def compute_adf_pvalue(series: pd.Series) -> float | None:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 20:
        return None
    try:
        from statsmodels.tsa.stattools import adfuller
    except Exception:
        return None
    try:
        result = adfuller(clean, autolag="AIC")
    except Exception:
        return None
    return float(result[1])


def validate_mean_reversion_params(
    *,
    mr_window: int,
    entry_z: float,
    exit_z: float,
    top_n: int,
    volume_window: int,
    min_volume_ratio: float,
    use_rsi_filter: bool,
    rsi_window: int,
    rsi_oversold: float,
    use_adf_filter: bool,
    adf_window: int,
    adf_pvalue_max: float,
    market_filter_window: int,
    volatility_window: int,
    target_annual_vol: float,
    max_gross_exposure: float,
) -> None:
    if mr_window <= 1:
        raise ValueError("mr-window must be > 1")
    if entry_z <= 0:
        raise ValueError("entry-z must be positive")
    if exit_z < 0:
        raise ValueError("exit-z must be non-negative")
    if exit_z > entry_z:
        raise ValueError("exit-z must be <= entry-z")
    if top_n <= 0:
        raise ValueError("top-n must be positive")
    validate_volume_filter(volume_window, min_volume_ratio)
    if use_rsi_filter:
        if rsi_window <= 1:
            raise ValueError("rsi-window must be > 1")
        if not 0 < rsi_oversold < 50:
            raise ValueError("rsi-oversold must be within (0, 50)")
    if use_adf_filter:
        if adf_window < 20:
            raise ValueError("adf-window must be >= 20")
        if not 0 < adf_pvalue_max < 1:
            raise ValueError("adf-pvalue-max must be within (0, 1)")
    if market_filter_window <= 0:
        raise ValueError("market-filter-window must be positive")
    if volatility_window <= 1:
        raise ValueError("volatility-window must be > 1")
    if target_annual_vol <= 0:
        raise ValueError("target-annual-vol must be positive")
    if max_gross_exposure < 1:
        raise ValueError("max-gross-exposure must be >= 1")


def required_mean_reversion_signal_bars(*, params: MeanReversionParams) -> int:
    windows = [
        params.mr_window,
        params.volume_window + 1,
        params.market_filter_window,
        params.volatility_window + 1,
    ]
    if params.use_rsi_filter:
        windows.append(params.rsi_window + 1)
    if params.use_adf_filter:
        windows.append(params.adf_window)
    return max(windows)


def required_mean_reversion_warmup_bars(*, params: MeanReversionParams) -> int:
    return max(required_mean_reversion_signal_bars(params=params), 30) + 5


def _format_float(value: float | None, fmt: str, missing: str = "n/a") -> str:
    if value is None or pd.isna(value):
        return missing
    return format(value, fmt)


def _build_recommendation_reason(
    *,
    target_codes: tuple[str, ...],
    candidate_codes: tuple[str, ...],
    lead_zscore: float | None,
    lead_rsi: float | None,
    market_is_risk_on: bool,
    pool_close: float,
    pool_ma: float,
    params: MeanReversionParams,
) -> str:
    if target_codes:
        leader = target_codes[0]
        rsi_clause = (
            f"，RSI={_format_float(lead_rsi, '.1f')}"
            if params.use_rsi_filter
            else ""
        )
        return (
            f"{leader} 偏离均值最明显(z={_format_float(lead_zscore, '.2f')}{rsi_clause})，"
            f"触发均值回归入场条件(入场阈值 z<=-{params.entry_z:.2f}，退出阈值 z>=-{params.exit_z:.2f})。"
        )
    if candidate_codes and not market_is_risk_on:
        return (
            f"候选标的已出现超跌，但股票池均值 {pool_close:.2f} 低于 "
            f"{params.market_filter_window} 日均线 {pool_ma:.2f}，当前保持 CASH。"
        )
    return "当前无标的满足均值回归入场条件，建议保持 CASH。"


def _build_least_preferred_reason(
    *,
    code: str | None,
    zscore: float | None,
    rsi: float | None,
    params: MeanReversionParams,
) -> str:
    if not code:
        return "无可用标的可评估。"
    base = f"{code} 与均值偏离最不利(z={_format_float(zscore, '.2f')})"
    if params.use_rsi_filter and rsi is not None and not pd.isna(rsi):
        return f"{base}，且 RSI={rsi:.1f} 未处于超卖区。"
    return base + "。"


def build_mean_reversion_signal(
    prices: pd.DataFrame,
    volumes: pd.DataFrame,
    *,
    params: MeanReversionParams | None = None,
    mr_window: int = DEFAULT_MR_WINDOW,
    entry_z: float = DEFAULT_ENTRY_Z,
    exit_z: float = DEFAULT_EXIT_Z,
    top_n: int = DEFAULT_TOP_N,
    volume_window: int = DEFAULT_VOLUME_WINDOW,
    min_volume_ratio: float = DEFAULT_MIN_VOLUME_RATIO,
    use_rsi_filter: bool = DEFAULT_USE_RSI_FILTER,
    rsi_window: int = DEFAULT_RSI_WINDOW,
    rsi_oversold: float = DEFAULT_RSI_OVERSOLD,
    use_adf_filter: bool = DEFAULT_USE_ADF_FILTER,
    adf_window: int = DEFAULT_ADF_WINDOW,
    adf_pvalue_max: float = DEFAULT_ADF_PVALUE_MAX,
    market_filter_window: int = DEFAULT_MARKET_FILTER_WINDOW,
    volatility_window: int = DEFAULT_VOLATILITY_WINDOW,
    target_annual_vol: float = DEFAULT_TARGET_ANNUAL_VOL,
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE,
) -> MeanReversionSignal | None:
    resolved = params or MeanReversionParams(
        mr_window=mr_window,
        entry_z=entry_z,
        exit_z=exit_z,
        top_n=top_n,
        volume_window=volume_window,
        min_volume_ratio=min_volume_ratio,
        use_rsi_filter=use_rsi_filter,
        rsi_window=rsi_window,
        rsi_oversold=rsi_oversold,
        use_adf_filter=use_adf_filter,
        adf_window=adf_window,
        adf_pvalue_max=adf_pvalue_max,
        market_filter_window=market_filter_window,
        volatility_window=volatility_window,
        target_annual_vol=target_annual_vol,
        max_gross_exposure=max_gross_exposure,
    )
    resolved.validate()

    if prices.empty or volumes.empty:
        return None
    if not prices.index.equals(volumes.index) or not prices.columns.equals(volumes.columns):
        raise ValueError("prices and volumes must share the same index and columns")

    required_bars = required_mean_reversion_signal_bars(params=resolved)
    if len(prices.index) < required_bars:
        return None

    zscores = prices.apply(lambda col: compute_price_zscore(col, resolved.mr_window))
    relative_volume = volumes.apply(lambda col: compute_relative_volume(col, resolved.volume_window))
    rsi_frame = prices.apply(lambda col: compute_rsi(col, resolved.rsi_window)) if resolved.use_rsi_filter else None

    latest_index = -1
    latest_date = prices.index[latest_index]
    zrow = zscores.iloc[latest_index]
    volrow = relative_volume.iloc[latest_index]
    rsirow = rsi_frame.iloc[latest_index] if rsi_frame is not None else pd.Series(index=prices.columns, dtype=float)

    pool_close = prices.mean(axis=1)
    pool_ma = pool_close.rolling(window=resolved.market_filter_window, min_periods=resolved.market_filter_window).mean()
    market_is_risk_on = bool(pd.notna(pool_ma.iloc[latest_index]) and pool_close.iloc[latest_index] >= pool_ma.iloc[latest_index])

    candidate_scores: dict[str, tuple[float, float]] = {}
    for code in prices.columns:
        z = zrow.get(code)
        v = volrow.get(code)
        if pd.isna(z) or pd.isna(v):
            continue
        if z > -resolved.entry_z:
            continue
        if v < resolved.min_volume_ratio:
            continue
        if resolved.use_rsi_filter:
            rsi_value = rsirow.get(code)
            if pd.isna(rsi_value) or float(rsi_value) > resolved.rsi_oversold:
                continue
        if resolved.use_adf_filter:
            window_slice = prices[code].iloc[-resolved.adf_window:]
            pvalue = compute_adf_pvalue(window_slice)
            if pvalue is None or pvalue > resolved.adf_pvalue_max:
                continue
        candidate_scores[code] = (float(z), float(v))

    ranked_candidates = sorted(candidate_scores.items(), key=lambda kv: (kv[1][0], -kv[1][1]))
    candidate_codes = tuple(code for code, _ in ranked_candidates)
    target_codes = candidate_codes[: min(resolved.top_n, len(candidate_codes))] if market_is_risk_on else ()

    daily_pool_returns = pool_close.pct_change()
    realized_daily_vol = daily_pool_returns.rolling(
        window=resolved.volatility_window,
        min_periods=resolved.volatility_window,
    ).std()
    gross_exposure = 0.0
    if target_codes:
        annualized_vol = float(realized_daily_vol.iloc[latest_index] * (252**0.5)) if pd.notna(realized_daily_vol.iloc[latest_index]) else 0.0
        vol_multiplier = min(1.0, resolved.target_annual_vol / annualized_vol) if annualized_vol > 0 else 1.0
        gross_exposure = float(vol_multiplier * resolved.max_gross_exposure)

    weight_per_code = gross_exposure / len(target_codes) if target_codes else 0.0

    least_code = None
    least_z = None
    least_rsi = None
    valid_z = zrow.dropna()
    if not valid_z.empty:
        least_code = valid_z.sort_values(ascending=False).index[0]
        least_z = float(valid_z.loc[least_code])
        if resolved.use_rsi_filter and least_code in rsirow.index and pd.notna(rsirow.loc[least_code]):
            least_rsi = float(rsirow.loc[least_code])

    lead = candidate_codes[0] if candidate_codes else None
    lead_z = float(zrow.loc[lead]) if lead in zrow.index and pd.notna(zrow.loc[lead]) else None
    lead_rsi = float(rsirow.loc[lead]) if lead in rsirow.index and pd.notna(rsirow.loc[lead]) else None

    return MeanReversionSignal(
        completed_trade_date=latest_date,
        target_codes=target_codes,
        target_weights={code: weight_per_code for code in target_codes},
        gross_exposure=gross_exposure,
        market_is_risk_on=market_is_risk_on,
        candidate_codes=candidate_codes,
        least_preferred_code=least_code,
        recommendation_reason=_build_recommendation_reason(
            target_codes=target_codes,
            candidate_codes=candidate_codes,
            lead_zscore=lead_z,
            lead_rsi=lead_rsi,
            market_is_risk_on=market_is_risk_on,
            pool_close=float(pool_close.iloc[latest_index]),
            pool_ma=float(pool_ma.iloc[latest_index]) if pd.notna(pool_ma.iloc[latest_index]) else float("nan"),
            params=resolved,
        ),
        least_preferred_reason=_build_least_preferred_reason(
            code=least_code,
            zscore=least_z,
            rsi=least_rsi,
            params=resolved,
        ),
    )
