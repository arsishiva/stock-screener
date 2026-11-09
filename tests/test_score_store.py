import unittest
from datetime import date, datetime, timezone
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from stock_screener.score_store import (
    ScoreStoreConfig,
    ScoreStoreError,
    build_score_snapshots,
    fetch_local_latest_snapshots,
    fetch_local_snapshot_history,
    fetch_latest_snapshots,
    fetch_snapshot_history,
    load_score_store_config,
    save_local_daily_snapshots,
    save_daily_snapshots,
)


class ScoreStoreTests(unittest.TestCase):
    def test_missing_and_partial_database_secrets(self):
        self.assertIsNone(load_score_store_config({}))
        with self.assertRaises(ScoreStoreError):
            load_score_store_config({"SUPABASE_URL": "https://example.supabase.co"})
        with self.assertRaises(ScoreStoreError):
            load_score_store_config({
                "SUPABASE_URL": "http://example.supabase.co",
                "SUPABASE_SERVICE_ROLE_KEY": "test-key",
            })

    def test_builds_anonymous_daily_snapshot_for_each_scored_company(self):
        companies = {
            "aapl": {
                "name": "Apple Inc.",
                "sector": "Technology",
                "industry": "Consumer Electronics",
                "currency": "USD",
            },
            "MSFT": {"name": "Microsoft Corporation"},
        }
        scores = {
            "aapl": {
                "Business quality": 72.5,
                "Financial health": None,
                "Moat proxy": 80,
                "Growth": 60,
                "Valuation": 50,
                "Technical strength": 70,
                "Risk": 20,
                "Overall score": 69.25,
                "Coverage": 85.7,
            }
        }
        snapshots = build_score_snapshots(
            companies,
            scores,
            snapshot_date=date(2026, 11, 9),
            analyzed_at=datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
        )

        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["ticker"], "AAPL")
        self.assertEqual(snapshots[0]["score_date"], "2026-11-09")
        self.assertEqual(snapshots[0]["business_quality"], 72.5)
        self.assertIsNone(snapshots[0]["financial_health"])
        self.assertNotIn("user", snapshots[0])

    def test_daily_upsert_ignores_duplicate_ticker_date(self):
        session = Mock()
        response = Mock()
        session.request.return_value = response
        config = ScoreStoreConfig("https://example.supabase.co", "service-secret")

        save_daily_snapshots(config, [{"ticker": "AAPL", "score_date": "2026-11-09"}], session=session)

        _, kwargs = session.request.call_args
        self.assertEqual(kwargs["params"], {"on_conflict": "ticker,score_date"})
        self.assertEqual(
            kwargs["headers"]["Prefer"],
            "resolution=ignore-duplicates,return=minimal",
        )
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer service-secret",
        )

    def test_latest_scores_reads_from_the_latest_view(self):
        session = Mock()
        response = Mock()
        response.json.return_value = [{"ticker": "AAPL"}]
        session.request.return_value = response
        config = ScoreStoreConfig("https://example.supabase.co", "service-secret")

        rows = fetch_latest_snapshots(config, session=session)

        self.assertEqual(rows, [{"ticker": "AAPL"}])
        args, kwargs = session.request.call_args
        self.assertEqual(args[:2], ("GET", "https://example.supabase.co/rest/v1/latest_stock_scores"))
        self.assertEqual(kwargs["params"]["order"], "ticker.asc")

    def test_snapshot_history_can_filter_by_ticker(self):
        session = Mock()
        response = Mock()
        response.json.return_value = [{"ticker": "AAPL", "score_date": "2026-11-09"}]
        session.request.return_value = response
        config = ScoreStoreConfig("https://example.supabase.co", "service-secret")

        rows = fetch_snapshot_history(config, ticker=" aapl ", session=session)

        self.assertEqual(len(rows), 1)
        self.assertEqual(session.request.call_args.kwargs["params"]["ticker"], "eq.AAPL")

    def test_snapshot_history_paginates_all_rows(self):
        session = Mock()
        first_response = Mock()
        first_response.json.return_value = [
            {"ticker": f"TICKER{index}"} for index in range(1000)
        ]
        second_response = Mock()
        second_response.json.return_value = [{"ticker": "LAST"}]
        session.request.side_effect = [first_response, second_response]
        config = ScoreStoreConfig("https://example.supabase.co", "service-secret")

        rows = fetch_snapshot_history(config, session=session)

        self.assertEqual(len(rows), 1001)
        self.assertEqual(session.request.call_count, 2)
        self.assertEqual(
            session.request.call_args_list[1].kwargs["headers"]["Range"],
            "1000-1999",
        )

    def test_local_archive_persists_latest_and_daily_history(self):
        with TemporaryDirectory() as directory:
            db_path = f"{directory}/scores.sqlite3"
            snapshots = [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple",
                    "score_date": "2026-11-08",
                    "analyzed_at": "2026-11-08T12:00:00+00:00",
                    "methodology_version": "scorecard-v1",
                    "overall_score": 70,
                },
                {
                    "ticker": "AAPL",
                    "company_name": "Apple",
                    "score_date": "2026-11-09",
                    "analyzed_at": "2026-11-09T12:00:00+00:00",
                    "methodology_version": "scorecard-v1",
                    "overall_score": 75,
                },
                {
                    "ticker": "MSFT",
                    "company_name": "Microsoft",
                    "score_date": "2026-11-09",
                    "analyzed_at": "2026-11-09T12:00:00+00:00",
                    "methodology_version": "scorecard-v1",
                    "overall_score": 80,
                },
            ]

            save_local_daily_snapshots(snapshots, db_path=db_path)
            save_local_daily_snapshots(
                [{**snapshots[1], "overall_score": 99}],
                db_path=db_path,
            )

            latest = fetch_local_latest_snapshots(db_path=db_path)
            history = fetch_local_snapshot_history(db_path=db_path)
            apple_history = fetch_local_snapshot_history(
                ticker="aapl",
                db_path=db_path,
            )

        self.assertEqual(
            {row["ticker"]: row["overall_score"] for row in latest},
            {"AAPL": 75, "MSFT": 80},
        )
        self.assertEqual(len(history), 3)
        self.assertEqual(len(apple_history), 2)
        self.assertEqual(apple_history[0]["score_date"], "2026-11-09")


if __name__ == "__main__":
    unittest.main()
