from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tradesignal.config import load_strategy_config


class StrategyNameConfigTests(unittest.TestCase):
    def test_accepts_mean_reversion_strategy_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strategy.json"
            path.write_text(json.dumps({"name": "mean_reversion", "params": {"entry_z": 1.2}}), encoding="utf-8")
            loaded = load_strategy_config(path)

        self.assertEqual(loaded.name, "mean_reversion")
        self.assertEqual(loaded.params.get("entry_z"), 1.2)

    def test_rejects_unknown_strategy_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strategy.json"
            path.write_text(json.dumps({"name": "unknown", "params": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_strategy_config(path)

    def test_requires_explicit_strategy_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strategy.json"
            path.write_text(json.dumps({"params": {"top_n": 2}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_strategy_config(path)


if __name__ == "__main__":
    unittest.main()
