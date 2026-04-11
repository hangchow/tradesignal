from __future__ import annotations

import unittest
from pathlib import Path

from tradesignal.cli import build_notification_message
from tradesignal.config import (
    AppConfig,
    EmailNotificationConfig,
    NotificationConfig,
    StockPoolConfig,
    StrategyConfig,
)
from tradesignal.strategy.dual_momentum import DualMomentumSignal


class NotificationMessageTests(unittest.TestCase):
    def test_candidate_summary_excludes_target_codes(self) -> None:
        config = AppConfig(
            stock_pool=StockPoolConfig(
                codes=("US.MU", "US.AVGO"),
                market="US",
                data_root=Path("/tmp"),
                code_names={"US.MU": "美光科技", "US.AVGO": "博通"},
            ),
            notification=NotificationConfig(
                email=EmailNotificationConfig(subject_prefix="[test]")
            ),
        )
        strategy = StrategyConfig(name="dual_momentum")
        signal = DualMomentumSignal(
            completed_trade_date="2026-04-10",
            target_codes=("US.MU",),
            target_weights={"US.MU": 1.0},
            gross_exposure=1.0,
            market_is_risk_on=True,
            candidate_codes=("US.MU", "US.AVGO"),
            least_preferred_code="US.AVGO",
            recommendation_reason="reason",
            least_preferred_reason="least",
        )

        _, body, html_body = build_notification_message(config, strategy, signal)

        self.assertIn("推荐目标：US.MU(美光科技)", body)
        self.assertIn("备选候选：US.AVGO(博通)", body)
        self.assertNotIn("备选候选：US.MU(美光科技)", body)
        self.assertIn("US.AVGO(博通)", html_body)


if __name__ == "__main__":
    unittest.main()
