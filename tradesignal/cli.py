from __future__ import annotations

import argparse
import traceback
from html import escape
from pathlib import Path

from .config import (
    DEFAULT_STRATEGY_CONFIG_RELATIVE_PATH,
    AppConfig,
    StrategyConfig,
    load_config,
    load_default_strategy_config,
    load_notification_config,
    load_strategy_config,
)
from .data import load_daily_data
from .emailer import send_email_notification, write_email_preview
from .strategy.dual_momentum import DualMomentumParams, build_dual_momentum_signal
from .yfinance_day import refresh_daily_data

DEFAULT_CODE_NAMES = {
    "HK.00005": "汇丰控股",
    "HK.00700": "腾讯",
    "HK.01211": "比亚迪股份",
    "HK.01810": "小米集团",
    "HK.03690": "美团",
    "HK.03750": "药明康德",
    "HK.09988": "阿里巴巴",
    "HK.00981": "中芯国际",
}


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
    config_path = Path(args.config)
    notification = None
    try:
        notification = load_notification_config(config_path)
    except Exception:
        notification = None

    try:
        return _run(args)
    except Exception as exc:
        _notify_error(args, config_path, notification, exc)
        return 1


def _run(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    strategy = load_default_strategy_config()
    if args.strategy_config:
        strategy = load_strategy_config(Path(args.strategy_config), base=strategy)
    params = DualMomentumParams.from_mapping(strategy.params)
    params.validate()

    print(
        f"RUNNING strategy={strategy.name} market={config.stock_pool.market} codes={len(config.stock_pool.codes)} data_root={config.stock_pool.data_root}",
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

    subject, body, html_body = build_notification_message(config, strategy, signal)
    print(body, flush=True)
    preview_path = write_email_preview(config.notification.email, subject=subject, body=body, html_body=html_body)
    print(f"EMAIL_PREVIEW path={preview_path}", flush=True)

    if not args.no_email and config.notification.email.enabled:
        send_email_notification(config.notification.email, subject=subject, body=body, html_body=html_body)
        print(f"EMAIL_SENT to={','.join(config.notification.email.to_addresses)} subject={subject}", flush=True)

    return 0


def _notify_error(args: argparse.Namespace, config_path: Path, notification, exc: Exception) -> None:
    details = "".join(traceback.format_exception(exc))
    print(details, flush=True)

    if args.no_email or notification is None or not notification.email.enabled:
        return

    subject = f"{notification.email.subject_prefix} tradesignal 运行失败".strip()
    body = "\n".join(
        [
            "tradesignal",
            "",
            "运行状态：failed",
            f"配置文件：{config_path}",
            f"错误类型：{type(exc).__name__}",
            f"错误信息：{exc}",
            "",
            "Traceback:",
            details.strip(),
        ]
    )
    html_body = build_notification_html(
        title=subject,
        strategy_name="N/A",
        completed_trade_date="N/A",
        stock_pool="N/A",
        target_summary="N/A",
        candidate_summary="N/A",
        least_preferred_summary="N/A",
        risk_state="error",
        gross_exposure="0.0000",
        recommendation_reason=f"运行失败：{type(exc).__name__}: {exc}",
        least_preferred_reason="请检查配置与日志后重试。",
    )
    preview_path = write_email_preview(notification.email, subject=subject, body=body, html_body=html_body)
    print(f"EMAIL_PREVIEW path={preview_path}", flush=True)
    send_email_notification(notification.email, subject=subject, body=body, html_body=html_body)
    print(f"EMAIL_SENT to={','.join(notification.email.to_addresses)} subject={subject}", flush=True)


def build_notification_message(config: AppConfig, strategy: StrategyConfig, signal) -> tuple[str, str, str]:
    target_codes = signal.target_codes
    candidate_codes = signal.candidate_codes
    target_summary = _format_code_summary(config, target_codes, empty_value="CASH")
    candidate_summary = _format_code_summary(config, candidate_codes, empty_value="无")
    subject_target_summary = _format_name_summary(config, target_codes, empty_value="CASH")
    risk_state = "risk_on" if signal.market_is_risk_on else "risk_off"
    least_preferred_summary = _format_single_code(config, signal.least_preferred_code, empty_value="无")

    subject_core = f"{signal.completed_trade_date} {strategy.name} 推荐：{subject_target_summary}"
    subject = f"{config.notification.email.subject_prefix} {subject_core}".strip()
    body = "\n".join(
        [
            "tradesignal",
            "",
            f"策略：{strategy.name}",
            f"已完成交易日：{signal.completed_trade_date}",
            f"当前股票池：{_format_code_summary(config, config.stock_pool.codes, separator=', ', empty_value='无')}",
            f"推荐目标：{target_summary}",
            f"备选候选：{candidate_summary}",
            f"最不推荐：{least_preferred_summary}",
            f"风险状态：{risk_state}",
            f"总仓位倍率：{signal.gross_exposure:.4f}",
            f"推荐理由：{signal.recommendation_reason}",
            f"不推荐理由：{signal.least_preferred_reason}",
        ]
    )
    html_body = build_notification_html(
        title=subject,
        strategy_name=strategy.name,
        completed_trade_date=str(signal.completed_trade_date),
        stock_pool=_format_code_summary(config, config.stock_pool.codes, separator=", ", empty_value="无"),
        target_summary=target_summary,
        candidate_summary=candidate_summary,
        least_preferred_summary=least_preferred_summary,
        risk_state=risk_state,
        gross_exposure=f"{signal.gross_exposure:.4f}",
        recommendation_reason=signal.recommendation_reason,
        least_preferred_reason=signal.least_preferred_reason,
    )
    return subject, body, html_body


def _format_code_summary(config: AppConfig, codes: tuple[str, ...] | list[str], *, separator: str = "、", empty_value: str) -> str:
    if not codes:
        return empty_value
    return separator.join(_format_code(config, code) for code in codes)


def _format_single_code(config: AppConfig, code: str | None, *, empty_value: str) -> str:
    if not code:
        return empty_value
    return _format_code(config, code)


def _format_name_summary(config: AppConfig, codes: tuple[str, ...] | list[str], *, empty_value: str) -> str:
    if not codes:
        return empty_value
    return "、".join(_format_name(config, code) for code in codes)


def _format_code(config: AppConfig, code: str) -> str:
    code_name = _lookup_code_name(config, code)
    if not code_name:
        return code
    return f"{code}({code_name})"


def _format_name(config: AppConfig, code: str) -> str:
    return _lookup_code_name(config, code) or code


def _lookup_code_name(config: AppConfig, code: str) -> str | None:
    return config.stock_pool.code_names.get(code) or DEFAULT_CODE_NAMES.get(code)


def build_notification_html(
    *,
    title: str,
    strategy_name: str,
    completed_trade_date: str,
    stock_pool: str,
    target_summary: str,
    candidate_summary: str,
    least_preferred_summary: str,
    risk_state: str,
    gross_exposure: str,
    recommendation_reason: str,
    least_preferred_reason: str,
) -> str:
    metrics = [
        ("策略", strategy_name),
        ("已完成交易日", completed_trade_date),
        ("当前股票池", stock_pool),
        ("推荐目标", target_summary),
        ("备选候选", candidate_summary),
        ("最不推荐", least_preferred_summary),
        ("风险状态", risk_state),
        ("总仓位倍率", gross_exposure),
    ]
    metric_rows = "\n".join(
        [
            (
                '          <div class="metric-row">'
                f'<div class="metric-label">{escape(label)}</div>'
                f'<div class="metric-value">{escape(value)}</div>'
                "</div>"
            )
            for label, value in metrics
        ]
    )
    return "\n".join(
        [
            '      <section class="mail-root">',
            '        <div class="hero">',
            f'          <h1>{escape(title)}</h1>',
            "        </div>",
            '        <div class="content">',
            '          <section class="panel">',
            '            <h2>信号摘要</h2>',
            f"{metric_rows}",
            "          </section>",
            '          <section class="panel">',
            '            <h2>原因说明</h2>',
            '            <div class="reason-block">',
            '              <div class="reason-title">推荐理由</div>',
            f'              <p>{escape(recommendation_reason)}</p>',
            "            </div>",
            '            <div class="reason-block alt">',
            '              <div class="reason-title">不推荐理由</div>',
            f'              <p>{escape(least_preferred_reason)}</p>',
            "            </div>",
            "          </section>",
            '          <div class="footer-note">本邮件由 tradesignal 自动生成。</div>',
            "        </div>",
            "      </section>",
            "      <style>",
            "        .mail-root { background: #fffdf8; }",
            "        .hero { padding: 28px 28px 20px; background: radial-gradient(circle at top left, #f7e6b5, #efe1cc 45%, #f8f5ef 100%); border-bottom: 1px solid #eadfce; }",
            "        .hero h1 { margin: 14px 0 10px; font-size: 28px; line-height: 1.25; color: #1f2937; }",
            "        .hero-text { margin: 0; color: #5b6472; font-size: 15px; line-height: 1.7; }",
            "        .content { padding: 22px; }",
            "        .panel { margin-bottom: 18px; padding: 18px; background: #ffffff; border: 1px solid #ece3d5; border-radius: 16px; }",
            "        .panel h2 { margin: 0 0 14px; font-size: 17px; color: #2b3442; }",
            "        .metric-row { padding: 10px 0; border-bottom: 1px solid #f2ece2; }",
            "        .metric-row:last-child { border-bottom: 0; }",
            "        .metric-label { margin-bottom: 4px; font-size: 12px; font-weight: 700; color: #8a7352; letter-spacing: 0.04em; text-transform: uppercase; }",
            "        .metric-value { font-size: 15px; line-height: 1.6; color: #1f2937; word-break: break-word; }",
            "        .reason-block { padding: 14px 16px; border-radius: 14px; background: #f7f3ea; }",
            "        .reason-block.alt { margin-top: 12px; background: #f3efe8; }",
            "        .reason-title { margin-bottom: 8px; font-size: 13px; font-weight: 700; color: #6c5738; }",
            "        .reason-block p { margin: 0; font-size: 15px; line-height: 1.75; color: #334155; }",
            "        .footer-note { padding: 2px 4px 8px; color: #8a8f99; font-size: 12px; text-align: center; }",
            "        @media (max-width: 640px) { .hero { padding: 24px 20px 18px; } .hero h1 { font-size: 24px; } .content { padding: 16px; } .panel { padding: 16px; } }",
            "      </style>",
        ]
    )
