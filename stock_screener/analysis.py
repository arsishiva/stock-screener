"""Market-data retrieval and transparent stock-analysis calculations."""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

LOGGER = logging.getLogger(__name__)
TICKER_PATTERN = re.compile(r"^[A-Za-z0-9.^=-]{1,20}$")
BENCHMARKS = ("MSFT", "GOOGL", "META", "AAPL")


def validate_ticker(ticker: str) -> str:
    """Return a normalized ticker or reject unsafe/ambiguous input."""
    value = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(value):
        raise ValueError("Enter a ticker using letters, numbers, dots, hyphens, ^ or =.")
    return value


def fetch_stock_data(ticker: str) -> dict[str, Any]:
    """Fetch one company's profile, five-year history, and annual statements."""
    symbol = validate_ticker(ticker)
    stock = yf.Ticker(symbol)
    warnings: list[str] = []

    try:
        info = stock.get_info()
    except Exception as exc:
        LOGGER.warning("Profile unavailable for %s: %s", symbol, exc)
        info = {}
        warnings.append(f"Company profile unavailable: {exc}")

    try:
        history = stock.history(period="5y", auto_adjust=True, actions=False, timeout=20)
    except Exception as exc:
        LOGGER.exception("Price history request failed for %s", symbol)
        raise RuntimeError(f"Could not retrieve price history for {symbol}: {exc}") from exc

    if history.empty or "Close" not in history:
        raise RuntimeError(
            f"No historical prices were returned for {symbol}. Check the ticker and exchange suffix."
        )

    statements: dict[str, pd.DataFrame] = {}
    for key, attribute in (
        ("income", "financials"),
        ("balance", "balance_sheet"),
        ("cashflow", "cashflow"),
    ):
        try:
            statements[key] = getattr(stock, attribute)
        except Exception as exc:
            LOGGER.warning("%s statement unavailable for %s: %s", key, symbol, exc)
            statements[key] = pd.DataFrame()
            warnings.append(f"Annual {key} statement unavailable: {exc}")

    quarterly_statements: dict[str, pd.DataFrame] = {}
    for key, attribute in (
        ("income", "quarterly_income_stmt"),
        ("balance", "quarterly_balance_sheet"),
        ("cashflow", "quarterly_cash_flow"),
    ):
        try:
            quarterly_statements[key] = getattr(stock, attribute)
        except Exception as exc:
            LOGGER.warning("%s quarterly statement unavailable for %s: %s", key, symbol, exc)
            quarterly_statements[key] = pd.DataFrame()
            warnings.append(f"Quarterly {key} statement unavailable: {exc}")

    return {
        "ticker": symbol,
        "info": info or {},
        "history": history,
        "statements": statements,
        "quarterly_statements": quarterly_statements,
        "retrieved_at": datetime.now(timezone.utc),
        "warnings": warnings,
    }


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _statement_value(statement: pd.DataFrame, *aliases: str) -> float | None:
    if statement.empty:
        return None
    normalized_aliases = [alias.casefold().replace(" ", "") for alias in aliases]
    for row in statement.index:
        normalized_row = str(row).casefold().replace(" ", "")
        if normalized_row in normalized_aliases:
            values = statement.loc[row]
            if isinstance(values, pd.Series):
                for value in values:
                    number = _number(value)
                    if number is not None:
                        return number
            return _number(values)
    return None


