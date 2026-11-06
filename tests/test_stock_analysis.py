import unittest

import pandas as pd

from stock_screener.analysis import (
    annual_cagr,
    calculate_dcf,
    classify_cyclicality,
    company_metrics,
    dcf_confidence,
    discounted_cash_flow,
    financial_history,
    historical_fcf_summary,
    historical_return,
    recommendation,
    reverse_dcf_growth,
    technical_indicators,
    validate_ticker,
)
from stock_screener.guidance import (
    build_financial_forecast,
    extract_guidance_from_document,
    guidance_accuracy,
)


class StockAnalysisTests(unittest.TestCase):
    def test_validate_ticker_normalizes_and_rejects_invalid_input(self):
        self.assertEqual(validate_ticker("  relIance.ns "), "RELIANCE.NS")
        with self.assertRaises(ValueError):
            validate_ticker("MSFT; DROP TABLE")

    def test_financial_history_calculates_growth_and_cash_flow(self):
        columns = pd.to_datetime(["2023-12-31", "2024-12-31"])
        income = pd.DataFrame(
            [
                [100.0, 120.0],
                [60.0, 72.0],
                [30.0, 36.0],
                [20.0, 24.0],
                [2.0, 2.4],
            ],
            index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "Diluted EPS"],
            columns=columns,
        )
        cashflow = pd.DataFrame(
            [[25.0, 30.0], [-5.0, -6.0], [4.0, 5.0]],
            index=["Operating Cash Flow", "Capital Expenditure", "Depreciation And Amortization"],
            columns=columns,
        )
        balance = pd.DataFrame(
            [[20.0, 25.0], [10.0, 12.0], [50.0, 60.0], [25.0, 30.0]],
            index=["Cash And Cash Equivalents", "Total Debt", "Current Assets", "Current Liabilities"],
            columns=columns,
        )
        data = {
            "statements": {
                "income": income,
                "cashflow": cashflow,
                "balance": balance,
            }
        }

        rows = financial_history(data)

        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[-1]["Revenue growth"], 0.2)
        self.assertAlmostEqual(rows[-1]["Free cash flow"], 24.0)
        self.assertAlmostEqual(rows[-1]["Operating margin"], 0.3)
        self.assertEqual(rows[-1]["Cash"], 25)
        self.assertEqual(rows[-1]["Total debt"], 12)

    def test_annual_cagr_uses_reported_periods(self):
        rows = [{"Revenue": value} for value in (100.0, 110.0, 121.0, 133.1)]
        self.assertAlmostEqual(annual_cagr(rows, "Revenue", 3), 0.1)
        self.assertIsNone(annual_cagr(rows[:3], "Revenue", 3))

    def test_technical_indicators_and_historical_return(self):
        dates = pd.bdate_range("2024-01-01", periods=260)
        close = pd.Series(range(100, 360), index=dates, dtype=float)
        history = pd.DataFrame(
            {
                "Open": close,
                "High": close + 1,
                "Low": close - 1,
                "Close": close,
                "Volume": 1_000,
            },
            index=dates,
        )

        indicators = technical_indicators(history)

        self.assertAlmostEqual(indicators["SMA 200"].iloc[-1], close.iloc[-200:].mean())
        self.assertEqual(indicators["RSI 14"].iloc[-1], 100)
        self.assertGreater(historical_return(history, 30), 0)

    def test_dcf_rejects_invalid_inputs_and_prices_positive_cash_flow(self):
        self.assertIsNone(discounted_cash_flow(100, 10, 0, 0, 0.05, 0.08, 0.08))
        self.assertIsNone(discounted_cash_flow(100, 10, None, 0, 0.05, 0.09, 0.02))
        value = discounted_cash_flow(100, 10, 20, 10, 0.05, 0.09, 0.02, 5)
        self.assertIsNotNone(value)
        self.assertGreater(value, 10)

    def test_dcf_reconciles_enterprise_value_to_equity_value_and_diluted_shares(self):
        result = calculate_dcf(
            100, 10, 20, 10, 5, [0], 0.1, 0,
        )

        self.assertAlmostEqual(result["enterprise_value"], 1000)
        self.assertAlmostEqual(result["equity_value"], 1005)
        self.assertAlmostEqual(result["fair_value_per_share"], 100.5)
        self.assertTrue(result["minority_interest_applied"])

    def test_dcf_accepts_individual_growth_rates_and_rejects_non_finite_inputs(self):
        result = calculate_dcf(100, 10, 20, 10, None, [0.1, 0.2], 0.1, 0.02)
        self.assertEqual([row["Growth rate"] for row in result["forecast"]], [0.1, 0.2])
        self.assertIsNone(
            calculate_dcf(100, 10, 20, 10, None, [float("nan")], 0.1, 0.02)
        )

    def test_dcf_separates_fcf_and_revenue_growth_for_margin_sensitivity(self):
        result = calculate_dcf(
            100, 10, 20, 10, None, [0.1], 0.1, 0,
            annual_revenue_growth_rates=[0.5],
            revenue=1000,
            base_operating_margin=0.1,
            forecast_operating_margin=0.2,
            tax_rate=0.2,
        )

        self.assertAlmostEqual(result["forecast"][0]["Forecast FCF"], 230)
        self.assertAlmostEqual(result["forecast"][0]["Revenue growth rate"], 0.5)

    def test_normalized_fcf_uses_reported_median_and_tracks_coverage(self):
        annual = [
            {
                "Fiscal year": str(year),
                "Free cash flow": value,
                "Revenue": 1000,
                "EBITDA margin": value / 1000,
                "Operating cash flow": value + 100,
                "Capital expenditure": -100,
            }
            for year, value in zip(range(2019, 2024), [50, 100, 500, -100, 150])
        ]

        summary = historical_fcf_summary(annual)

        self.assertEqual(summary["normalized_fcf"], 100)
        self.assertEqual(summary["fcf_count"], 5)
        self.assertEqual(summary["reported_fcf_median"], 100)
        self.assertEqual(summary["normalization_period_count"], 5)
        self.assertTrue(summary["has_five_year_history"])
        self.assertEqual(summary["peak_year"], "2021")
        self.assertEqual(summary["trough_year"], "2022")

    def test_company_metrics_does_not_substitute_profile_fcf_for_missing_statements(self):
        dates = pd.to_datetime(["2024-01-02"])
        history = pd.DataFrame(
            {"Open": [10], "High": [11], "Low": [9], "Close": [10], "Volume": [100]},
            index=dates,
        )
        empty = pd.DataFrame()
        data = {
            "ticker": "TEST",
            "retrieved_at": pd.Timestamp("2024-01-02", tz="UTC"),
            "warnings": [],
            "info": {
                "freeCashflow": 999,
                "sharesOutstanding": 100,
                "totalCash": 50,
                "totalDebt": 10,
            },
            "history": history,
            "statements": {"income": empty, "cashflow": empty, "balance": empty},
        }

        metrics = company_metrics(data)

        self.assertIsNone(metrics["free_cash_flow"])
        self.assertIsNone(metrics["fcf_source"])

    def test_reverse_dcf_recovers_market_implied_growth(self):
        market_value = calculate_dcf(
            100, 10, 20, 10, None, [0.05] * 5, 0.09, 0.02
        )["enterprise_value"]

        implied_growth = reverse_dcf_growth(
            market_value, 100, 10, 20, 10, None, 0.09, 0.02, 5
        )

        self.assertAlmostEqual(implied_growth, 0.05, places=6)

    def test_confidence_is_independent_and_cyclicality_is_labeled(self):
        history = historical_fcf_summary([
            {"Fiscal year": str(year), "Free cash flow": value}
            for year, value in zip(range(2019, 2024), [100, 120, 80, 150, 110])
        ])
        confidence = dcf_confidence(
            history, [80, 100, 120], 100, 95, True, 75, 0.7
        )

        self.assertLess(confidence["score"], 100)
        self.assertLess(confidence["components"]["Cyclicality"], 100)
        self.assertEqual(
            classify_cyclicality("MU", "Micron", "Semiconductors", "Technology", None)[1],
            "Memory semiconductors",
        )

    def test_recommendation_thresholds(self):
        self.assertEqual(recommendation(None), "INSUFFICIENT DATA")
        self.assertEqual(recommendation(75), "STRONG BUY")
        self.assertEqual(recommendation(60), "BUY")
        self.assertEqual(recommendation(40), "HOLD")
        self.assertEqual(recommendation(20), "SELL")
        self.assertEqual(recommendation(19), "STRONG SELL")


