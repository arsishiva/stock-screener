import json
import tempfile
import unittest
from pathlib import Path

from stock_screener.user_data import (
    DEFAULT_USER_DATA,
    load_user_data,
    save_user_data,
)


class UserDataTests(unittest.TestCase):
    def test_missing_file_returns_empty_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            data, error = load_user_data(Path(directory) / "missing.json")

        self.assertIsNone(error)
        self.assertEqual(data, DEFAULT_USER_DATA)

    def test_save_and_load_preserves_watchlist_portfolio_and_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "user_data.json"
            original = {
                "watchlist": ["AAPL", "NVDA"],
                "portfolio": [{
                    "ticker": "MSFT",
                    "quantity": 2.5,
                    "average_cost": 400.0,
                }],
                "theme": "Light",
            }

            save_user_data(original, path)
            loaded, error = load_user_data(path)

        self.assertIsNone(error)
        self.assertEqual(loaded, original)

    def test_invalid_portfolio_is_reported_instead_of_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "user_data.json"
            path.write_text(json.dumps({
                "watchlist": [],
                "portfolio": [{
                    "ticker": "MSFT",
                    "quantity": float("nan"),
                    "average_cost": 400.0,
                }],
                "theme": "Dark",
            }), encoding="utf-8")

            loaded, error = load_user_data(path)

        self.assertIsNotNone(error)
        self.assertEqual(loaded, DEFAULT_USER_DATA)

    def test_invalid_json_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "user_data.json"
            path.write_text("{", encoding="utf-8")

            loaded, error = load_user_data(path)

        self.assertIsNotNone(error)
        self.assertEqual(loaded, DEFAULT_USER_DATA)


if __name__ == "__main__":
    unittest.main()
