from __future__ import annotations

import argparse
from pathlib import Path

from .config import (
    DEFAULT_STRATEGY_CONFIG_RELATIVE_PATH,
    AppConfig,
    StrategyConfig,
    load_config,
    load_default_strategy_config,
    load_strategy_config,
)
from .data import load_daily_data
from .emailer import send_email_notification
from .polygon_day import refresh_daily_data
from .strategy.dual_momentum import DualMomentumParams, build_dual_momentum_signal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run dual momentum and optionally send an email notification.")
    parser.add_argument("--config", required=True, help="Path to JSON config file.")
    parser.add_argument(
        "--strategy-config",
        "--strategy_config",
        dest="strategy_config",
        help=(
            "Path to JSON strategy config override. "
            f"Matching params override defaults from {DEFAULT_STRATEGY_CONFIG_RELATIVE_PATH.as_posix()}."
        ),
    )
    parser.add_argument("--no-email", action="store_true", help="Suppress email even if enabled in config.")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip Polygon daily data refresh before loading local CSV files.")
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    strategy = load_default_strategy_config()
    if args.strategy_config:
        strategy = load_strategy_config(Path(args.strategy_config), base=strategy)
    params = DualMomentumParams.from_mapping(strategy.params)
    params.validate()

    print(
        f"RUNNING strategy={strategy.name} codes={len(config.stock_pool.codes)} data_root={config.stock_pool.data_root}",
        flush=True,
    )
    if not args.skip_fetch:
        refresh_daily_data(config.stock_pool.data_root, config.stock_pool.codes)
    prices, volumes = load_daily_data(config.stock_pool.data_root, config.stock_pool.codes)
    signal = build_dual_momentum_signal(prices, volumes, params=params)
    if signal is None:
        raise SystemExit(
            "Signal unavailable: not enough completed daily bars for the configured windows. "
            f"Required warmup bars: {params.required_warmup_bars()}."
        )

    subject, body = build_notification_message(config, strategy, signal)
    print(body, flush=True)

    if not args.no_email and config.notification.email.enabled:
        send_email_notification(config.notification.email, subject=subject, body=body)
        print(f"EMAIL_SENT to={','.join(config.notification.email.to_addresses)} subject={subject}", flush=True)

    return 0


def build_notification_message(config: AppConfig, strategy: StrategyConfig, signal) -> tuple[str, str]:
    target_codes = signal.target_codes
    candidate_codes = signal.candidate_codes
    target_summary = "、".join(target_codes) if target_codes else "CASH"
    candidate_summary = "、".join(candidate_codes) if candidate_codes else "无"
    risk_state = "risk_on" if signal.market_is_risk_on else "risk_off"
    least_preferred_summary = signal.least_preferred_code or "无"

    subject_core = f"{signal.completed_trade_date} {strategy.name} 推荐：{target_summary}"
    subject = f"{config.notification.email.subject_prefix} {subject_core}".strip()
    body = "\n".join(
        [
            "tradesignal",
            "",
            f"策略：{strategy.name}",
            f"已完成交易日：{signal.completed_trade_date}",
            f"当前股票池：{', '.join(config.stock_pool.codes)}",
            f"推荐目标：{target_summary}",
            f"备选候选：{candidate_summary}",
            f"最不推荐：{least_preferred_summary}",
            f"风险状态：{risk_state}",
            f"总仓位倍率：{signal.gross_exposure:.4f}",
            f"推荐理由：{signal.recommendation_reason}",
            f"不推荐理由：{signal.least_preferred_reason}",
        ]
    )
    return subject, body