def financial_history(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build annual financial rows from reported statements without filling gaps."""
    return _financial_history(data.get("statements", {}))


def quarterly_financial_history(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build quarterly financial rows from reported quarterly statements."""
    return _financial_history(data.get("quarterly_statements", {}))


def _financial_history(statements: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Build financial rows at the reporting frequency supplied."""
    income = statements.get("income", pd.DataFrame())
    cashflow = statements.get("cashflow", pd.DataFrame())
    balance = statements.get("balance", pd.DataFrame())

    dates: set[pd.Timestamp] = set()
    for statement in (income, cashflow, balance):
        if not statement.empty:
            dates.update(pd.Timestamp(column) for column in statement.columns)

    rows = []
    for period_end in sorted(dates):
        annual = {}
        for key, statement in statements.items():
            if statement.empty:
                annual[key] = pd.DataFrame()
                continue
            matching_columns = [
                column for column in statement.columns
                if pd.Timestamp(column) == period_end
            ]
            annual[key] = statement[matching_columns] if matching_columns else pd.DataFrame()

        revenue = _statement_value(annual["income"], "Total Revenue", "Operating Revenue")
        gross_profit = _statement_value(annual["income"], "Gross Profit")
        operating_income = _statement_value(annual["income"], "Operating Income")
        operating_expenses = _statement_value(
            annual["income"], "Operating Expense", "Operating Expenses"
        )
        net_income = _statement_value(annual["income"], "Net Income", "Net Income Common Stockholders")
        eps = _statement_value(annual["income"], "Diluted EPS", "Basic EPS")
        operating_cash_flow = _statement_value(
            annual["cashflow"], "Operating Cash Flow", "Cash Flow From Continuing Operating Activities"
        )
        capital_expenditure = _statement_value(
            annual["cashflow"], "Capital Expenditure", "Capital Expenditures"
        )
        free_cash_flow = (
            operating_cash_flow - abs(capital_expenditure)
            if operating_cash_flow is not None and capital_expenditure is not None
            else None
        )
        depreciation = _statement_value(
            annual["cashflow"], "Depreciation And Amortization", "Depreciation Amortization Depletion"
        )
        ebitda = operating_income + depreciation if operating_income is not None and depreciation is not None else None
        cash = _statement_value(
            annual["balance"],
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Short Term Investments",
        )
        total_debt = _statement_value(
            annual["balance"], "Total Debt", "Long Term Debt And Capital Lease Obligation"
        )
        current_assets = _statement_value(annual["balance"], "Current Assets")
        current_liabilities = _statement_value(annual["balance"], "Current Liabilities")
        diluted_shares = _statement_value(
            annual["income"], "Diluted Average Shares", "Diluted Shares"
        )
        minority_interest = _statement_value(
            annual["balance"], "Minority Interest", "Minority Interests", "Noncontrolling Interest"
        )
        interest_expense = _statement_value(
            annual["income"], "Interest Expense", "Interest Expense Non Operating"
        )
        pretax_income = _statement_value(
            annual["income"], "Pretax Income", "Income Before Tax"
        )
        tax_provision = _statement_value(annual["income"], "Tax Provision", "Income Tax Expense")

        rows.append({
            "Period": period_end.strftime("%Y-%m-%d"),
            "Fiscal year": str(period_end.year),
            "Revenue": revenue,
            "Revenue growth": None,
            "Gross profit": gross_profit,
            "Gross margin": gross_profit / revenue if gross_profit is not None and revenue else None,
            "Operating income": operating_income,
            "Operating expenses": operating_expenses,
            "Operating margin": operating_income / revenue if operating_income is not None and revenue else None,
            "Operating income": operating_income,
            "EBITDA": ebitda,
            "EBITDA margin": ebitda / revenue if ebitda is not None and revenue else None,
            "Net income": net_income,
            "Net margin": net_income / revenue if net_income is not None and revenue else None,
            "EPS": eps,
            "Free cash flow": free_cash_flow,
            "Operating cash flow": operating_cash_flow,
            "Capital expenditure": capital_expenditure,
            "Cash": cash,
            "Total debt": total_debt,
            "Current assets": current_assets,
            "Current liabilities": current_liabilities,
            "Diluted shares": diluted_shares,
            "Minority interest": minority_interest,
            "Interest expense": interest_expense,
            "Depreciation and amortization": depreciation,
            "Pretax income": pretax_income,
            "Tax provision": tax_provision,
        })

    rows.sort(key=lambda row: row["Period"])
    for index, row in enumerate(rows):
        if index and rows[index - 1]["Revenue"] and row["Revenue"] is not None:
            row["Revenue growth"] = row["Revenue"] / rows[index - 1]["Revenue"] - 1
    return rows


def technical_indicators(history: pd.DataFrame) -> pd.DataFrame:
    """Calculate price-based indicators from adjusted daily OHLCV history."""
    prices = history.copy().sort_index()
    close = prices["Close"].astype(float)
    prices["SMA 20"] = close.rolling(20).mean()
    prices["SMA 50"] = close.rolling(50).mean()
    prices["SMA 100"] = close.rolling(100).mean()
    prices["SMA 200"] = close.rolling(200).mean()
    prices["EMA 20"] = close.ewm(span=20, adjust=False).mean()
    prices["EMA 50"] = close.ewm(span=50, adjust=False).mean()
    prices["EMA 200"] = close.ewm(span=200, adjust=False).mean()
    prices["BB upper"] = close.rolling(20).mean() + 2 * close.rolling(20).std()
    prices["BB lower"] = close.rolling(20).mean() - 2 * close.rolling(20).std()

    changes = close.diff()
    average_gain = changes.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    average_loss = -changes.clip(upper=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    relative_strength = average_gain / average_loss.replace(0, float("nan"))
    prices["RSI 14"] = 100 - 100 / (1 + relative_strength)
    prices.loc[(average_loss == 0) & (average_gain > 0), "RSI 14"] = 100

    fast_ema = close.ewm(span=12, adjust=False).mean()
    slow_ema = close.ewm(span=26, adjust=False).mean()
    prices["MACD"] = fast_ema - slow_ema
    prices["MACD signal"] = prices["MACD"].ewm(span=9, adjust=False).mean()
    prices["MACD histogram"] = prices["MACD"] - prices["MACD signal"]

    if {"High", "Low"}.issubset(prices.columns):
        previous_close = close.shift()
        true_range = pd.concat(
            [
                prices["High"] - prices["Low"],
                (prices["High"] - previous_close).abs(),
                (prices["Low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        prices["ATR 14"] = true_range.rolling(14).mean()
    return prices


def historical_return(history: pd.DataFrame, days: int) -> float | None:
    close = history["Close"].dropna()
    if len(close) < 2:
        return None
    target_date = close.index[-1] - pd.Timedelta(days=days)
    available = close.loc[close.index <= target_date]
    if available.empty:
        return None
    return float(close.iloc[-1] / available.iloc[-1] - 1)


def performance_metrics(history: pd.DataFrame) -> dict[str, float | None]:
    close = history["Close"].dropna()
    if close.empty:
        return {}
    ytd = close.loc[close.index.year == close.index[-1].year]
    drawdown = close / close.cummax() - 1
    returns = close.pct_change().dropna()
    return {
        "1 day return": float(returns.iloc[-1]) if not returns.empty else None,
        "1 week return": historical_return(history, 7),
        "1 month return": historical_return(history, 30),
        "3 month return": historical_return(history, 90),
        "6 month return": historical_return(history, 182),
        "1 year return": historical_return(history, 365),
        "3 year return": historical_return(history, 365 * 3),
        "5 year return": historical_return(history, 365 * 5),
        "YTD return": float(ytd.iloc[-1] / ytd.iloc[0] - 1) if len(ytd) > 1 else None,
        "Maximum drawdown": float(drawdown.min()),
        "Historical volatility": float(returns.std() * (252 ** 0.5)) if len(returns) > 1 else None,
    }


def annual_cagr(rows: list[dict[str, Any]], metric: str, years: int) -> float | None:
    values = [row.get(metric) for row in rows if row.get(metric) is not None]
    if len(values) <= years:
        return None
    start, end = values[-(years + 1)], values[-1]
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def discounted_cash_flow(
    free_cash_flow: float | None,
    shares: float | None,
    cash: float | None,
    debt: float | None,
    annual_growth: float,
    discount_rate: float,
    terminal_growth: float,
    years: int = 5,
) -> float | None:
    """Compatibility wrapper for an FCF-growth DCF returning value per share."""
    growth_rates = [annual_growth] * years
    result = calculate_dcf(
        free_cash_flow,
        shares,
        cash,
        debt,
        None,
        growth_rates,
        discount_rate,
        terminal_growth,
    )
    return result["fair_value_per_share"] if result else None


def calculate_dcf(
    starting_fcf: float | None,
    diluted_shares: float | None,
    cash: float | None,
    debt: float | None,
    minority_interest: float | None,
    annual_growth_rates: list[float],
    discount_rate: float,
    terminal_growth: float,
    *,
    annual_revenue_growth_rates: list[float] | None = None,
    revenue: float | None = None,
    base_operating_margin: float | None = None,
    forecast_operating_margin: float | None = None,
    tax_rate: float | None = None,
    base_capex_margin: float | None = None,
    forecast_capex_margin: float | None = None,
) -> dict[str, Any] | None:
    """Discount annual FCF forecasts and reconcile enterprise to equity value.

    FCF growth is the forecast baseline. When reported revenue, operating margin,
    capex ratio, and user-entered margin/capex assumptions exist, changes in those
    assumptions are translated into an explicit after-tax operating-profit and
    capex adjustment to each forecast year.
    """
    if (
        starting_fcf is None or starting_fcf <= 0
        or diluted_shares is None or diluted_shares <= 0
        or cash is None or debt is None
        or not annual_growth_rates
        or not 0 <= terminal_growth < discount_rate
        or not all(math.isfinite(value) for value in (starting_fcf, diluted_shares, cash, debt, discount_rate, terminal_growth))
        or any(not math.isfinite(rate) or rate <= -1 for rate in annual_growth_rates)
        or any(
            value is not None and not math.isfinite(value)
            for value in (
                minority_interest, revenue, base_operating_margin,
                forecast_operating_margin, tax_rate, base_capex_margin,
                forecast_capex_margin,
            )
        )
        or (
            annual_revenue_growth_rates is not None
            and (
                len(annual_revenue_growth_rates) != len(annual_growth_rates)
                or any(
                    not math.isfinite(rate) or rate <= -1
                    for rate in annual_revenue_growth_rates
                )
            )
        )
    ):
        return None

    forecast = []
    present_values = []
    fcf = starting_fcf
    forecast_revenue = revenue
    revenue_growth_rates = annual_revenue_growth_rates or annual_growth_rates
    for year, (growth_rate, revenue_growth_rate) in enumerate(
        zip(annual_growth_rates, revenue_growth_rates), start=1
    ):
        fcf *= 1 + growth_rate
        if forecast_revenue is not None:
            forecast_revenue *= 1 + revenue_growth_rate
        if (
            forecast_revenue is not None
            and base_operating_margin is not None
            and forecast_operating_margin is not None
            and tax_rate is not None
        ):
            fcf += (
                forecast_revenue
                * (forecast_operating_margin - base_operating_margin)
                * (1 - tax_rate)
            )
        if (
            forecast_revenue is not None
            and base_capex_margin is not None
            and forecast_capex_margin is not None
        ):
            fcf -= forecast_revenue * (forecast_capex_margin - base_capex_margin)

        present_value = fcf / (1 + discount_rate) ** year
        forecast.append({
            "Year": year,
            "Growth rate": growth_rate,
            "Revenue growth rate": revenue_growth_rate,
            "Forecast FCF": fcf,
            "Present value": present_value,
        })
        present_values.append(present_value)

    terminal_value = fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    terminal_present_value = terminal_value / (1 + discount_rate) ** len(annual_growth_rates)
    enterprise_value = sum(present_values) + terminal_present_value
    equity_value = enterprise_value + cash - debt
    minority_interest_applied = minority_interest is not None
    if minority_interest_applied:
        equity_value -= minority_interest

    return {
        "forecast": forecast,
        "terminal_value": terminal_value,
        "terminal_present_value": terminal_present_value,
        "present_value_of_forecast": sum(present_values),
        "enterprise_value": enterprise_value,
        "cash": cash,
        "debt": debt,
        "minority_interest": minority_interest,
        "minority_interest_applied": minority_interest_applied,
        "equity_value": equity_value,
        "diluted_shares": diluted_shares,
        "fair_value_per_share": equity_value / diluted_shares,
        "terminal_value_share": (
            terminal_present_value / enterprise_value if enterprise_value > 0 else None
        ),
    }


def calculate_forecast_dcf(
    forecast: list[dict[str, Any]],
    current_diluted_shares: float | None,
    cash: float | None,
    debt: float | None,
    minority_interest: float | None,
    discount_rate: float,
    terminal_growth: float,
) -> dict[str, Any] | None:
    """Value explicitly forecast operating cash flow less capex, not a grown FCF proxy."""
    if (
        not forecast
        or current_diluted_shares is None or current_diluted_shares <= 0
        or cash is None or debt is None
        or not math.isfinite(discount_rate)
        or not 0 <= terminal_growth < discount_rate
    ):
        return None

    projected: list[dict[str, Any]] = []
    present_values: list[float] = []
    for year, row in enumerate(forecast, start=1):
        operating_cash_flow = row.get("Operating cash flow")
        capital_expenditure = row.get("Capital expenditure")
        if (
            operating_cash_flow is None or capital_expenditure is None
            or not math.isfinite(operating_cash_flow)
            or not math.isfinite(capital_expenditure)
        ):
            return None
        free_cash_flow = operating_cash_flow - abs(capital_expenditure)
        present_value = free_cash_flow / (1 + discount_rate) ** year
        projected_row = {
            **row,
            "Forecast year": year,
            "Free cash flow": free_cash_flow,
            "Present value of FCF": present_value,
        }
        projected.append(projected_row)
        present_values.append(present_value)

    terminal_fcf = projected[-1]["Free cash flow"]
    if terminal_fcf <= 0:
        return None
    terminal_value = terminal_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    terminal_present_value = terminal_value / (1 + discount_rate) ** len(projected)
    enterprise_value = sum(present_values) + terminal_present_value
    equity_value = enterprise_value + cash - debt
    minority_interest_applied = minority_interest is not None
    if minority_interest_applied:
        equity_value -= minority_interest

    return {
        "forecast": projected,
        "terminal_value": terminal_value,
        "terminal_present_value": terminal_present_value,
        "present_value_of_forecast": sum(present_values),
        "enterprise_value": enterprise_value,
        "cash": cash,
        "debt": debt,
        "minority_interest": minority_interest,
        "minority_interest_applied": minority_interest_applied,
        "equity_value": equity_value,
        "diluted_shares": current_diluted_shares,
        "fair_value_per_share": equity_value / current_diluted_shares,
        "terminal_value_share": (
            terminal_present_value / enterprise_value if enterprise_value > 0 else None
        ),
    }


def historical_fcf_summary(annual: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize reported FCF and calculated EBITDA margins without filling gaps."""
    fcf_rows = [row for row in annual if row.get("Free cash flow") is not None]
    fcf_values = [row["Free cash flow"] for row in fcf_rows]
    positive_fcf = [value for value in fcf_values if value > 0]
    normalization_rows = [
        row for row in annual
        if row.get("Revenue") is not None and row["Revenue"] > 0
        and row.get("Operating cash flow") is not None
        and row.get("Capital expenditure") is not None
    ]
    historical_revenues = [row["Revenue"] for row in normalization_rows]
    operating_cash_flow_margins = [
        row["Operating cash flow"] / row["Revenue"] for row in normalization_rows
    ]
    capex_margins = [
        abs(row["Capital expenditure"]) / row["Revenue"] for row in normalization_rows
    ]
    normalized_fcf = None
    if len(normalization_rows) >= 3:
        normalized_fcf = float(pd.Series(historical_revenues).median()) * (
            float(pd.Series(operating_cash_flow_margins).median())
            - float(pd.Series(capex_margins).median())
        )
    reported_fcf_median = (
        float(pd.Series(fcf_values).median()) if len(fcf_values) >= 3 else None
    )
    fcf_mean = float(pd.Series(fcf_values).mean()) if fcf_values else None
    fcf_std = float(pd.Series(fcf_values).std(ddof=0)) if len(fcf_values) > 1 else None
    fcf_cv = fcf_std / abs(fcf_mean) if fcf_std is not None and fcf_mean else None
    fcf_margins = [
        row["Free cash flow"] / row["Revenue"]
        for row in fcf_rows if row.get("Revenue")
    ]
    ebitda_margin_rows = [
        row for row in annual
        if row.get("EBITDA margin") is not None
    ]
    ebitda_margins = [row["EBITDA margin"] for row in ebitda_margin_rows]
    margin_mean = float(pd.Series(ebitda_margins).mean()) if ebitda_margins else None
    margin_std = float(pd.Series(ebitda_margins).std(ddof=0)) if len(ebitda_margins) > 1 else None
    sign_changes = sum(
        1 for previous, current in zip(fcf_values, fcf_values[1:])
        if previous * current < 0
    )

    peak_year = None
    trough_year = None
    if fcf_rows:
        peak_year = max(fcf_rows, key=lambda row: row["Free cash flow"])["Fiscal year"]
        trough_year = min(fcf_rows, key=lambda row: row["Free cash flow"])["Fiscal year"]

    return {
        "fcf_values": fcf_values,
        "fcf_periods": [row["Fiscal year"] for row in fcf_rows],
        "fcf_count": len(fcf_values),
        "positive_fcf_count": len(positive_fcf),
        "normalized_fcf": normalized_fcf,
        "normalization_period_count": len(normalization_rows),
        "normalization_method": (
            "Median reported revenue × (median operating-cash-flow margin − median capex/revenue)"
            if normalized_fcf is not None else None
        ),
        "median_historical_revenue": (
            float(pd.Series(historical_revenues).median()) if historical_revenues else None
        ),
        "median_operating_cash_flow_margin": (
            float(pd.Series(operating_cash_flow_margins).median())
            if operating_cash_flow_margins else None
        ),
        "median_capex_margin": (
            float(pd.Series(capex_margins).median()) if capex_margins else None
        ),
        "reported_fcf_median": reported_fcf_median,
        "operating_cash_flow_values": [
            row["Operating cash flow"] for row in normalization_rows
        ],
        "capex_values": [
            abs(row["Capital expenditure"]) for row in normalization_rows
        ],
        "normalization_periods": [
            row["Fiscal year"] for row in normalization_rows
        ],
        "fcf_mean": fcf_mean,
        "fcf_std": fcf_std,
        "fcf_cv": fcf_cv,
        "fcf_margins": fcf_margins,
        "median_fcf_margin": float(pd.Series(fcf_margins).median()) if fcf_margins else None,
        "ebitda_margins": ebitda_margins,
        "ebitda_margin_periods": [
            row["Fiscal year"] for row in ebitda_margin_rows
        ],
        "median_ebitda_margin": float(pd.Series(ebitda_margins).median()) if ebitda_margins else None,
        "ebitda_margin_std": margin_std,
        "ebitda_margin_mean": margin_mean,
        "fcf_sign_changes": sign_changes,
        "peak_year": peak_year,
        "trough_year": trough_year,
        "has_five_year_history": len(fcf_values) >= 5,
    }


def dcf_confidence(
    historical: dict[str, Any],
    sensitivity_values: list[float | None],
    base_value: float | None,
    normalized_value: float | None,
    cyclical: bool,
    completeness: float,
    terminal_value_share: float | None,
    guidance_accuracy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score model reliability separately from expected return."""
    fcf_cv = historical.get("fcf_cv")
    stability = (
        max(0.0, min(100.0, 100 / (1 + fcf_cv)))
        if fcf_cv is not None else 35.0 if historical.get("fcf_count", 0) > 0 else 0.0
    )
    sensitivity_values = [value for value in sensitivity_values if value is not None]
    if base_value and base_value > 0 and sensitivity_values:
        sensitivity_spread = (max(sensitivity_values) - min(sensitivity_values)) / base_value
        sensitivity_score = max(0.0, min(100.0, 100 - sensitivity_spread * 100))
    else:
        sensitivity_score = 0.0

    history_count = historical.get("normalization_period_count", 0)
    normalization_score = (
        min(100.0, history_count * 20)
        if normalized_value is not None else 0.0
    )
    cyclicality_score = 35.0 if cyclical else 80.0
    terminal_dependence_score = (
        max(0.0, min(100.0, 100 - terminal_value_share * 100))
        if terminal_value_share is not None else 35.0
    )
    accuracy_count = guidance_accuracy.get("count", 0) if guidance_accuracy else 0
    absolute_guidance_variance = (
        abs(guidance_accuracy["mean_midpoint_variance"])
        if guidance_accuracy and guidance_accuracy.get("mean_midpoint_variance") is not None
        else None
    )
    guidance_accuracy_score = (
        max(0.0, min(100.0, 100 - absolute_guidance_variance * 100))
        if accuracy_count >= 3 and absolute_guidance_variance is not None
        else max(35.0, 50.0 - max(0, 3 - accuracy_count) * 5)
    )

    components = {
        "Historical cash-flow stability": stability,
        "Forecast sensitivity": sensitivity_score,
        "Data completeness": max(0.0, min(100.0, completeness)),
        "Cyclicality": cyclicality_score,
        "Normalized FCF reliability": normalization_score,
        "Terminal value dependence": terminal_dependence_score,
        "Historical guidance accuracy": guidance_accuracy_score,
    }
    weights = {
        "Historical cash-flow stability": 0.18,
        "Forecast sensitivity": 0.18,
        "Data completeness": 0.18,
        "Cyclicality": 0.14,
        "Normalized FCF reliability": 0.12,
        "Terminal value dependence": 0.10,
        "Historical guidance accuracy": 0.10,
    }
    score = sum(components[key] * weights[key] for key in components)
    return {"score": round(score), "components": components}


def reverse_dcf_growth(
    market_enterprise_value: float | None,
    starting_fcf: float | None,
    diluted_shares: float | None,
    cash: float | None,
    debt: float | None,
    minority_interest: float | None,
    discount_rate: float,
    terminal_growth: float,
    years: int = 5,
) -> float | None:
    """Find a uniform annual FCF growth rate implied by the market EV."""
    if (
        market_enterprise_value is None or starting_fcf is None or starting_fcf <= 0
        or diluted_shares is None or diluted_shares <= 0 or cash is None or debt is None
        or not 0 <= terminal_growth < discount_rate
    ):
        return None

    low, high = -0.95, 2.0
    low_value = calculate_dcf(
        starting_fcf, diluted_shares, cash, debt, minority_interest,
        [low] * years, discount_rate, terminal_growth,
    )
    high_value = calculate_dcf(
        starting_fcf, diluted_shares, cash, debt, minority_interest,
        [high] * years, discount_rate, terminal_growth,
    )
    if not low_value or not high_value:
        return None
    if not low_value["enterprise_value"] <= market_enterprise_value <= high_value["enterprise_value"]:
        return None

    for _ in range(80):
        middle = (low + high) / 2
        result = calculate_dcf(
            starting_fcf, diluted_shares, cash, debt, minority_interest,
            [middle] * years, discount_rate, terminal_growth,
        )
        if not result:
            return None
        if result["enterprise_value"] < market_enterprise_value:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def classify_cyclicality(
    ticker: str, name: str, industry: str, sector: str, summary: str | None
) -> tuple[bool, str]:
    """Classify cyclical industries using provider profile text and explicit ticker rules."""
    profile = " ".join((ticker, name, industry, sector, summary or "")).casefold()
    if ticker.upper() == "MU" or any(
        word in profile for word in ("memory semiconductor", "dram", "nand", "flash memory")
    ):
        return True, "Memory semiconductors"
    cyclical_terms = (
        "semiconductor", "chip", "automobile", "automotive", "steel", "mining",
        "oil & gas", "oil and gas", "energy", "chemical", "airline", "shipping",
        "commodity", "materials",
    )
    if any(term in profile for term in cyclical_terms):
        return True, "Cyclical industry"
    return False, "No explicit cyclical-industry match"


def industry_peer_tickers(ticker: str, industry: str, sector: str) -> list[str]:
    """Return a short peer set selected for the business industry, not cross-sector benchmarks."""
    profile = f"{ticker} {industry} {sector}".casefold()
    if ticker.upper() == "MU" or any(
        word in profile for word in ("memory semiconductor", "dram", "nand", "flash memory")
    ):
        return ["000660.KS", "005930.KS"]
    if "semiconductor" in profile or "chip" in profile:
        return ["NVDA", "AMD", "AVGO", "TSM", "ASML"]
    if "software" in profile:
        return ["CRM", "ADBE", "NOW", "ORCL", "INTU"]
    if "automotive" in profile or "automobile" in profile:
        return ["TM", "HMC", "BMW.DE", "MBG.DE", "STLA"]
    if "oil" in profile or "energy" in profile:
        return ["XOM", "CVX", "SHEL.L", "TTE.PA", "COP"]
    return []


def recommendation(score: float | None) -> str:
    if score is None:
        return "INSUFFICIENT DATA"
    if score >= 75:
        return "STRONG BUY"
    if score >= 60:
        return "BUY"
    if score >= 40:
        return "HOLD"
    if score >= 20:
        return "SELL"
    return "STRONG SELL"


def company_metrics(data: dict[str, Any]) -> dict[str, Any]:
    """Create comparable inputs while retaining source units and missing values."""
    info = data["info"]
    annual = financial_history(data)
    quarterly = quarterly_financial_history(data)
    history = data["history"]
    performance = performance_metrics(history)
    latest = annual[-1] if annual else {}
    previous = annual[-2] if len(annual) > 1 else {}

    def info_value(key: str) -> float | None:
        return _number(info.get(key))

    price = _number(history["Close"].dropna().iloc[-1]) if not history.empty else None
    basic_shares = info_value("sharesOutstanding")
    market_cap = info_value("marketCap")
    if market_cap is None and basic_shares is not None and price is not None:
        market_cap = basic_shares * price
    total_debt = info_value("totalDebt")
    debt_source = "Yahoo Finance company profile" if total_debt is not None else None
    if total_debt is None:
        total_debt = latest.get("Total debt")
        debt_source = "Latest annual balance sheet" if total_debt is not None else None
    cash = info_value("totalCash")
    cash_source = "Yahoo Finance company profile" if cash is not None else None
    if cash is None:
        cash = latest.get("Cash")
        cash_source = "Latest annual balance sheet" if cash is not None else None
    enterprise_value = info_value("enterpriseValue")
    if enterprise_value is None and market_cap is not None and total_debt is not None and cash is not None:
        enterprise_value = market_cap + total_debt - cash
    reported_revenue = latest.get("Revenue")
    revenue_source = (
        "Latest annual income statement" if reported_revenue is not None
        else "Yahoo Finance company profile" if info_value("totalRevenue") is not None
        else None
    )
    revenue = reported_revenue if reported_revenue is not None else info_value("totalRevenue")
    earnings = latest.get("Net income")
    fcf = latest.get("Free cash flow")
    ebitda = latest.get("EBITDA") or info_value("ebitda")
    net_debt = total_debt - cash if total_debt is not None and cash is not None else None
    if not basic_shares and market_cap and price:
        basic_shares = market_cap / price
    diluted_shares = latest.get("Diluted shares") or info_value("impliedSharesOutstanding")
    if diluted_shares is None:
        diluted_shares = basic_shares
    minority_interest = (
        latest.get("Minority interest")
        if latest.get("Minority interest") is not None
        else info_value("minorityInterest")
    )
    minority_interest_source = (
        "Latest annual balance sheet" if latest.get("Minority interest") is not None
        else "Yahoo Finance company profile" if info_value("minorityInterest") is not None
        else None
    )
    revenue_growth = (
        revenue / previous["Revenue"] - 1
        if revenue is not None and previous.get("Revenue") not in (None, 0)
        else info_value("revenueGrowth")
    )
    forward_pe = info_value("forwardPE")
    trailing_pe = info_value("trailingPE")
    net_income_margin = latest.get("Net margin")

    return {
        "ticker": data["ticker"],
        "name": info.get("longName") or info.get("shortName") or data["ticker"],
        "currency": info.get("currency") or "N/A",
        "exchange": info.get("fullExchangeName") or info.get("exchange") or "N/A",
        "country": info.get("country") or "N/A",
        "sector": info.get("sector") or "N/A",
        "industry": info.get("industry") or "N/A",
        "website": info.get("website"),
        "summary": info.get("longBusinessSummary"),
        "price": price,
        "price_date": history.index[-1],
        "52w_high": info_value("fiftyTwoWeekHigh") or _number(history["High"].tail(252).max()),
        "52w_low": info_value("fiftyTwoWeekLow") or _number(history["Low"].tail(252).min()),
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "shares": diluted_shares,
        "basic_shares": basic_shares,
        "diluted_shares": diluted_shares,
        "share_count_source": (
            "Diluted average shares" if latest.get("Diluted shares") is not None
            else "Provider implied shares" if info_value("impliedSharesOutstanding") is not None
            else "Basic shares outstanding proxy" if basic_shares is not None
            else None
        ),
        "minority_interest": minority_interest,
        "minority_interest_source": minority_interest_source,
        "revenue": revenue,
        "reported_revenue": reported_revenue,
        "revenue_source": revenue_source,
        "revenue_growth": revenue_growth,
        "revenue_cagr_3y": annual_cagr(annual, "Revenue", 3),
        "revenue_cagr_5y": annual_cagr(annual, "Revenue", 5),
        "reported_operating_margin": latest.get("Operating margin"),
        "gross_margin": latest.get("Gross margin") or info_value("grossMargins"),
        "operating_margin": latest.get("Operating margin") or info_value("operatingMargins"),
        "ebitda_margin": latest.get("EBITDA margin"),
        "net_margin": net_income_margin or info_value("profitMargins"),
        "net_income": earnings,
        "eps": latest.get("EPS") or info_value("trailingEps"),
        "trailing_eps": info_value("trailingEps"),
        "eps_growth": info_value("earningsGrowth"),
        "free_cash_flow": fcf,
        "historical_fcf": [row for row in annual if row.get("Free cash flow") is not None],
        "historical_fcf_summary": historical_fcf_summary(annual),
        "operating_cash_flow": latest.get("Operating cash flow"),
        "capex": abs(latest["Capital expenditure"]) if latest.get("Capital expenditure") is not None else None,
        "capex_margin": (
            abs(latest["Capital expenditure"]) / latest["Revenue"]
            if latest.get("Capital expenditure") is not None and latest.get("Revenue")
            else None
        ),
        "depreciation_margin": (
            latest["Depreciation and amortization"] / latest["Revenue"]
            if latest.get("Depreciation and amortization") is not None and latest.get("Revenue")
            else None
        ),
        "cash_tax_rate": (
            max(0.0, min(0.5, latest["Tax provision"] / latest["Pretax income"]))
            if latest.get("Tax provision") is not None and latest.get("Pretax income", 0) > 0
            else None
        ),
        "cash": cash,
        "cash_source": cash_source,
        "debt": total_debt,
        "debt_source": debt_source,
        "fcf_source": (
            "Latest annual cash-flow statement" if fcf is not None else None
        ),
        "net_debt": net_debt,
        "current_ratio": (
            info_value("currentRatio")
            if info_value("currentRatio") is not None
            else latest.get("Current assets") / latest.get("Current liabilities")
            if latest.get("Current assets") is not None and latest.get("Current liabilities")
            else None
        ),
        "quick_ratio": info_value("quickRatio"),
        "net_debt_ebitda": net_debt / ebitda if net_debt is not None and ebitda and ebitda > 0 else None,
        "pe": trailing_pe,
        "forward_pe": forward_pe,
        "peg": info_value("pegRatio"),
        "price_sales": info_value("priceToSalesTrailing12Months"),
        "price_book": info_value("priceToBook"),
        "ev_ebitda": info_value("enterpriseToEbitda"),
        "price_fcf": market_cap / fcf if market_cap and fcf and fcf > 0 else None,
        "fcf_yield": fcf / market_cap if fcf is not None and fcf > 0 and market_cap else None,
        "earnings_yield": 1 / trailing_pe if trailing_pe and trailing_pe > 0 else None,
        "dividend_yield": info_value("dividendYield"),
        "roe": info_value("returnOnEquity"),
        "roa": info_value("returnOnAssets"),
        "beta": info_value("beta"),
        "analyst_rating": info.get("recommendationKey"),
        "analyst_count": info_value("numberOfAnalystOpinions"),
        "analyst_target": info_value("targetMeanPrice"),
        "insider_ownership": info_value("heldPercentInsiders"),
        "institutional_ownership": info_value("heldPercentInstitutions"),
        "short_interest": info_value("shortPercentOfFloat"),
        "annual": annual,
        "quarterly": quarterly,
        "history": history,
        "performance": performance,
        "retrieved_at": data["retrieved_at"],
        "warnings": data["warnings"],
    }
