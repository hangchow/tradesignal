from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_STRATEGY_CONFIG_RELATIVE_PATH = Path("config/strategy_config.default.json")
DEFAULT_STRATEGY_CONFIG_PATH = (Path(__file__).resolve().parent.parent / DEFAULT_STRATEGY_CONFIG_RELATIVE_PATH).resolve()


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
    data_root: Path


@dataclass(frozen=True)
class AppConfig:
    stock_pool: StockPoolConfig
    notification: NotificationConfig = field(default_factory=NotificationConfig)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    stock_pool_raw = payload.get("stock_pool")
    if not isinstance(stock_pool_raw, dict):
        raise ValueError("stock_pool must be an object")
    codes_raw = stock_pool_raw.get("codes")
    if not isinstance(codes_raw, list) or not codes_raw:
        raise ValueError("stock_pool.codes must be a non-empty array")
    codes = tuple(str(code).strip().upper() for code in codes_raw if str(code).strip())
    if not codes:
        raise ValueError("stock_pool.codes must contain at least one non-empty code")

    data_root_raw = str(stock_pool_raw.get("data_root", "kline_day")).strip()
    if not data_root_raw:
        raise ValueError("stock_pool.data_root must not be empty")
    data_root = Path(data_root_raw)
    if not data_root.is_absolute():
        data_root = (config_path.parent / data_root).resolve()

    notification_raw = payload.get("notification", {})
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

    return AppConfig(
        stock_pool=StockPoolConfig(codes=codes, data_root=data_root),
        notification=NotificationConfig(email=email),
    )


def load_strategy_config(path: str | Path, *, base: StrategyConfig | None = None) -> StrategyConfig:
    strategy_config_path = Path(path)
    payload = json.loads(strategy_config_path.read_text(encoding="utf-8"))
    if base is None:
        return _parse_strategy_config(payload, prefix="strategy config")
    return _merge_strategy_config(base, payload, prefix="strategy config")


def load_default_strategy_config() -> StrategyConfig:
    return load_strategy_config(DEFAULT_STRATEGY_CONFIG_PATH)


def _parse_strategy_config(payload: object, *, prefix: str = "strategy") -> StrategyConfig:
    if payload is None:
        raise ValueError(f"{prefix} must be an object")
    if not isinstance(payload, dict):
        raise ValueError(f"{prefix} must be an object")

    strategy_name = str(payload.get("name", "")).strip()
    if strategy_name != "dual_momentum":
        raise ValueError(f"{prefix}.name must be dual_momentum")

    strategy_params = payload.get("params", {})
    if strategy_params is None:
        strategy_params = {}
    if not isinstance(strategy_params, dict):
        raise ValueError(f"{prefix}.params must be an object")
    return StrategyConfig(name=strategy_name, params=dict(strategy_params))


def _merge_strategy_config(base: StrategyConfig, payload: object, *, prefix: str = "strategy") -> StrategyConfig:
    if payload is None:
        raise ValueError(f"{prefix} must be an object")
    if not isinstance(payload, dict):
        raise ValueError(f"{prefix} must be an object")

    strategy_name = str(payload.get("name", base.name)).strip()
    if strategy_name != "dual_momentum":
        raise ValueError(f"{prefix}.name must be dual_momentum")

    override_params = payload.get("params", {})
    if override_params is None:
        override_params = {}
    if not isinstance(override_params, dict):
        raise ValueError(f"{prefix}.params must be an object")

    merged_params = dict(base.params)
    merged_params.update(override_params)
    return StrategyConfig(name=strategy_name, params=merged_params)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
