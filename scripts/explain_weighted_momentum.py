from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tradesignal.config import load_config, load_default_strategy_config, load_strategy_config
from tradesignal.data import load_daily_data
from tradesignal.strategy.dual_momentum import (
    MAX_VOLUME_BOOST_RATIO,
    DualMomentumParams,
    build_dual_momentum_signal,
    compute_volume_boost,
)
from tradesignal.strategy.volume import compute_relative_volume


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain weighted momentum with concrete intermediate numbers.")
    parser.add_argument("--config", required=True, help="Path to tradesignal config JSON.")
    parser.add_argument("--strategy-config", "--strategy_config", dest="strategy_config", help="Optional strategy config JSON.")
    parser.add_argument("--date", help="Trade date in YYYY-MM-DD. Defaults to the latest completed trade date.")
    parser.add_argument("--code", required=True, help="Ticker code in stock pool, e.g. US.GLD.")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    strategy = load_default_strategy_config()
    if args.strategy_config:
        strategy = load_strategy_config(Path(args.strategy_config), base=strategy)
    params = DualMomentumParams.from_mapping(strategy.params)
    params.validate()

    prices, volumes = load_daily_data(config.stock_pool.data_root, config.stock_pool.codes)
    latest_signal = build_dual_momentum_signal(prices, volumes, params=params)
    if latest_signal is None:
        raise SystemExit("latest signal unavailable: not enough completed daily bars for configured windows")

    trade_date = args.date or str(latest_signal.completed_trade_date)
    code = args.code

    if code not in prices.columns:
        raise SystemExit(f"code not found in stock pool: {code}")
    if trade_date not in prices.index.astype(str):
        raise SystemExit(f"date not found in loaded history: {trade_date}")

    use_long_lookback = params.long_lookback_weight > 0
    price_col = prices[code]
    volume_col = volumes[code]
    relative_volume_col = compute_relative_volume(volume_col, params.volume_window)
    boost_col = compute_volume_boost(relative_volume_col, params.min_volume_ratio)
    short_col = price_col.divide(price_col.shift(params.lookback_days)) - 1
    if use_long_lookback:
        long_col = price_col.divide(price_col.shift(params.long_lookback_days)) - 1
    else:
        long_col = short_col * 0.0
    blended_col = short_col * (1 - params.long_lookback_weight) + long_col * params.long_lookback_weight
    weighted_col = blended_col.where(blended_col > 0) * boost_col

    idx = price_col.index.astype(str).get_loc(trade_date)
    required_history = max(params.lookback_days, params.long_lookback_days if use_long_lookback else 0)
    if idx < required_history:
        raise SystemExit(
            "not enough history before target date for configured lookback windows: "
            f"need at least {required_history} bars, only found {idx}"
        )

    close_t = float(price_col.iloc[idx])
    close_short = float(price_col.iloc[idx - params.lookback_days])
    close_long = float(price_col.iloc[idx - params.long_lookback_days]) if use_long_lookback else None
    vol_t = float(volume_col.iloc[idx])
    vol_baseline = float(volume_col.shift(1).rolling(window=params.volume_window, min_periods=1).mean().iloc[idx])
    relative_volume = float(relative_volume_col.iloc[idx])
    boost = float(boost_col.iloc[idx])
    short_momentum = float(short_col.iloc[idx])
    long_momentum = float(long_col.iloc[idx])
    blended_momentum = float(blended_col.iloc[idx])
    weighted_momentum = float(weighted_col.iloc[idx])

    if (
        price_col.iloc[idx] != price_col.iloc[idx]
        or price_col.iloc[idx - params.lookback_days] != price_col.iloc[idx - params.lookback_days]
        or (
            use_long_lookback
            and price_col.iloc[idx - params.long_lookback_days] != price_col.iloc[idx - params.long_lookback_days]
        )
        or volume_col.iloc[idx] != volume_col.iloc[idx]
    ):
        raise SystemExit("input data contains NaN on required bars; cannot explain this date/code reliably")

    print(f"date={trade_date} code={code}")
    print("--- 输入数据 ---")
    print(f"当日收盘 = {close_t:.6f}")
    print(f"{params.lookback_days} 日前收盘 = {close_short:.6f}")
    if use_long_lookback and close_long is not None:
        print(f"{params.long_lookback_days} 日前收盘 = {close_long:.6f}")
    print(f"当日成交量 = {vol_t:.2f}")
    print(f"过去 {params.volume_window} 日均量(不含当日) = {vol_baseline:.2f}")
    print("--- 中间结果 ---")
    print(f"短周期动量 = {close_t:.6f} / {close_short:.6f} - 1 = {short_momentum:.8f} ({short_momentum * 100:.4f}%)")
    if use_long_lookback and close_long is not None:
        print(f"长周期动量 = {close_t:.6f} / {close_long:.6f} - 1 = {long_momentum:.8f} ({long_momentum * 100:.4f}%)")
        print(
            "综合动量 = "
            f"{short_momentum:.8f} * {1 - params.long_lookback_weight:.2f} + "
            f"{long_momentum:.8f} * {params.long_lookback_weight:.2f} = {blended_momentum:.8f} "
            f"({blended_momentum * 100:.4f}%)"
        )
    else:
        print(f"综合动量 = {short_momentum:.8f} * 1.00 = {blended_momentum:.8f} ({blended_momentum * 100:.4f}%)")
    print(f"量比 = {vol_t:.2f} / {vol_baseline:.2f} = {relative_volume:.8f}")
    if relative_volume >= params.min_volume_ratio:
        print(
            "量能加权因子 = "
            f"min({relative_volume:.8f}, {MAX_VOLUME_BOOST_RATIO:.8f}) / {params.min_volume_ratio:.2f} = {boost:.8f}"
        )
    else:
        print(
            "量能加权因子 = "
            f"1.0 (因为量比 {relative_volume:.8f} < 阈值 {params.min_volume_ratio:.2f}) = {boost:.8f}"
        )
    print("--- 最终结果 ---")
    print(f"加权动量(原始值) = {blended_momentum:.8f} * {boost:.8f} = {weighted_momentum:.8f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
