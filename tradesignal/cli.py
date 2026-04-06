from __future__ import annotations

import argparse
from pathlib import Path

from .config import AppConfig, load_config
from .data import load_daily_data
from .emailer import send_email_notification
from .strategy.dual_momentum import DualMomentumParams, build_dual_momentum_signal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run dual momentum and optionally send an email notification.")
    parser.add_argument("--config", required=True, help="Path to JSON config file.")
    parser.add_argument("--no-email", action="store_true", help="Suppress email even if enabled in config.")
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    params = DualMomentumParams.from_mapping(config.strategy.params)
    params.validate()

    prices, volumes = load_daily_data(config.stock_pool.data_root, config.stock_pool.codes)
    signal = build_dual_momentum_signal(prices, volumes, params=params)
    if signal is None:
        raise SystemExit(
            "Signal unavailable: not enough completed daily bars for the configured windows. "
            f"Required warmup bars: {params.required_warmup_bars()}."
        )

    subject, body = build_notification_message(config, signal)
    print(body)

    if not args.no_email and config.notification.email.enabled:
        send_email_notification(config.notification.email, subject=subject, body=body)
        print(f"EMAIL_SENT to={','.join(config.notification.email.to_addresses)} subject={subject}")

    return 0


def build_notification_message(config: AppConfig, signal) -> tuple[str, str]:
    target_codes = signal.target_codes
    candidate_codes = signal.candidate_codes
    target_summary = "、".join(target_codes) if target_codes else "CASH"
    candidate_summary = "、".join(candidate_codes) if candidate_codes else "无"
    risk_state = "risk_on" if signal.market_is_risk_on else "risk_off"

    subject_core = f"{signal.completed_trade_date} dual_momentum 推荐：{target_summary}"
    subject = f"{config.notification.email.subject_prefix} {subject_core}".strip()
    body = "\n".join(
        [
            "tradesignal",
            "",
            "策略：dual_momentum",
            f"已完成交易日：{signal.completed_trade_date}",
            f"当前股票池：{', '.join(config.stock_pool.codes)}",
            f"推荐目标：{target_summary}",
            f"备选候选：{candidate_summary}",
            f"风险状态：{risk_state}",
            f"总仓位倍率：{signal.gross_exposure:.4f}",
        ]
    )
    return subject, body