class CompanyGuidanceTests(unittest.TestCase):
    def test_numeric_guidance_preserves_range_source_and_period(self):
        source = {
            "source_url": "https://www.sec.gov/example",
            "publication_date": "2025-01-15",
            "reporting_period": "2024-12-31",
            "retrieved_at": "2025-01-16T00:00:00+00:00",
            "document_reference": "ex99-1.htm",
            "form": "8-K",
        }

        guidance = extract_guidance_from_document(
            "We expect revenue for FY2025 to be between $1.2 billion and $1.4 billion.",
            ticker="TEST",
            currency="USD",
            document=source,
            document_index=0,
        )

        revenue = next(item for item in guidance if item["metric"] == "revenue")
        self.assertEqual(revenue["classification"], "Company guidance")
        self.assertEqual(revenue["period"], "FY2025")
        self.assertEqual(revenue["low"], 1_200_000_000)
        self.assertEqual(revenue["high"], 1_400_000_000)
        self.assertEqual(revenue["source_url"], source["source_url"])
        self.assertEqual(revenue["publication_date"], source["publication_date"])

    def test_qualitative_commentary_does_not_become_numeric_guidance(self):
        guidance = extract_guidance_from_document(
            "Management expects revenue growth to improve as demand recovers.",
            ticker="TEST",
            currency="USD",
            document={
                "source_url": "https://www.sec.gov/example",
                "publication_date": "2025-01-15",
                "reporting_period": "2024-12-31",
                "retrieved_at": "2025-01-16T00:00:00+00:00",
                "document_reference": "ex99-1.htm",
                "form": "8-K",
            },
            document_index=0,
        )

        revenue_growth = next(item for item in guidance if item["metric"] == "revenue_growth")
        self.assertEqual(
            revenue_growth["classification"],
            "Qualitative management commentary",
        )
        self.assertIsNone(revenue_growth["low"])
        self.assertIsNone(revenue_growth["high"])

    def test_annual_forecast_prefers_company_guidance_and_calculates_fcf(self):
        annual_history = [
            {
                "Fiscal year": str(year),
                "Revenue": 1000.0 + (year - 2020) * 50,
                "Revenue growth": 0.05,
                "Gross margin": 0.4,
                "Operating margin": 0.2,
                "Operating income": 200.0,
                "Net margin": 0.15,
                "Net income": 150.0,
                "Pretax income": 180.0,
                "Tax provision": 30.0,
                "Operating cash flow": 180.0,
                "Capital expenditure": -50.0,
                "Free cash flow": 130.0,
                "Diluted shares": 100.0,
                "EPS": 1.5,
            }
            for year in range(2020, 2025)
        ]
        quarterly_history = [{
            "Period": "2024-09-30",
            "Revenue": 300.0,
            "Gross profit": 120.0,
            "Operating income": 60.0,
            "Net income": 45.0,
            "Operating cash flow": 50.0,
            "Capital expenditure": -15.0,
            "Diluted shares": 100.0,
        }]
        guidance_items = []
        for metric, low, high in (
            ("revenue", 1200.0, 1300.0),
            ("operating_cash_flow", 230.0, 250.0),
            ("capital_expenditure", 40.0, 50.0),
        ):
            guidance_items.append({
                "metric": metric,
                "classification": "Company guidance",
                "period": "FY2025",
                "low": low,
                "high": high,
                "publication_date": "2024-11-15",
                "source_url": "https://www.sec.gov/example",
                "document_reference": "ex99-1.htm",
                "sentence": "Management guidance",
            })
        guidance_items.append({
            "metric": "gross_margin",
            "classification": "Company guidance",
            "period": "FY2025",
            "low": 80.0,
            "high": 90.0,
            "publication_date": "2024-10-15",
            "source_url": "https://www.sec.gov/older-release",
            "document_reference": "old-ex99-1.htm",
            "sentence": "Older management guidance",
        })

        result = build_financial_forecast(
            annual_history,
            quarterly_history,
            {
                "status": "available",
                "guidance": guidance_items,
                "latest_earnings_filing_date": "2024-11-15",
            },
            years=5,
            quarters=4,
            model_assumptions={
                "annual_revenue_growth_rates": [0.1] * 5,
                "operating_margin": 0.2,
                "tax_rate": 0.2,
                "operating_cash_flow_margin": 0.18,
                "capital_expenditure_margin": 0.05,
            },
        )

        first_year = result["annual"][0]
        self.assertEqual(first_year["Revenue"], 1250.0)
        self.assertEqual(first_year["Revenue classification"], "Company guidance")
        self.assertEqual(first_year["Operating cash flow"], 240.0)
        self.assertEqual(first_year["Capital expenditure"], 45.0)
        self.assertEqual(first_year["Free cash flow"], 195.0)
        self.assertEqual(first_year["Gross margin"], 0.4)
        self.assertEqual(
            first_year["Line item sources"]["Gross margin"]["classification"],
            "Model estimate",
        )
        self.assertEqual(
            first_year["Line item sources"]["Operating cash flow"]["classification"],
            "Company guidance",
        )
        self.assertEqual(len(result["annual"]), 5)
        self.assertEqual(len(result["quarterly"]), 4)

    def test_guidance_accuracy_only_matches_period_aligned_actuals(self):
        source = {
            "metric": "revenue",
            "classification": "Company guidance",
            "period": "FY2024 Q1",
            "low": 90.0,
            "high": 110.0,
            "publication_date": "2024-02-01",
            "source_url": "https://www.sec.gov/example",
        }
        result = guidance_accuracy(
            [source],
            [
                {"Period": "2024-03-31", "Revenue": 105.0},
                {"Period": "2024-06-30", "Revenue": 200.0},
            ],
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["comparisons"][0]["result"], "within range")
        self.assertAlmostEqual(result["mean_midpoint_variance"], 0.05)


if __name__ == "__main__":
    unittest.main()
