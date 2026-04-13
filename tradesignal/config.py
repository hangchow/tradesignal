from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_STRATEGY_CONFIG_RELATIVE_PATH = Path("config/strategy_config.default.json")
DEFAULT_STRATEGY_CONFIG_PATH = (Path(__file__).resolve().parent.parent / DEFAULT_STRATEGY_CONFIG_RELATIVE_PATH).resolve()
SUPPORTED_STRATEGY_NAMES = frozenset({"dual_momentum", "mean_reversion"})


@dataclass(frozen=True)
class EmailNotificationConfig:
    enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    username: str | None = None
    password: str | None = None
    password_env: str | None = None
    from_address: str | None = None
    from_name: str | None = None
    to_addresses: tuple[str, ...] = field(default_factory=tuple)
    subject_prefix: str = "[tradesignal]"
    use_tls: bool = True
    use_ssl: bool = False


@dataclass(frozen=True)
class NotificationConfig:
    email: EmailNotificationConfig = field(default_factory=EmailNotificationConfig)


@dataclass(frozen=True)
class StrategyConfig:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StockPoolConfig:
    codes: tuple[str, ...]
    market: str
    data_root: Path
    code_names: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AppConfig:
    stock_pool: StockPoolConfig
    notification: NotificationConfig = field(default_factory=NotificationConfig)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    notification = _parse_notification_config(payload.get("notification", {}))

    stock_pool_raw = payload.get("stock_pool")
    if not isinstance(stock_pool_raw, dict):
        raise ValueError("stock_pool must be an object")
    codes, code_names = _parse_stocks(stock_pool_raw, prefix="stock_pool")
    market = _infer_market(codes)

    data_root_raw = str(stock_pool_raw.get("data_root", "kline_day")).strip()
    if not data_root_raw:
        raise ValueError("stock_pool.data_root must not be empty")
    data_root = Path(data_root_raw)
    if not data_root.is_absolute():
        data_root = (config_path.parent / data_root).resolve()

    return AppConfig(
        stock_pool=StockPoolConfig(codes=codes, market=market, data_root=data_root, code_names=code_names),
        notification=notification,
    )


def load_notification_config(path: str | Path) -> NotificationConfig:
    config_path = Path(path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return _parse_notification_config(payload.get("notification", {}))


def load_strategy_config(path: str | Path) -> StrategyConfig:
    strategy_config_path = Path(path)
    payload = json.loads(strategy_config_path.read_text(encoding="utf-8"))
    return _parse_strategy_config(payload, prefix="strategy config")


def load_default_strategy_config() -> StrategyConfig:
    return load_strategy_config(DEFAULT_STRATEGY_CONFIG_PATH)


def _parse_strategy_config(payload: object, *, prefix: str = "strategy") -> StrategyConfig:
    if payload is None:
        raise ValueError(f"{prefix} must be an object")
    if not isinstance(payload, dict):
        raise ValueError(f"{prefix} must be an object")

    strategy_name = str(payload.get("name", "")).strip()
    if strategy_name not in SUPPORTED_STRATEGY_NAMES:
        raise ValueError(f"{prefix}.name must be one of: {', '.join(sorted(SUPPORTED_STRATEGY_NAMES))}")

    strategy_params = payload.get("params", {})
    if strategy_params is None:
        strategy_params = {}
    if not isinstance(strategy_params, dict):
        raise ValueError(f"{prefix}.params must be an object")
    return StrategyConfig(name=strategy_name, params=dict(strategy_params))


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_stocks(stock_pool_raw: dict[str, Any], *, prefix: str) -> tuple[tuple[str, ...], dict[str, str]]:
    stocks_raw = stock_pool_raw.get("stocks")
    if not isinstance(stocks_raw, list) or not stocks_raw:
        raise ValueError(f"{prefix}.stocks must be a non-empty array")
    codes: list[str] = []
    code_names: dict[str, str] = {}
    for index, item in enumerate(stocks_raw):
        item_prefix = f"{prefix}.stocks[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_prefix} must be an object")
        code = _normalize_code(str(item.get("code", "")).strip())
        if not code:
            raise ValueError(f"{item_prefix}.code must be non-empty")
        codes.append(code)
        cn_name = str(item.get("cn_name", "")).strip()
        if cn_name:
            code_names[code] = cn_name
    return tuple(codes), code_names


def _normalize_code(code: str) -> str:
    upper = code.strip().upper()
    if upper.startswith("HK.") and upper[3:].isdigit():
        return f"HK.{int(upper[3:]):05d}"
    if upper.isdigit():
        return f"HK.{int(upper):05d}"
    return upper


def _infer_market(codes: tuple[str, ...]) -> str:
    prefixes = {"US" if code.startswith("US.") else "HK" if code.startswith("HK.") else "UNKNOWN" for code in codes}
    if prefixes == {"US"}:
        return "US"
    if prefixes == {"HK"}:
        return "HK"
    if prefixes == {"US", "HK"}:
        raise ValueError("stock_pool.codes must belong to a single market; found both US.* and HK.* codes")
    raise ValueError("stock_pool.codes only support US.* or HK.* codes")


def _parse_notification_config(notification_raw: object) -> NotificationConfig:
    if notification_raw is None:
        notification_raw = {}
    if not isinstance(notification_raw, dict):
        raise ValueError("notification must be an object")
    email_raw = notification_raw.get("email", {})
    if email_raw is None:
        email_raw = {}
    if not isinstance(email_raw, dict):
        raise ValueError("notification.email must be an object")

    to_raw = email_raw.get("to", [])
    if to_raw is None:
        to_raw = []
    if not isinstance(to_raw, list):
        raise ValueError("notification.email.to must be an array")
    to_addresses = tuple(str(value).strip() for value in to_raw if str(value).strip())

    email = EmailNotificationConfig(
        enabled=bool(email_raw.get("enabled", False)),
        smtp_host=_optional_string(email_raw.get("smtp_host")),
        smtp_port=int(email_raw.get("smtp_port", 587)),
        username=_optional_string(email_raw.get("username")),
        password=_optional_string(email_raw.get("password")),
        password_env=_optional_string(email_raw.get("password_env")),
        from_address=_optional_string(email_raw.get("from")),
        from_name=_optional_string(email_raw.get("from_name")),
        to_addresses=to_addresses,
        subject_prefix=str(email_raw.get("subject_prefix", "[tradesignal]")).strip() or "[tradesignal]",
        use_tls=bool(email_raw.get("use_tls", True)),
        use_ssl=bool(email_raw.get("use_ssl", False)),
    )
    return NotificationConfig(email=email)
