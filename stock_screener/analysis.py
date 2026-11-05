"""Market-data retrieval and transparent stock-analysis calculations."""

from __future__ import annotations

import logging
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

    return {
        "ticker": symbol,
        "info": info or {},
        "history": history,
        "statements": statements,
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
    statements = data["statements"]
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

        rows.append({
            "Period": period_end.strftime("%Y-%m-%d"),
            "Fiscal year": str(period_end.year),
            "Revenue": revenue,
            "Revenue growth": None,
            "Gross profit": gross_profit,
            "Gross margin": gross_profit / revenue if gross_profit is not None and revenue else None,
            "Operating income": operating_income,
            "Operating margin": operating_income / revenue if operating_income is not None and revenue else None,
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
    """Estimate per-share equity value using a simple, editable FCF DCF."""
    if (
        free_cash_flow is None or free_cash_flow <= 0
        or shares is None or shares <= 0 or cash is None or debt is None
        or discount_rate <= terminal_growth or terminal_growth < -1
    ):
        return None

    present_value = 0.0
    projected_fcf = free_cash_flow
    for year in range(1, years + 1):
        projected_fcf *= 1 + annual_growth
        present_value += projected_fcf / (1 + discount_rate) ** year

    terminal_value = projected_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    present_value += terminal_value / (1 + discount_rate) ** years
    equity_value = present_value + cash - debt
    return equity_value / shares


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
    history = data["history"]
    performance = performance_metrics(history)
    latest = annual[-1] if annual else {}
    previous = annual[-2] if len(annual) > 1 else {}

    def info_value(key: str) -> float | None:
        return _number(info.get(key))

    price = _number(history["Close"].dropna().iloc[-1]) if not history.empty else None
    shares = info_value("sharesOutstanding")
    market_cap = info_value("marketCap")
    if market_cap is None and shares is not None and price is not None:
        market_cap = shares * price
    total_debt = info_value("totalDebt")
    if total_debt is None:
        total_debt = latest.get("Total debt")
    cash = info_value("totalCash")
    if cash is None:
        cash = latest.get("Cash")
    enterprise_value = info_value("enterpriseValue")
    if enterprise_value is None and market_cap is not None and total_debt is not None and cash is not None:
        enterprise_value = market_cap + total_debt - cash
    revenue = latest.get("Revenue")
    earnings = latest.get("Net income")
    fcf = latest.get("Free cash flow")
    ebitda = latest.get("EBITDA") or info_value("ebitda")
    net_debt = total_debt - cash if total_debt is not None and cash is not None else None
    if not shares and market_cap and price:
        shares = market_cap / price
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
        "shares": shares,
        "revenue": revenue or info_value("totalRevenue"),
        "revenue_growth": revenue_growth,
        "revenue_cagr_3y": annual_cagr(annual, "Revenue", 3),
        "revenue_cagr_5y": annual_cagr(annual, "Revenue", 5),
        "gross_margin": latest.get("Gross margin") or info_value("grossMargins"),
        "operating_margin": latest.get("Operating margin") or info_value("operatingMargins"),
        "ebitda_margin": latest.get("EBITDA margin"),
        "net_margin": net_income_margin or info_value("profitMargins"),
        "net_income": earnings,
        "eps": latest.get("EPS") or info_value("trailingEps"),
        "trailing_eps": info_value("trailingEps"),
        "eps_growth": info_value("earningsGrowth"),
        "free_cash_flow": fcf if fcf is not None else info_value("freeCashflow"),
        "cash": cash,
        "debt": total_debt,
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
        "history": history,
        "performance": performance,
        "retrieved_at": data["retrieved_at"],
        "warnings": data["warnings"],
    }
