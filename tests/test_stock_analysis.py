import unittest

import pandas as pd

from stock_screener.analysis import (
    annual_cagr,
    discounted_cash_flow,
    financial_history,
    historical_return,
    recommendation,
    technical_indicators,
    validate_ticker,
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

    def test_recommendation_thresholds(self):
        self.assertEqual(recommendation(None), "INSUFFICIENT DATA")
        self.assertEqual(recommendation(75), "STRONG BUY")
        self.assertEqual(recommendation(60), "BUY")
        self.assertEqual(recommendation(40), "HOLD")
        self.assertEqual(recommendation(20), "SELL")
        self.assertEqual(recommendation(19), "STRONG SELL")


if __name__ == "__main__":
    unittest.main()
