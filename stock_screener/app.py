from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import streamlit as st

from stock_screener.analysis import (
    BENCHMARKS,
    calculate_forecast_dcf,
    company_metrics,
    classify_cyclicality,
    dcf_confidence,
    fetch_stock_data,
    industry_peer_tickers,
    recommendation,
    reverse_dcf_growth,
    technical_indicators,
    validate_ticker,
)
from stock_screener.guidance import build_financial_forecast, fetch_official_guidance
from stock_screener.ui.components import render_company_heading
from stock_screener.ui.theme import apply_theme
from stock_screener.user_data import (
    DEFAULT_USER_DATA_PATH,
    load_user_data,
    save_user_data,
)

st.set_page_config(
    page_title="Equity Research | Stock Screener",
    page_icon=":material/monitoring:",
    layout="wide",
)

if "analysis_ticker" not in st.session_state:
    st.session_state["analysis_ticker"] = "NVDA"

if "local_user_data" not in st.session_state:
    local_user_data, local_user_data_error = load_user_data()
    st.session_state["local_user_data"] = local_user_data
    st.session_state["local_user_data_error"] = local_user_data_error

user_data = st.session_state["local_user_data"]
apply_theme(user_data["theme"])
if st.session_state.get("local_user_data_error"):
    st.sidebar.warning(st.session_state["local_user_data_error"])

research_sections = {
    "Financial performance": "Financials",
    "7 Indicators": "7 Indicators",
    "Valuation": "Valuation",
    "Technical analysis": "Technicals",
    "Risk analysis": "Risk analysis",
    "News & events": "Ownership & news",
}


def _activate_stock_research() -> None:
    st.session_state["workspace_navigation"] = "Stock Research"


with st.sidebar:
    st.markdown("### Equity research")
    workspace = st.radio(
        "Workspace",
        options=(
            "Dashboard",
            "Stock Research",
            "Compare Stocks",
            "Watchlist",
            "Portfolio",
            "Settings",
        ),
        key="workspace_navigation",
        label_visibility="collapsed",
    )
    st.markdown("**Stock Research**")
    research_label = st.radio(
        "Research section",
        options=tuple(research_sections),
        key="research_navigation",
        on_change=_activate_stock_research,
        label_visibility="collapsed",
    )
    if workspace == "Stock Research":
        navigation = research_sections[research_label]
    else:
        navigation = {
            "Dashboard": "Overview",
            "Compare Stocks": "Comparison",
            "Watchlist": "Watchlist",
            "Portfolio": "Portfolio",
            "Settings": "Settings",
        }[workspace]
    st.divider()
    peer_input = st.text_input(
        "Additional comparison tickers",
        placeholder="e.g. AMD, AVGO",
        help="Optional comma-separated peer symbols; use exchange suffixes when needed.",
        key="additional_peers",
    )
    st.markdown("**Permanent benchmarks**")
    st.caption("MSFT · GOOGL · META · AAPL")
    st.caption("Comparison prices and reported financials keep their original currencies.")

st.markdown("### Market research")
st.caption("Company fundamentals, valuation, and price trends in one research workspace.")
with st.form("ticker_search", border=False):
    search_columns = st.columns([1.5, 3.2, 1], vertical_alignment="bottom")
    with search_columns[0]:
        st.markdown("**Global stock search**")
    with search_columns[1]:
        ticker_input = st.text_input(
            "Ticker symbol",
            value=st.session_state["analysis_ticker"],
            placeholder="e.g. NVDA or RELIANCE.NS",
            help="Use an exchange suffix for non-US listings, such as .NS, .L, .DE, or .T.",
            key="global_ticker_search",
        )
    with search_columns[2]:
        submitted = st.form_submit_button(
            "Analyze",
            type="primary",
            icon=":material/search:",
            width="stretch",
        )
if submitted:
    try:
        st.session_state["analysis_ticker"] = validate_ticker(ticker_input)
    except ValueError as exc:
        st.error(str(exc))


@st.cache_data(ttl=900, max_entries=40, show_spinner=False)
def get_stock_data(ticker: str) -> dict[str, Any]:
    return fetch_stock_data(ticker)


@st.cache_data(ttl=3600, max_entries=40, show_spinner=False)
def get_company_guidance(ticker: str, currency: str) -> dict[str, Any]:
    return fetch_official_guidance(ticker, currency)


def _load_company(ticker: str) -> tuple[str, dict[str, Any] | None, str | None]:
    try:
        return ticker, get_stock_data(ticker), None
    except (RuntimeError, ValueError) as exc:
        return ticker, None, str(exc)
    except Exception as exc:
        return ticker, None, f"Unexpected data-provider error: {exc}"


def _persist_user_data(updated_data: dict[str, Any]) -> bool:
    try:
        save_user_data(updated_data)
    except OSError as exc:
        st.error(f"Could not save your local data: {exc}")
        return False
    st.session_state["local_user_data"] = updated_data
    st.session_state["local_user_data_error"] = None
    return True


def _open_research(ticker: str) -> None:
    st.session_state["analysis_ticker"] = ticker
    st.session_state["workspace_navigation"] = "Dashboard"


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _average(values: list[float | None]) -> float | None:
    available = [value for value in values if value is not None and pd.notna(value)]
    return sum(available) / len(available) if available else None


def _growth_score(value: float | None) -> float | None:
    return _clamp(50 + value * 100) if value is not None else None


def _score_company(
    company: dict[str, Any],
    valuation_score: float | None = None,
) -> dict[str, float | None]:
    gross = company["gross_margin"]
    operating = company["operating_margin"]
    roe = company["roe"]
    quality = _average([
        _clamp(gross * 100) if gross is not None else None,
        _clamp(operating * 100) if operating is not None else None,
        _clamp(50 + roe * 100) if roe is not None else None,
    ])

    leverage = company["net_debt_ebitda"]
    current_ratio = company["current_ratio"]
    fcf_yield = company["fcf_yield"]
    financial_health = _average([
        _clamp(70 - leverage * 10) if leverage is not None else None,
        _clamp(current_ratio * 40) if current_ratio is not None else None,
        _clamp(50 + fcf_yield * 500) if fcf_yield is not None else None,
    ])

    annual_margins = [
        row["Operating margin"]
        for row in company["annual"][-3:]
        if row.get("Operating margin") is not None
    ]
    margin_level = _average([
        _clamp(value * 100) for value in annual_margins
    ])
    margin_stability = (
        _clamp(100 - pd.Series(annual_margins).std(ddof=0) * 200)
        if len(annual_margins) > 1 else None
    )
    moat_proxy = _average([margin_level, margin_stability])
    growth = _average([
        _growth_score(company["revenue_growth"]),
        _growth_score(company["revenue_cagr_3y"]),
        _growth_score(company["eps_growth"]),
    ])
    history = company["history"]
    technical = technical_indicators(history)
    latest = technical.iloc[-1]
    technical_score = _average([
        (
            75.0 if latest["Close"] > latest["SMA 200"] else 25.0
        ) if pd.notna(latest["SMA 200"]) else None,
        70.0 if latest["MACD"] > latest["MACD signal"] else 30.0,
        50.0 if pd.isna(latest["RSI 14"]) else (
            55.0 if 40 <= latest["RSI 14"] <= 65 else
            35.0 if latest["RSI 14"] > 70 or latest["RSI 14"] < 30 else 50.0
        ),
    ])

    performance = company["performance"]
    beta = company["beta"]
    drawdown = performance.get("Maximum drawdown")
    risk = _average([
        _clamp(beta * 30) if beta is not None else None,
        _clamp(abs(drawdown) * 150) if drawdown is not None else None,
        _clamp(50 + leverage * 10) if leverage is not None else None,
    ])
    dimensions = {
        "Business quality": quality,
        "Financial health": financial_health,
        "Moat proxy": moat_proxy,
        "Growth": growth,
        "Valuation": valuation_score,
        "Technical strength": technical_score,
        "Risk": risk,
    }
    coverage = len([value for value in dimensions.values() if value is not None]) / 7 * 100
    weights = {
        "Business quality": 0.15,
        "Financial health": 0.15,
        "Moat proxy": 0.15,
        "Growth": 0.20,
        "Valuation": 0.20,
        "Technical strength": 0.05,
        "Risk": 0.10,
    }
    available_weight = sum(weights[key] for key, value in dimensions.items() if value is not None)
    score = None
    if available_weight:
        score = sum(
            weights[key] * (100 - value if key == "Risk" else value)
            for key, value in dimensions.items()
            if value is not None
        ) / available_weight
    dimensions["Overall score"] = score
    dimensions["Coverage"] = coverage
    return dimensions


def _valuation_score(
    fair_values: list[float | None],
    current_price: float | None,
    confidence: float | None,
    relative_multiple_score: float | None,
    reverse_growth_gap: float | None,
) -> float | None:
    upside_scores = [
        _clamp(50 + max(-0.75, min(1.0, value / current_price - 1)) * 40)
        for value in fair_values
        if value is not None and current_price is not None and current_price > 0
    ]
    margin_of_safety_scores = [
        _clamp(50 + max(-0.75, min(0.6, (value - current_price) / value)) * 50)
        for value in fair_values
        if value is not None and value > 0 and current_price is not None and current_price > 0
    ]
    evidence = [*upside_scores, *margin_of_safety_scores]
    if relative_multiple_score is not None:
        evidence.append(relative_multiple_score)
    if reverse_growth_gap is not None:
        evidence.append(_clamp(50 + max(-0.5, min(0.5, -reverse_growth_gap)) * 40))
    if not evidence:
        return None

    raw_score = sum(evidence) / len(evidence)
    reliability = max(0.0, min(1.0, (confidence or 0) / 100))
    return _clamp(50 + (raw_score - 50) * reliability)


def _fmt(value: Any, currency: str | None = None, kind: str = "number") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    number = float(value)
    if kind == "percent":
        return f"{number:.1%}"
    if kind == "money":
        return f"{currency or ''} {number:,.2f}".strip()
    if kind == "large_money":
        return f"{currency or ''} {number / 1e9:,.2f}B".strip()
    if kind == "multiple":
        return f"{number:.2f}x"
    if kind == "score":
        return f"{number:.0f}/100"
    return f"{number:,.2f}"


HEATMAP_COLORS = (
    "#e57373",
    "#ef9a72",
    "#f4b183",
    "#ffe082",
    "#dce775",
    "#aed581",
    "#81c784",
)


def _heatmap_table(
    display: pd.DataFrame,
    raw: pd.DataFrame,
    higher_is_better: set[str],
    lower_is_better: set[str],
    columns: list[str],
    center_is_best: set[str] | None = None,
) -> Any:
    center_is_best = center_is_best or set()

    def color_row(row: pd.Series) -> list[str]:
        metric = row.name
        if (
            metric not in higher_is_better
            and metric not in lower_is_better
            and metric not in center_is_best
        ):
            return [""] * len(row)

        values = {
            column: raw.loc[metric, column]
            for column in columns
            if column in raw.columns
            and isinstance(raw.loc[metric, column], (int, float))
            and pd.notna(raw.loc[metric, column])
        }
        if not values:
            return [""] * len(row)

        minimum = min(values.values())
        maximum = max(values.values())
        styles = []
        for column in row.index:
            value = values.get(column)
            if value is None:
                styles.append("")
                continue
            if metric in center_is_best:
                position = 1 - abs(value - 50) / 50
            else:
                position = (value - minimum) / (maximum - minimum) if maximum != minimum else 0.5
            if metric in lower_is_better:
                position = 1 - position
            position = max(0.0, min(1.0, position))
            color_index = round(position * (len(HEATMAP_COLORS) - 1))
            styles.append(
                f"background-color: {HEATMAP_COLORS[color_index]}; color: #242424"
            )
        return styles

    return display.style.apply(color_row, axis=1)


def _render_heatmap_legend() -> None:
    swatches = "".join(
        f'<span style="display:inline-block;width:28px;height:12px;background:{color};"></span>'
        for color in HEATMAP_COLORS
    )
    st.html(
        f'<div role="img" aria-label="Relative heatmap: less favorable in red, mid-range in yellow, '
        f'more favorable in green" style="display:flex;align-items:center;gap:8px;margin:4px 0 8px;">'
        f'<span style="font-size:0.85rem;">Less favorable</span>'
        f'<span style="display:inline-flex;overflow:hidden;border-radius:4px;">{swatches}</span>'
        f'<span style="font-size:0.85rem;">More favorable</span></div>'
    )


def _build_comparison(
    companies: dict[str, dict[str, Any]],
    scores: dict[str, dict[str, float | None]],
    fair_values: dict[str, float | None],
    selected_group: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    definitions = {
        "Price": ("price", "Last adjusted close; local trading currency.", "money"),
        "Market cap": ("market_cap", "Latest reported equity market value; local currency.", "large_money"),
        "Enterprise value": ("enterprise_value", "Market capitalization plus debt, less cash; local currency.", "large_money"),
        "Revenue": ("revenue", "Latest available annual revenue; reported fiscal period.", "large_money"),
        "Revenue growth": ("revenue_growth", "Latest annual year-over-year revenue growth.", "percent"),
        "Revenue CAGR (3y)": ("revenue_cagr_3y", "Three-year revenue compound annual growth, when periods are available.", "percent"),
        "Revenue CAGR (5y)": ("revenue_cagr_5y", "Five-year revenue compound annual growth, when periods are available.", "percent"),
        "Gross margin": ("gross_margin", "Gross profit divided by revenue.", "percent"),
        "Operating margin": ("operating_margin", "Operating income divided by revenue.", "percent"),
        "EBITDA margin": ("ebitda_margin", "EBITDA divided by revenue.", "percent"),
        "Net margin": ("net_margin", "Net income divided by revenue.", "percent"),
        "ROE": ("roe", "Return on equity, as reported by the provider.", "percent"),
        "ROA": ("roa", "Return on assets, as reported by the provider.", "percent"),
        "EPS growth": ("eps_growth", "Latest provider-reported earnings growth estimate.", "percent"),
        "Free cash flow": ("free_cash_flow", "Operating cash flow less capital expenditure; local currency.", "large_money"),
        "P/E": ("pe", "Trailing price-to-earnings multiple; N/M when not reported.", "multiple"),
        "Forward P/E": ("forward_pe", "Provider-reported forward price-to-earnings multiple.", "multiple"),
        "PEG": ("peg", "Provider-reported price/earnings-to-growth multiple.", "multiple"),
        "Price/sales": ("price_sales", "Price-to-sales multiple.", "multiple"),
        "Price/book": ("price_book", "Price-to-book multiple.", "multiple"),
        "EV/EBITDA": ("ev_ebitda", "Enterprise value divided by EBITDA.", "multiple"),
        "Price/FCF": ("price_fcf", "Market capitalization divided by positive free cash flow.", "multiple"),
        "FCF yield": ("fcf_yield", "Free cash flow divided by market capitalization.", "percent"),
        "Earnings yield": ("earnings_yield", "Inverse of positive trailing P/E; N/M for negative earnings.", "percent"),
        "Dividend yield": ("dividend_yield", "Provider-reported forward dividend yield.", "percent"),
        "Cash": ("cash", "Latest reported cash and cash equivalents; local currency.", "large_money"),
        "Total debt": ("debt", "Latest reported total debt; local currency.", "large_money"),
        "Net debt": ("net_debt", "Total debt less cash; negative indicates net cash.", "large_money"),
        "Current ratio": ("current_ratio", "Current assets divided by current liabilities.", "multiple"),
        "Net debt/EBITDA": ("net_debt_ebitda", "Net debt divided by positive EBITDA.", "multiple"),
        "1-month return": ("1 month return", "Price return over approximately one month.", "percent"),
        "6-month return": ("6 month return", "Price return over approximately six months.", "percent"),
        "YTD return": ("YTD return", "Price return since the start of the current calendar year.", "percent"),
        "1-year return": ("1 year return", "Price return over approximately one year.", "percent"),
        "3-year return": ("3 year return", "Price return over approximately three years.", "percent"),
        "5-year return": ("5 year return", "Price return over approximately five years.", "percent"),
        "Beta": ("beta", "Provider-reported market beta.", "number"),
        "Maximum drawdown": ("Maximum drawdown", "Largest peak-to-trough price decline within available five-year history.", "percent"),
        "Business quality": ("Business quality", "Profitability/return proxy; not a qualitative business review.", "score"),
        "Financial health": ("Financial health", "Cash-flow, liquidity, and leverage proxy.", "score"),
        "Moat proxy": ("Moat proxy", "Profitability and return proxy; not a researched moat assessment.", "score"),
        "Growth score": ("Growth", "Revenue and earnings growth proxy.", "score"),
        "Valuation score": ("Valuation", "Based on the editable DCF's implied upside; N/A when DCF is unavailable.", "score"),
        "Risk score": ("Risk", "Proxy score where higher means more risk; deducted from the overall score.", "score"),
        "Overall score": ("Overall score", "Weighted, data-available dimensions; risk is subtracted.", "score"),
        "Rating": ("rating", "Rule-based rating from available weighted dimensions, not investment advice.", "text"),
        "DCF fair value": ("fair_value", "Base-case DCF per-share estimate; editable assumptions.", "money"),
        "DCF implied upside": ("upside", "Base-case DCF value compared with the last adjusted close.", "percent"),
    }
    groups = {
        "All metrics": list(definitions),
        "Financials": [
            "Revenue", "Revenue growth", "Revenue CAGR (3y)", "Revenue CAGR (5y)",
            "Gross margin", "Operating margin", "EBITDA margin", "Net margin",
            "ROE", "ROA", "EPS growth", "Free cash flow", "Cash", "Total debt",
            "Net debt", "Current ratio", "Net debt/EBITDA",
        ],
        "Valuation": [
            "P/E", "Forward P/E", "PEG", "Price/sales", "Price/book", "EV/EBITDA",
            "Price/FCF", "FCF yield", "Earnings yield", "Dividend yield", "Valuation score",
            "DCF fair value", "DCF implied upside",
        ],
        "Growth": ["Revenue growth", "Revenue CAGR (3y)", "Revenue CAGR (5y)", "EPS growth", "Growth score"],
        "Price performance": [
            "1-month return", "6-month return", "YTD return", "1-year return",
            "3-year return", "5-year return", "Beta", "Maximum drawdown", "Risk score",
        ],
        "Investment quality": ["Business quality", "Financial health", "Moat proxy", "Growth score", "Valuation score", "Risk score", "Overall score", "Rating", "DCF fair value", "DCF implied upside"],
    }
    chosen = groups[selected_group]
    tickers = list(companies)
    raw = pd.DataFrame(index=chosen, columns=tickers, dtype=object)
    display = pd.DataFrame(index=chosen, columns=tickers, dtype=object)
    for label in chosen:
        key, _, kind = definitions[label]
        for ticker, company in companies.items():
            if key == "rating":
                value: Any = recommendation(scores[ticker]["Overall score"])
            elif key == "fair_value":
                value = fair_values.get(ticker)
            elif key == "upside":
                fair_value = fair_values.get(ticker)
                value = fair_value / company["price"] - 1 if fair_value and company["price"] else None
            elif key in ("Business quality", "Financial health", "Moat proxy", "Growth", "Valuation", "Risk", "Overall score"):
                value = scores[ticker].get(key)
            elif key in company["performance"]:
                value = company["performance"].get(key)
            else:
                value = company.get(key)
            not_meaningful = (
                label in ("P/E", "Forward P/E", "Price/FCF")
                and value is not None and value <= 0
            ) or (
                label == "Price/FCF"
                and company["free_cash_flow"] is not None
                and company["free_cash_flow"] <= 0
            ) or (
                label == "FCF yield"
                and company["free_cash_flow"] is not None
                and company["free_cash_flow"] <= 0
            ) or (
                label == "Earnings yield"
                and company["trailing_eps"] is not None
                and company["trailing_eps"] <= 0
            )
            raw.loc[label, ticker] = None if not_meaningful else value
            display.loc[label, ticker] = (
                "N/M" if not_meaningful
                else str(value) if kind == "text" else _fmt(value, company["currency"], kind)
            )

    definitions_table = pd.DataFrame(
        {"Metric": chosen, "Definition": [definitions[label][1] for label in chosen]}
    )
    shown = display.copy()
    shown.insert(0, "Definition", definitions_table["Definition"].values)
    shown.index.name = "Metric"

    higher_is_better = {
        "Revenue growth", "Revenue CAGR (3y)", "Revenue CAGR (5y)", "Gross margin",
        "Operating margin", "EBITDA margin", "Net margin", "ROE", "ROA", "EPS growth",
        "FCF yield", "Dividend yield", "Cash", "Current ratio", "1-month return",
        "6-month return", "YTD return", "1-year return", "3-year return", "5-year return",
        "Business quality", "Financial health", "Moat proxy", "Growth score", "Valuation score",
        "Earnings yield", "Overall score", "DCF implied upside", "Maximum drawdown",
    }
    lower_is_better = {
        "P/E", "Forward P/E", "PEG", "Price/sales", "Price/book", "EV/EBITDA", "Price/FCF",
        "Net debt/EBITDA", "Beta", "Risk score",
    }

    return _heatmap_table(shown, raw, higher_is_better, lower_is_better, tickers), raw


def _render_research_comparison(
    title: str,
    metric_group: str,
    companies: dict[str, dict[str, Any]],
    scores: dict[str, dict[str, float | None]],
    fair_values: dict[str, float | None],
    note: str,
) -> None:
    st.subheader(title)
    comparison, _ = _build_comparison(companies, scores, fair_values, metric_group)
    st.dataframe(
        comparison,
        height=520,
        alt=f"{metric_group} comparison across the analyzed company and available benchmarks",
    )
    _render_heatmap_legend()
    st.caption(note)


def _build_seven_indicator_comparison(
    companies: dict[str, dict[str, Any]],
    fair_values: dict[str, float | None],
    ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame, set[str], set[str], set[str]]:
    entries = [
        ("1 · Revenue growth and quality", "Revenue growth YoY", "Latest reported annual revenue growth.", "revenue_growth", "percent", "higher"),
        ("1 · Revenue growth and quality", "Revenue CAGR (3y)", "Three-year revenue CAGR from reported annual statements.", "revenue_cagr_3y", "percent", "higher"),
        ("1 · Revenue growth and quality", "Revenue CAGR (5y)", "Five-year revenue CAGR from reported annual statements.", "revenue_cagr_5y", "percent", "higher"),
        ("1 · Revenue growth and quality", "Organic / recurring growth", "The current data provider does not split organic, recurring, acquisition-driven, or backlog growth.", "unavailable", "text", "none"),
        ("2 · Profitability and margins", "Gross margin", "Latest reported gross profit divided by revenue.", "gross_margin", "percent", "higher"),
        ("2 · Profitability and margins", "Operating margin", "Latest reported operating income divided by revenue.", "operating_margin", "percent", "higher"),
        ("2 · Profitability and margins", "EBITDA margin", "EBITDA divided by revenue where statements provide the required components.", "ebitda_margin", "percent", "higher"),
        ("2 · Profitability and margins", "Net profit margin", "Latest reported net income divided by revenue.", "net_margin", "percent", "higher"),
        ("2 · Profitability and margins", "Free cash flow margin", "Free cash flow divided by revenue; FCF is operating cash flow less capital expenditure.", "fcf_margin", "percent", "higher"),
        ("2 · Profitability and margins", "Operating margin change (3y)", "Change in operating margin versus the closest reported period at least three years earlier.", "operating_margin_change", "percentage_points", "higher"),
        ("3 · Competitive moat and market position", "Gross margin (pricing / differentiation proxy)", "A margin is only an indirect proxy; market share and pricing power are not directly measured.", "gross_margin", "percent", "higher"),
        ("3 · Competitive moat and market position", "ROE (returns proxy)", "Provider-reported return on equity; not evidence of a moat by itself.", "roe", "percent", "higher"),
        ("3 · Competitive moat and market position", "Market share / retention / switching costs", "Market share, customer retention, switching costs, patents, and customer concentration are not available in this feed.", "unavailable", "text", "none"),
        ("4 · Cash flow and financial health", "Operating cash flow", "Latest annual cash flow from operations; reported currency.", "operating_cash_flow", "large_money", "none"),
        ("4 · Cash flow and financial health", "Free cash flow", "Operating cash flow less capital expenditure; reported currency.", "free_cash_flow", "large_money", "none"),
        ("4 · Cash flow and financial health", "FCF conversion (FCF / net income)", "Calculated only when reported net income is positive.", "fcf_conversion", "percent", "higher"),
        ("4 · Cash flow and financial health", "Net debt / EBITDA", "Negative values indicate net cash; requires positive EBITDA.", "net_debt_ebitda", "multiple", "lower"),
        ("4 · Cash flow and financial health", "Cash reserves", "Latest available cash balance; reported currency.", "cash", "large_money", "none"),
        ("4 · Cash flow and financial health", "Capital expenditure", "Latest annual capex outflow, shown as a positive amount; reported currency.", "capital_expenditure", "large_money", "none"),
        ("4 · Cash flow and financial health", "Interest coverage", "Not available from the current data provider.", "unavailable", "text", "none"),
        ("5 · Valuation and margin of safety", "Forward P/E", "Provider-reported forward price-to-earnings multiple.", "forward_pe", "multiple", "lower"),
        ("5 · Valuation and margin of safety", "PEG", "Provider-reported price/earnings-to-growth multiple.", "peg", "multiple", "lower"),
        ("5 · Valuation and margin of safety", "EV / EBITDA", "Provider-reported enterprise-value-to-EBITDA multiple.", "ev_ebitda", "multiple", "lower"),
        ("5 · Valuation and margin of safety", "Price / FCF", "Market capitalization divided by positive free cash flow.", "price_fcf", "multiple", "lower"),
        ("5 · Valuation and margin of safety", "FCF yield", "Free cash flow divided by market capitalization.", "fcf_yield", "percent", "higher"),
        ("5 · Valuation and margin of safety", "DCF value / share", "Target-only base DCF using the assumptions shown in Valuation; not calculated for benchmark stocks.", "fair_value", "money", "none"),
        ("5 · Valuation and margin of safety", "DCF margin of safety", "Calculated as (DCF value − price) / DCF value. Target only; N/A when DCF inputs are incomplete.", "margin_of_safety", "percent", "higher"),
        ("5 · Valuation and margin of safety", "Historical valuation multiples", "Three-/five-year historical valuation multiples are not provided by the current feed.", "unavailable", "text", "none"),
        ("6 · Management and capital allocation", "ROE", "Provider-reported return on equity.", "roe", "percent", "higher"),
        ("6 · Management and capital allocation", "Insider ownership", "Latest aggregate insider ownership reported by the provider.", "insider_ownership", "percent", "none"),
        ("6 · Management and capital allocation", "Dividend yield", "Provider-reported forward dividend yield; buybacks and dividend history are not modeled.", "dividend_yield", "percent", "none"),
        ("6 · Management and capital allocation", "ROIC / dilution / execution record", "ROIC, share dilution, acquisition returns, and historical guidance accuracy are not available in this feed.", "unavailable", "text", "none"),
        ("7 · Momentum and technical positioning", "Price vs 50-day SMA", "Adjusted closing price relative to the 50-day simple moving average.", "sma50_distance", "percent", "higher"),
        ("7 · Momentum and technical positioning", "Price vs 200-day SMA", "Adjusted closing price relative to the 200-day simple moving average.", "sma200_distance", "percent", "higher"),
        ("7 · Momentum and technical positioning", "RSI (14)", "Calculated from daily adjusted closing prices; values above 70 or below 30 can indicate extreme momentum.", "rsi", "number", "center"),
        ("7 · Momentum and technical positioning", "MACD signal", "Bullish when MACD is above its signal line; calculated from daily adjusted closing prices.", "macd_signal", "text", "none"),
        ("7 · Momentum and technical positioning", "1-year relative return vs benchmark mean", "Company's one-year price return minus the mean return of available permanent benchmarks.", "relative_return", "percent", "higher"),
        ("7 · Momentum and technical positioning", "Maximum drawdown (5y)", "Largest peak-to-trough decline within available five-year price history.", "Maximum drawdown", "percent", "higher"),
        ("7 · Momentum and technical positioning", "Volume trend / institutional accumulation", "Volume trend and institutional accumulation are not assessed by the current feed.", "unavailable", "text", "none"),
    ]

    benchmark_returns = [
        company["performance"].get("1 year return")
        for symbol, company in companies.items()
        if symbol in BENCHMARKS and company["performance"].get("1 year return") is not None
    ]
    benchmark_average_return = (
        sum(benchmark_returns) / len(benchmark_returns) if benchmark_returns else None
    )
    raw = pd.DataFrame(index=[entry[1] for entry in entries], columns=list(companies), dtype=object)
    display = pd.DataFrame(index=[entry[1] for entry in entries], columns=list(companies), dtype=object)
    categories = {}
    definitions = {}
    directions = {}

    for category, label, definition, key, kind, direction in entries:
        categories[label] = category
        definitions[label] = definition
        directions[label] = direction
        for symbol, company in companies.items():
            annual = company["annual"]
            latest = annual[-1] if annual else {}
            value: Any = None
            if key == "unavailable":
                value = "Unavailable"
            elif key in ("revenue_growth", "revenue_cagr_3y", "revenue_cagr_5y", "gross_margin", "operating_margin", "ebitda_margin", "net_margin", "net_debt_ebitda", "forward_pe", "peg", "ev_ebitda", "price_fcf", "fcf_yield", "cash", "roe", "insider_ownership", "dividend_yield", "Maximum drawdown"):
                value = company.get(key)
                if key == "Maximum drawdown":
                    value = company["performance"].get(key)
            elif key == "operating_cash_flow":
                value = latest.get("Operating cash flow")
            elif key == "free_cash_flow":
                value = company["free_cash_flow"]
            elif key == "capital_expenditure":
                value = abs(latest["Capital expenditure"]) if latest.get("Capital expenditure") is not None else None
            elif key == "fcf_margin":
                value = company["free_cash_flow"] / company["revenue"] if company["free_cash_flow"] is not None and company["revenue"] else None
            elif key == "fcf_conversion":
                value = company["free_cash_flow"] / company["net_income"] if company["free_cash_flow"] is not None and company["net_income"] and company["net_income"] > 0 else None
            elif key == "operating_margin_change":
                comparable = next(
                    (
                        row for row in reversed(annual[:-1])
                        if int(latest["Fiscal year"]) - int(row["Fiscal year"]) >= 3
                        and row.get("Operating margin") is not None
                    ),
                    None,
                )
                value = latest.get("Operating margin") - comparable["Operating margin"] if comparable and latest.get("Operating margin") is not None else None
            elif key in ("fair_value", "margin_of_safety"):
                fair_value = fair_values.get(symbol)
                value = fair_value if key == "fair_value" else (
                    (fair_value - company["price"]) / fair_value
                    if symbol == ticker and fair_value and company["price"] is not None
                    else None
                )
            elif key in ("sma50_distance", "sma200_distance", "rsi", "macd_signal"):
                technical = technical_indicators(company["history"])
                latest_technical = technical.iloc[-1]
                if key == "rsi":
                    value = latest_technical.get("RSI 14")
                elif key == "macd_signal":
                    value = (
                        "Bullish" if latest_technical["MACD"] > latest_technical["MACD signal"]
                        else "Bearish"
                    )
                else:
                    average = latest_technical.get("SMA 50" if key == "sma50_distance" else "SMA 200")
                    value = latest_technical["Close"] / average - 1 if pd.notna(average) and average else None
            elif key == "relative_return":
                company_return = company["performance"].get("1 year return")
                value = (
                    company_return - benchmark_average_return
                    if company_return is not None and benchmark_average_return is not None
                    else None
                )

            raw.loc[label, symbol] = value
            if isinstance(value, str) or value is None or pd.isna(value):
                shown_value = value if isinstance(value, str) else "N/A"
            elif kind == "percent" or kind == "percentage_points":
                shown_value = f"{value * 100:+.1f} pp" if kind == "percentage_points" else f"{value:.1%}"
            elif kind == "money":
                shown_value = _fmt(value, company["currency"], "money")
            elif kind == "large_money":
                shown_value = _fmt(value, company["currency"], "large_money")
            elif kind == "multiple":
                shown_value = _fmt(value, kind="multiple")
            else:
                shown_value = _fmt(value)
            display.loc[label, symbol] = shown_value

    display.insert(0, "Definition", pd.Series(definitions))
    display.insert(0, "Indicator", pd.Series(categories))
    higher = {label for label, direction in directions.items() if direction == "higher"}
    lower = {label for label, direction in directions.items() if direction == "lower"}
    centered = {label for label, direction in directions.items() if direction == "center"}
    return (
        _heatmap_table(display, raw, higher, lower, list(companies), centered),
        raw,
        higher,
        lower,
        centered,
    )


def _chart_history(
    companies: dict[str, dict[str, Any]], days: int, include_benchmarks: bool = True
) -> pd.DataFrame:
    frames = []
    selected = list(companies.items()) if include_benchmarks else list(companies.items())[:1]
    for ticker, company in selected:
        history = company["history"]["Close"].dropna().tail(days)
        if history.empty:
            continue
        frame = history.rename(f"{company['name']} ({ticker})").to_frame()
        frame = frame / frame.iloc[0, 0] * 100
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, axis=1).sort_index()
    combined.index.name = "Date"
    return combined


def _financial_overlay(
    companies: dict[str, dict[str, Any]], metric_name: str
) -> pd.DataFrame:
    frames = []
    for ticker, company in companies.items():
        history = company["annual"]
        points = [
            {"Fiscal year": row["Fiscal year"], "value": row.get(metric_name)}
            for row in history
            if row.get(metric_name) is not None and pd.notna(row.get(metric_name))
        ]
        if not points:
            continue
        frame = pd.DataFrame(points).drop_duplicates("Fiscal year", keep="last")
        series = frame.set_index("Fiscal year")["value"]
        if metric_name in ("Revenue", "Net income", "EPS", "Free cash flow"):
            initial = next((value for value in series if value is not None and value > 0), None)
            if initial:
                series = series / initial * 100
        elif "margin" in metric_name.casefold() or metric_name == "Revenue growth":
            series = series * 100
        series.name = f"{company['name']} ({ticker})"
        frames.append(series)
    if not frames:
        return pd.DataFrame()
    result = pd.concat(frames, axis=1).sort_index()
    result.index.name = "Fiscal year"
    return result


def _format_annual(annual: list[dict[str, Any]], currency: str) -> pd.DataFrame:
    fields = [
        "Period", "Revenue", "Revenue growth", "Gross margin", "Operating income",
        "Operating margin", "Net income", "Net margin", "EPS", "Free cash flow",
        "Operating cash flow", "Capital expenditure",
    ]
    frame = pd.DataFrame(annual)
    if frame.empty:
        return frame
    frame = frame[fields].copy()
    for column in fields:
        if column in ("Revenue growth", "Gross margin", "Operating margin", "Net margin"):
            frame[column] = frame[column].map(lambda value: _fmt(value, kind="percent"))
        elif column not in ("Period", "EPS"):
            frame[column] = frame[column].map(lambda value: _fmt(value, currency, "large_money"))
        elif column == "EPS":
            frame[column] = frame[column].map(lambda value: _fmt(value, currency))
    return frame


ticker = st.session_state["analysis_ticker"]
try:
    ticker = validate_ticker(ticker)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

peer_tickers = []
invalid_peers = []
for peer in peer_input.split(","):
    candidate = peer.strip()
    if not candidate:
        continue
    try:
        candidate = validate_ticker(candidate)
        if candidate not in peer_tickers and candidate != ticker and candidate not in BENCHMARKS:
            peer_tickers.append(candidate)
    except ValueError:
        invalid_peers.append(candidate)
if invalid_peers:
    st.sidebar.warning(f"Skipped invalid peer ticker(s): {', '.join(invalid_peers)}")
peer_tickers = peer_tickers[:5]

with st.spinner(f"Loading {ticker} and identifying industry peers…"):
    target_symbol, initial_target_data, target_error = _load_company(ticker)
if initial_target_data is None:
    st.error(target_error or f"No market data is available for {ticker}.")
    st.info("Check the symbol and exchange suffix, then try again.")
    st.stop()

initial_target = company_metrics(initial_target_data)
cyclical_industry, industry_classification = classify_cyclicality(
    ticker,
    initial_target["name"],
    initial_target["industry"],
    initial_target["sector"],
    initial_target["summary"],
)
industry_peers = industry_peer_tickers(
    ticker, initial_target["industry"], initial_target["sector"]
)
if ticker == "MU":
    industry_peers = ["000660.KS", "005930.KS"]
industry_peers = [
    symbol for symbol in industry_peers
    if symbol != ticker and symbol not in BENCHMARKS
]
personal_symbols = (
    user_data["watchlist"]
    if navigation == "Watchlist"
    else [position["ticker"] for position in user_data["portfolio"]]
    if navigation == "Portfolio"
    else []
)
symbols = list(dict.fromkeys([
    ticker, *BENCHMARKS, *industry_peers, *peer_tickers, *personal_symbols,
]))
fetched: dict[str, dict[str, Any]] = {ticker: initial_target_data}
failures: dict[str, str] = {}

with st.spinner(f"Loading benchmarks and industry peers for {ticker}…"):
    with ThreadPoolExecutor(max_workers=min(5, max(1, len(symbols) - 1))) as executor:
        futures = {
            executor.submit(_load_company, symbol): symbol
            for symbol in symbols if symbol != ticker
        }
        for future in as_completed(futures):
            symbol, data, error = future.result()
            if data is not None:
                fetched[symbol] = data
            elif error:
                failures[symbol] = error

companies = {symbol: company_metrics(fetched[symbol]) for symbol in symbols if symbol in fetched}
target = companies[ticker]
with st.spinner(f"Checking latest official SEC filings for {ticker}…"):
    target_guidance = get_company_guidance(ticker, target["currency"])
for symbol, message in failures.items():
    if symbol != ticker:
        st.warning(f"{symbol} could not be loaded and is omitted from comparisons: {message}")

for warning in target["warnings"]:
    st.warning(warning)

with st.expander("Edit valuation assumptions", expanded=False):
    observed_growth = target["revenue_cagr_3y"]
    if observed_growth is None:
        observed_growth = target["revenue_growth"] or 0.05
    default_growth = int(max(-20, min(40, observed_growth * 100)))
    left, middle, right, last = st.columns(4)
    with left:
        growth_pct = st.slider(
            "Annual free cash flow growth",
            min_value=-20,
            max_value=40,
            value=default_growth,
            step=1,
            format="%d%%",
            key="dcf_growth",
            help="Defaults to observed three-year revenue CAGR when available; this is a user assumption, not a forecast.",
        )
    with middle:
        wacc_pct = st.slider(
            "Discount rate / WACC",
            min_value=4,
            max_value=18,
            value=9,
            step=1,
            format="%d%%",
            key="dcf_wacc",
        )
    with right:
        terminal_pct = st.slider(
            "Terminal growth rate",
            min_value=0,
            max_value=4,
            value=2,
            step=1,
            format="%d%%",
            key="dcf_terminal",
        )
    with last:
        projection_years = st.selectbox(
            "Projection period",
            options=(5, 7, 10),
            index=0,
            format_func=lambda value: f"{value} years",
            key="dcf_years",
        )

    st.markdown("**Scenario assumptions**")
    st.caption(
        "The standard DCF is built from forecast revenue, margins, operating cash flow, and capital expenditure. "
        "The separate normalized DCF uses its editable starting FCF and the annual FCF growth schedule below."
    )
    observed_revenue_growth = target["revenue_growth"]
    if observed_revenue_growth is None:
        observed_revenue_growth = target["revenue_cagr_3y"] or 0.05
    default_revenue_growth = int(max(-20, min(40, observed_revenue_growth * 100)))
    scenario_offsets = {
        "Bear": (-8, -5, 2, -1, -5, 4),
        "Conservative": (-3, -2, 1, 0, -2, 2),
        "Base": (0, 0, 0, 0, 0, 0),
        "Bull": (3, 2, -1, 1, 2, -1),
        "Extreme Bull": (8, 5, -2, 2, 5, -3),
    }
    growth_columns = [
        f"Normalized DCF FCF growth Y{year} (%)"
        for year in range(1, projection_years + 1)
    ]
    revenue_growth_columns = [
        f"Revenue growth Y{year} (%)" for year in range(1, projection_years + 1)
    ]
    rows = []
    for name, (
        growth_offset, revenue_offset, wacc_offset, terminal_offset,
        margin_offset, capex_offset,
    ) in scenario_offsets.items():
        row = {"Scenario": name}
        for column in growth_columns:
            row[column] = growth_pct + growth_offset
        for column in revenue_growth_columns:
            row[column] = default_revenue_growth + revenue_offset
        row["WACC (%)"] = wacc_pct + wacc_offset
        row["Terminal growth (%)"] = terminal_pct + terminal_offset
        row["Operating margin (%)"] = (
            target["reported_operating_margin"] * 100 + margin_offset
            if target["reported_operating_margin"] is not None else None
        )
        row["Tax rate (%)"] = (
            target["cash_tax_rate"] * 100
            if target["cash_tax_rate"] is not None else None
        )
        row["Capex / revenue (%)"] = (
            target["capex_margin"] * 100 + capex_offset
            if target["capex_margin"] is not None else None
        )
        rows.append(row)
    scenario_defaults = pd.DataFrame(rows)
    scenario_assumptions = st.data_editor(
        scenario_defaults,
        key="dcf_scenario_assumptions",
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Scenario": st.column_config.TextColumn("Scenario", disabled=True),
            **{
                column: st.column_config.NumberColumn(
                    column, format="%.1f%%", step=1.0,
                    help="User-entered annual FCF growth for the normalized DCF.",
                )
                for column in growth_columns
            },
            **{
                column: st.column_config.NumberColumn(
                    column, format="%.1f%%", step=1.0, help="User-entered annual revenue growth."
                )
                for column in revenue_growth_columns
            },
            "WACC (%)": st.column_config.NumberColumn("WACC (%)", format="%.1f%%", step=0.5),
            "Terminal growth (%)": st.column_config.NumberColumn(
                "Terminal growth (%)", format="%.1f%%", step=0.5
            ),
            "Operating margin (%)": st.column_config.NumberColumn(
                "Operating margin (%)", format="%.1f%%", step=1.0
            ),
            "Tax rate (%)": st.column_config.NumberColumn(
                "Tax rate (%)", format="%.1f%%", step=1.0
            ),
            "Capex / revenue (%)": st.column_config.NumberColumn(
                "Capex / revenue (%)", format="%.1f%%", step=1.0
            ),
        },
        alt="Editable DCF assumptions for five valuation scenarios",
    )
    historical_summary = target["historical_fcf_summary"]
    normalized_fcf_override = st.number_input(
        "Normalized starting FCF (reporting currency)",
        value=historical_summary["normalized_fcf"],
        min_value=None,
        max_value=None,
        step=1_000_000.0,
        format="%.2f",
        key=f"normalized_fcf_{ticker}",
        help=(
            "The default is calculated from historical median revenue, operating-cash-flow margin, "
            "and capex/revenue using at least three complete periods. Enter another value only as an "
            "explicit user assumption; blank means unavailable."
        ),
    )

base_growth = growth_pct / 100
wacc = wacc_pct / 100
terminal_growth = terminal_pct / 100
scenario_results: dict[str, dict[str, Any] | None] = {}
normalized_scenario_results: dict[str, dict[str, Any] | None] = {}
scenario_inputs: dict[str, dict[str, Any]] = {}
scenario_forecasts: dict[str, list[dict[str, Any]]] = {}
normalized_scenario_forecasts: dict[str, list[dict[str, Any]]] = {}
financial_forecast = None
latest_ocf_margin = (
    target["operating_cash_flow"] / target["reported_revenue"]
    if target["operating_cash_flow"] is not None
    and target["reported_revenue"] else None
)
historical_summary = target["historical_fcf_summary"]
for _, scenario_row in scenario_assumptions.iterrows():
    name = scenario_row["Scenario"]
    rates = [
        float(scenario_row[column]) / 100
        if pd.notna(scenario_row[column]) else base_growth
        for column in growth_columns
    ]
    revenue_rates = [
        float(scenario_row[column]) / 100
        if pd.notna(scenario_row[column]) else rates[index]
        for index, column in enumerate(revenue_growth_columns)
    ]
    scenario_inputs[name] = {
        "growth_rates": rates,
        "revenue_growth_rates": revenue_rates,
        "wacc": float(scenario_row["WACC (%)"]) / 100,
        "terminal_growth": float(scenario_row["Terminal growth (%)"]) / 100,
        "operating_margin": (
            float(scenario_row["Operating margin (%)"]) / 100
            if pd.notna(scenario_row["Operating margin (%)"]) else None
        ),
        "tax_rate": (
            float(scenario_row["Tax rate (%)"]) / 100
            if pd.notna(scenario_row["Tax rate (%)"]) else None
        ),
        "capex_margin": (
            float(scenario_row["Capex / revenue (%)"]) / 100
            if pd.notna(scenario_row["Capex / revenue (%)"]) else None
        ),
    }
    inputs = scenario_inputs[name]
    model_inputs = {
        "annual_revenue_growth_rates": inputs["revenue_growth_rates"],
        "operating_margin": inputs["operating_margin"],
        "tax_rate": inputs["tax_rate"],
        "operating_cash_flow_margin": latest_ocf_margin,
        "capital_expenditure_margin": inputs["capex_margin"],
    }
    forecast_result = build_financial_forecast(
        target["annual"],
        target["quarterly"],
        target_guidance,
        years=projection_years,
        quarters=4,
        model_assumptions=model_inputs,
    )
    scenario_forecasts[name] = forecast_result["annual"]
    if name == "Base":
        financial_forecast = forecast_result
    scenario_results[name] = calculate_forecast_dcf(
        forecast_result["annual"],
        target["diluted_shares"],
        target["cash"],
        target["debt"],
        target["minority_interest"],
        inputs["wacc"],
        inputs["terminal_growth"],
    )

    normalized_inputs = {
        **model_inputs,
        "operating_cash_flow_margin": historical_summary[
            "median_operating_cash_flow_margin"
        ],
        "capital_expenditure_margin": historical_summary["median_capex_margin"],
    }
    normalized_result = build_financial_forecast(
        target["annual"],
        target["quarterly"],
        target_guidance,
        years=projection_years,
        quarters=4,
        model_assumptions=normalized_inputs,
    )
    normalized_forecast = normalized_result["annual"]
    if (
        normalized_fcf_override is not None
        and target["reported_revenue"]
        and target["reported_revenue"] > 0
    ):
        cumulative_fcf_growth = 1.0
        for year_index, row in enumerate(normalized_forecast):
            cumulative_fcf_growth *= 1 + inputs["growth_rates"][year_index]
            capex = row.get("Capital expenditure")
            projected_normalized_fcf = normalized_fcf_override * cumulative_fcf_growth
            line_sources = row.get("Line item sources", {})
            guidance_precedence = any(
                line_sources.get(field, {}).get("classification") == "Company guidance"
                for field in ("Operating cash flow", "Capital expenditure", "Free cash flow")
            )
            if capex is not None and not guidance_precedence:
                row["Operating cash flow"] = projected_normalized_fcf + abs(capex)
                row["Free cash flow"] = projected_normalized_fcf
                row["Line item sources"]["Operating cash flow"] = {
                    "classification": "Model estimate",
                    "source": None,
                    "model_method": (
                        "Editable normalized starting FCF grown by the scenario FCF rate, "
                        "plus projected capital expenditure"
                    ),
                }
                row["Line item sources"]["Free cash flow"] = {
                    "classification": "Model estimate",
                    "source": None,
                    "model_method": (
                        "Editable normalized starting FCF grown by the scenario FCF rate"
                    ),
                }
    normalized_scenario_forecasts[name] = normalized_forecast
    normalized_scenario_results[name] = calculate_forecast_dcf(
        normalized_forecast,
        target["diluted_shares"],
        target["cash"],
        target["debt"],
        target["minority_interest"],
        inputs["wacc"],
        inputs["terminal_growth"],
    )

standard_base_result = scenario_results.get("Base")
normalized_base_result = normalized_scenario_results.get("Base")
target_fair_value = (
    standard_base_result["fair_value_per_share"] if standard_base_result else None
)
normalized_fair_value = (
    normalized_base_result["fair_value_per_share"] if normalized_base_result else None
)
fair_values: dict[str, float | None] = {ticker: target_fair_value}

market_enterprise_value = None
if (
    target["price"] is not None
    and target["diluted_shares"] is not None
    and target["debt"] is not None
    and target["cash"] is not None
):
    market_equity_value = target["price"] * target["diluted_shares"]
    market_enterprise_value = (
        market_equity_value + target["debt"] - target["cash"]
        + (target["minority_interest"] or 0)
    )
implied_growth = reverse_dcf_growth(
    market_enterprise_value,
    target["free_cash_flow"],
    target["diluted_shares"],
    target["cash"],
    target["debt"],
    target["minority_interest"],
    wacc,
    terminal_growth,
    projection_years,
)

peer_multiples = [
    companies[symbol]["ev_ebitda"]
    for symbol in industry_peers
    if symbol in companies
    and companies[symbol]["ev_ebitda"] is not None
    and companies[symbol]["ev_ebitda"] > 0
]
peer_median_multiple = float(pd.Series(peer_multiples).median()) if peer_multiples else None
latest_annual = target["annual"][-1] if target["annual"] else {}
target_ebitda = latest_annual.get("EBITDA")
comparable_fair_value = None
if (
    peer_median_multiple is not None
    and target_ebitda is not None and target_ebitda > 0
    and target["diluted_shares"] is not None
    and target["cash"] is not None and target["debt"] is not None
):
    comparable_equity = (
        target_ebitda * peer_median_multiple
        + target["cash"] - target["debt"]
        - (target["minority_interest"] or 0)
    )
    comparable_fair_value = comparable_equity / target["diluted_shares"]

base_sensitivity_values = []
if standard_base_result and scenario_forecasts.get("Base"):
    base_wacc = scenario_inputs["Base"]["wacc"]
    base_terminal_growth = scenario_inputs["Base"]["terminal_growth"]
    for sensitivity_wacc in (
        base_wacc - 0.02, base_wacc - 0.01, base_wacc,
        base_wacc + 0.01, base_wacc + 0.02,
    ):
        for sensitivity_terminal in (
            max(0, base_terminal_growth - 0.01),
            base_terminal_growth,
            base_terminal_growth + 0.01,
        ):
            result = calculate_forecast_dcf(
                scenario_forecasts["Base"],
                target["diluted_shares"],
                target["cash"],
                target["debt"],
                target["minority_interest"],
                sensitivity_wacc,
                sensitivity_terminal,
            )
            if result:
                base_sensitivity_values.append(result["fair_value_per_share"])

completeness_inputs = [
    target["free_cash_flow"],
    target["diluted_shares"],
    target["cash"],
    target["debt"],
    target["reported_revenue"],
    target["reported_operating_margin"],
    target["capex_margin"],
    target["cash_tax_rate"],
]
reported_completeness = (
    sum(value is not None for value in completeness_inputs)
    / len(completeness_inputs) * 100
)
forecast_rows = scenario_forecasts.get("Base", [])
forecast_fields = (
    "Revenue", "Gross profit", "Operating income", "Net income",
    "Operating cash flow", "Capital expenditure", "Free cash flow",
    "Diluted shares",
)
forecast_coverage = (
    sum(
        row.get(field) is not None
        for row in forecast_rows for field in forecast_fields
    ) / (len(forecast_rows) * len(forecast_fields)) * 100
    if forecast_rows else 0
)
completeness = (reported_completeness + forecast_coverage) / 2
confidence_result = dcf_confidence(
    target["historical_fcf_summary"],
    base_sensitivity_values,
    target_fair_value,
    normalized_fair_value,
    cyclical_industry,
    completeness,
    standard_base_result["terminal_value_share"] if standard_base_result else None,
    financial_forecast["guidance_accuracy"] if financial_forecast else None,
)
confidence_score = confidence_result["score"]
normalized_upside = (
    normalized_fair_value / target["price"] - 1
    if normalized_fair_value is not None and target["price"] else None
)
comparable_upside = (
    comparable_fair_value / target["price"] - 1
    if comparable_fair_value is not None and target["price"] else None
)
relative_multiple_score = (
    _clamp(50 + max(-1, min(1, peer_median_multiple / target["ev_ebitda"] - 1)) * 40)
    if peer_median_multiple is not None and target["ev_ebitda"]
    and target["ev_ebitda"] > 0 else None
)
growth_gap = implied_growth - base_growth if implied_growth is not None else None
valuation_score = _valuation_score(
    [target_fair_value, normalized_fair_value, comparable_fair_value],
    target["price"],
    confidence_score,
    relative_multiple_score,
    growth_gap,
)
scores = {
    symbol: _score_company(
        company,
        valuation_score if symbol == ticker else None,
    )
    for symbol, company in companies.items()
}
target_score = scores[ticker]["Overall score"]
target_upside = (
    target_fair_value / target["price"] - 1
    if target_fair_value is not None and target["price"]
    else None
)
rating = recommendation(target_score)

if navigation not in {"Watchlist", "Portfolio", "Settings"}:
    render_company_heading(target, ticker)
    metric_rows = [
        (
            "Last adjusted close",
            _fmt(target["price"], target["currency"], "money"),
            _fmt(target["performance"].get("1 day return"), kind="percent")
            if target["performance"].get("1 day return") is not None else None,
        ),
        ("Market cap", _fmt(target["market_cap"], target["currency"], "large_money"), None),
        (
            "52-week range",
            f"{_fmt(target['52w_low'], target['currency'])} – {_fmt(target['52w_high'], target['currency'])}",
            None,
        ),
        ("Base DCF value", _fmt(target_fair_value, target["currency"], "money"), None),
        (
            "DCF implied upside",
            _fmt(target_upside, kind="percent"),
            _fmt(target_upside, kind="percent") if target_upside is not None else None,
        ),
        ("Rule-based rating", rating, None),
    ]
    for start in (0, 3):
        metric_columns = st.columns(3)
        for column, (label, value, delta) in zip(
            metric_columns, metric_rows[start:start + 3]
        ):
            column.metric(label, value, delta=delta, border=True, height="stretch")

    st.caption(
        f"Price timestamp: {target['price_date']:%Y-%m-%d} · "
        f"Data retrieved: {target['retrieved_at']:%Y-%m-%d %H:%M UTC} · "
        f"Score coverage: {_fmt(scores[ticker]['Coverage'], kind='score')}"
    )
    st.caption(
        "Research only, not investment advice. The rating is a transparent quantitative screen, "
        "not an AI opinion. DCF outputs are assumption-sensitive estimates, not objective fair values."
    )

if navigation == "Overview":
    st.header("Investment summary")
    score_names = [
        "Business quality", "Financial health", "Moat proxy", "Growth",
        "Valuation", "Technical strength", "Risk",
    ]
    score_values = [
        scores[ticker].get(name)
        for name in score_names
    ]
    score_frame = pd.DataFrame(
        {"Dimension": score_names, "Score": [round(value, 1) if value is not None else None for value in score_values]}
    )
    left, right = st.columns([1.3, 1])
    with left:
        st.subheader("What the available data says")
        highlights = []
        if target["revenue_growth"] is not None:
            direction = "grew" if target["revenue_growth"] >= 0 else "declined"
            highlights.append(
                f"Latest annual revenue {direction} **{abs(target['revenue_growth']):.1%}**."
            )
        if target["reported_operating_margin"] is not None:
            highlights.append(
                f"Latest annual-statement operating margin is **{target['reported_operating_margin']:.1%}**."
            )
        if target_upside is not None:
            highlights.append(
                f"The editable base DCF implies **{target_upside:+.1%}** upside/downside."
            )
        if not highlights:
            highlights.append("Not enough financial data was returned to form quantitative highlights.")
        for highlight in highlights:
            st.markdown(f"- {highlight}")
        if target["summary"]:
            st.markdown("**Company overview**")
            st.write(target["summary"])
        else:
            st.caption("A provider-sourced company description is unavailable.")
        st.caption(
            "Score methodology: quality and moat are profitability/return proxies; financial health "
            "uses liquidity, leverage, and cash generation; growth uses observed revenue/EPS growth; "
            "valuation uses DCF upside; technical strength uses moving-average/MACD/RSI signals. "
            "Unavailable dimensions are excluded and remaining weights are renormalized."
        )
    with right:
        st.subheader("Quantitative scorecard")
        st.dataframe(
            score_frame,
            hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score (0–100)", min_value=0, max_value=100, format="%.0f"
                )
            },
            alt="Rule-based company quality, growth, valuation, and risk scores",
        )
        st.metric(
            "Overall score",
            _fmt(target_score, kind="score"),
            delta=rating,
        )
        st.caption(
            "Weights: quality 15%, financial health 15%, moat proxy 15%, growth 20%, "
            "valuation 20%, technical 5%, risk 10% (risk reduces the score)."
        )
    st.subheader("Price performance vs benchmarks")
    price_overlay = _chart_history(companies, 365 * 5)
    if price_overlay.empty:
        st.warning("Insufficient overlapping price history for a comparison chart.")
    else:
        st.line_chart(price_overlay, y_label="Indexed price (start = 100)", alt="Five-year price performance indexed to 100 for the analyzed stock and available benchmarks")
        st.caption("Adjusted closing prices are indexed to 100 at each series' first available date; currencies are therefore comparable as percentage changes.")

    st.subheader("Price and moving averages")
    target_history = target["history"]
    if target_history.empty or "Close" not in target_history.columns:
        st.info("Price history is unavailable, so moving averages cannot be displayed.")
    else:
        overview_technical = technical_indicators(target_history)
        latest_technical = overview_technical.iloc[-1]
        price_metrics = st.columns(3)
        price_metrics[0].metric(
            "Adjusted close",
            _fmt(latest_technical.get("Close"), target["currency"], "money"),
        )
        price_metrics[1].metric(
            "50-day moving average",
            _fmt(latest_technical.get("SMA 50"), target["currency"], "money"),
        )
        price_metrics[2].metric(
            "200-day moving average",
            _fmt(latest_technical.get("SMA 200"), target["currency"], "money"),
        )
        moving_average_chart = overview_technical.tail(365)[
            ["Close", "SMA 50", "SMA 200"]
        ].rename(columns={
            "Close": "Market price",
            "SMA 50": "50-day moving average",
            "SMA 200": "200-day moving average",
        })
        st.line_chart(
            moving_average_chart,
            y_label=f"Adjusted price ({target['currency']})",
            alt="Adjusted market price with 50-day and 200-day simple moving averages",
        )
        st.caption(
            "Moving averages are calculated from adjusted daily closing prices. "
            "They describe historical price trends and are not forecasts."
        )

elif navigation == "Comparison":
    st.header("Benchmark and peer comparison")
    st.write(
        "The permanent benchmark set is Microsoft, Alphabet, Meta, and Apple. "
        "These are cross-sector reference companies, not necessarily direct competitors. "
        "Industry-selected and user-entered peers are also included when data is available."
    )
    groups = (
        "All metrics", "Financials", "Valuation", "Growth",
        "Price performance", "Investment quality",
    )
    group = st.segmented_control(
        "Metric group",
        options=groups,
        default="All metrics",
        key="comparison_group",
    )
    present, raw = _build_comparison(companies, scores, fair_values, group)
    st.dataframe(
        present,
        height=680,
        column_config={
            "Definition": st.column_config.TextColumn(
                "Definition", help="Calculation or interpretation of the displayed metric."
            )
        },
        alt="Side-by-side financial and investment metric comparison",
    )
    st.download_button(
        "Download comparison as CSV",
        data=raw.to_csv(index=True).encode("utf-8"),
        file_name=f"{ticker.lower()}-benchmark-comparison.csv",
        mime="text/csv",
        icon=":material/download:",
    )
    st.caption(
        "Each metric uses a seven-shade red–yellow–green scale relative to the companies shown. "
        "The scale reverses for lower-is-better metrics; unranked, unavailable, and categorical values "
        "remain uncolored. Values retain each company's reported currency and fiscal-period differences."
    )
    _render_heatmap_legend()

    st.subheader("Overlaid financial trends")
    trend_choice = st.selectbox(
        "Metric to overlay",
        options=(
            "Revenue", "Operating margin", "Net income",
            "EPS", "Free cash flow", "Revenue growth",
        ),
        key="overlay_metric",
    )
    overlay = _financial_overlay(companies, trend_choice)
    if overlay.empty:
        st.warning(f"No annual {trend_choice.lower()} history is available for these companies.")
    else:
        indexed = trend_choice in ("Revenue", "Net income", "EPS", "Free cash flow")
        st.line_chart(
            overlay,
            y_label="Indexed (first positive year = 100)" if indexed else (
                "Percent" if "margin" in trend_choice.casefold() or trend_choice == "Revenue growth" else trend_choice
            ),
            alt=f"Overlaid annual {trend_choice.lower()} trends for the analyzed company and available benchmarks",
        )
        if indexed:
            st.caption(
                "Currency-denominated metrics are indexed to each company's first positive reported year (100) "
                "so the trend is comparable without converting reporting currencies."
            )
        st.caption(
            "Financial periods are company fiscal years and may not align exactly. Missing or non-positive "
            "starting values are omitted rather than replaced."
        )

elif navigation == "7 Indicators":
    st.header("7 indicators of a potentially excellent investment")
    st.write(
        "Compare the analyzed company with available benchmarks and industry/user-entered peers across "
        "the seven investment lenses you provided. The heatmap is relative to this comparison set; "
        "it is not a guarantee of investment quality."
    )
    indicator_table, indicator_raw, indicator_higher, indicator_lower, indicator_centered = (
        _build_seven_indicator_comparison(companies, fair_values, ticker)
    )
    indicator_names = list(dict.fromkeys(indicator_table.data["Indicator"].tolist()))
    selected_indicator = st.selectbox(
        "Indicator",
        options=("All seven", *indicator_names),
        key="seven_indicator_filter",
    )
    if selected_indicator != "All seven":
        rows = indicator_table.data["Indicator"] == selected_indicator
        filtered_display = indicator_table.data.loc[rows]
        filtered_raw = indicator_raw.loc[filtered_display.index]
        filtered_table = _heatmap_table(
            filtered_display,
            filtered_raw,
            indicator_higher,
            indicator_lower,
            list(companies),
            indicator_centered,
        )
    else:
        filtered_table = indicator_table

    st.dataframe(
        filtered_table,
        height=720 if selected_indicator == "All seven" else 440,
        column_config={
            "Indicator": st.column_config.TextColumn("Indicator"),
            "Definition": st.column_config.TextColumn(
                "How to read this metric",
                help="Metric definition, calculation, and limitations.",
            ),
        },
        alt="Seven investment indicators compared across the analyzed company and permanent benchmarks",
    )
    _render_heatmap_legend()
    st.caption(
        "Growth of 15–25% or more is the heuristic in your supplied criteria, not a universal rule. "
        "Operating-margin change is shown in percentage points. FCF conversion is defined here as "
        "free cash flow divided by positive net income. Amounts keep local currencies and are not "
        "ranked across companies. Unsupported qualitative inputs are marked unavailable rather than inferred."
    )

elif navigation == "Financials":
    st.header("Historical financial performance")
    annual = target["annual"]
    if not annual:
        st.warning("Annual financial statements are unavailable for this ticker.")
    else:
        chart_metric = st.selectbox(
            "Financial trend",
            ("Revenue", "Operating margin", "Net income", "EPS", "Free cash flow", "Revenue growth"),
            key="financial_metric",
        )
        chart = _financial_overlay(companies, chart_metric)
        if chart.empty:
            st.warning(
                f"No reported {chart_metric.lower()} history is available for this company or its benchmarks."
            )
        else:
            indexed = chart_metric in ("Revenue", "Net income", "EPS", "Free cash flow")
            st.line_chart(
                chart,
                y_label="Indexed (first positive year = 100)" if indexed else (
                    "Percent" if "margin" in chart_metric.casefold() or chart_metric == "Revenue growth" else chart_metric
                ),
                alt=f"Annual {chart_metric.lower()} trend for {target['name']} and available benchmarks",
            )
        st.subheader("Reported annual financials")
        financial_table = _format_annual(annual, target["currency"])
        st.dataframe(
            financial_table,
            hide_index=True,
            alt=f"Annual financial statements for {target['name']}",
        )
        st.caption(
            f"Source: Yahoo Finance via yfinance · reporting currency {target['currency']} · "
            "financial statement values are annual and are not estimates."
        )
    _render_research_comparison(
        "Financial performance vs benchmarks",
        "Financials",
        companies,
        scores,
        fair_values,
        "Benchmarks and available peers are shown using reported fiscal periods. "
        "Financial amounts remain in each company's reporting currency; growth and margins are more directly comparable.",
    )

elif navigation == "Valuation":
    st.header("Valuation and return scenarios")
    if st.button("Refresh official guidance", key=f"refresh_guidance_{ticker}"):
        get_company_guidance.clear()
        st.rerun()
    st.caption(
        "Reported figures come from Yahoo Finance via yfinance; official numeric guidance is extracted "
        "conservatively from SEC filings where accessible. Analyst consensus is unavailable until a "
        "licensed provider is configured. All independent projections are labeled model estimates. "
        "AI-generated interpretations: none; "
        "narrative flags are rule-based app outputs."
    )
    st.write(
        f"Industry classification: **{industry_classification}** "
        f"({'cyclical' if cyclical_industry else 'not classified as cyclical'}). "
        f"Base forecast horizon: {projection_years} years."
    )
    if target.get("share_count_source") == "Basic shares outstanding proxy":
        st.warning(
            "Diluted shares were unavailable; fair value uses basic shares outstanding as an explicitly labeled proxy."
        )
    if target["minority_interest"] is None:
        st.info("Minority-interest data is unavailable and was not subtracted from equity value.")

    st.subheader("Key valuation inputs and sources")
    key_input_rows = [
        {
            "Input": "Current price",
            "Value": _fmt(target["price"], target["currency"], "money"),
            "Classification / source": "Observed adjusted daily close from Yahoo Finance",
        },
        {
            "Input": "Starting free cash flow",
            "Value": _fmt(target["free_cash_flow"], target["currency"], "large_money"),
            "Classification / source": target["fcf_source"] or "Unavailable; no substitute used",
        },
        {
            "Input": "Revenue",
            "Value": _fmt(target["reported_revenue"], target["currency"], "large_money"),
            "Classification / source": target["revenue_source"] or "Unavailable",
        },
        {
            "Input": "Diluted shares",
            "Value": (
                f"{target['diluted_shares'] / 1e6:,.2f}M"
                if target["diluted_shares"] is not None else "N/A"
            ),
            "Classification / source": target["share_count_source"] or "Unavailable",
        },
        {
            "Input": "Cash",
            "Value": _fmt(target["cash"], target["currency"], "large_money"),
            "Classification / source": target["cash_source"] or "Unavailable",
        },
        {
            "Input": "Total debt",
            "Value": _fmt(target["debt"], target["currency"], "large_money"),
            "Classification / source": target["debt_source"] or "Unavailable",
        },
        {
            "Input": "Minority interest",
            "Value": _fmt(target["minority_interest"], target["currency"], "large_money"),
            "Classification / source": target["minority_interest_source"] or "Unavailable; not subtracted",
        },
        {
            "Input": "Operating margin / capex intensity",
            "Value": (
                f"{_fmt(target['reported_operating_margin'], kind='percent')} / "
                f"{_fmt(target['capex_margin'], kind='percent')}"
            ),
            "Classification / source": "Latest annual statement; both are editable scenario assumptions",
        },
    ]
    st.dataframe(
        pd.DataFrame(key_input_rows),
        hide_index=True,
        alt="Reported financial inputs, observed price, user assumptions, and data source labels",
    )

    st.subheader("Company Guidance and Market Estimates")
    st.caption(
        "Figures remain in their reported currency, units, accounting basis, and period. "
        "Numeric SEC-extracted values retain source sentences and document links; qualitative statements "
        "are not converted into numeric estimates."
    )
    guidance_status = target_guidance.get("status", "unavailable")
    if guidance_status == "available":
        st.success(
            f"SEC EDGAR filing status: {guidance_status}. Latest earnings filing: "
            f"{target_guidance.get('latest_earnings_filing_date') or 'date unavailable'}."
        )
    else:
        st.warning(
            f"SEC EDGAR guidance status: {guidance_status}. "
            f"{target_guidance.get('reason') or 'No verified company guidance is available.'}"
        )
    st.caption(
        f"Retrieved: {target_guidance.get('retrieved_at') or 'N/A'} · "
        f"Latest report period: {target_guidance.get('latest_earnings_report_date') or 'N/A'}"
    )
    guidance_rows = [
        {
            "Metric": item["metric"].replace("_", " ").title(),
            "Period": item.get("period") or "Not specified",
            "Guidance": item.get("display_value") or "Qualitative only",
            "Unit": item.get("unit") or "N/A",
            "Basis": item.get("accounting_basis"),
            "Classification": item.get("classification"),
            "Active for forecast": (
                guidance_status == "available"
                and item.get("publication_date")
                == target_guidance.get("latest_earnings_filing_date")
            ),
            "Publication date": item.get("publication_date"),
            "Reporting period": item.get("reporting_period"),
            "Retrieved at": item.get("retrieved_at"),
            "Evidence": item.get("sentence"),
            "Source URL": item.get("source_url"),
            "Document": item.get("document_reference"),
        }
        for item in target_guidance.get("guidance", [])
    ]
    if guidance_rows:
        st.dataframe(
            pd.DataFrame(guidance_rows),
            hide_index=True,
            column_config={
                "Source URL": st.column_config.LinkColumn("Source URL"),
            },
            height=330,
            alt="Official SEC filing guidance, source evidence, dates, and document links",
        )
    else:
        st.info("No current numeric company guidance was verified. No figures have been fabricated.")
    if target_guidance.get("documents"):
        with st.expander("SEC filing documents discovered"):
            document_rows = [
                {
                    "Form": doc.get("form"),
                    "Filing date": doc.get("filing_date"),
                    "Reporting period": doc.get("report_date"),
                    "Document": doc.get("document_reference"),
                    "Description": doc.get("description"),
                    "Source URL": doc.get("source_url"),
                }
                for doc in target_guidance["documents"]
            ]
            st.dataframe(
                pd.DataFrame(document_rows),
                hide_index=True,
                column_config={"Source URL": st.column_config.LinkColumn("Source URL")},
                alt="SEC filings and exhibits retrieved for guidance extraction",
            )
    st.info(
        "Analyst consensus: "
        f"{financial_forecast['analyst_estimates_status'] if financial_forecast else 'Unavailable'}. "
        "A licensed estimates provider is not configured; company guidance and analyst estimates are kept distinct."
    )

    st.markdown("**Reported actuals**")
    actual_rows = [
        {
            "Period": row.get("Fiscal year", row.get("Period")),
            "Revenue": row.get("Revenue"),
            "Gross profit": row.get("Gross profit"),
            "Operating income": row.get("Operating income"),
            "Net income": row.get("Net income"),
            "Operating cash flow": row.get("Operating cash flow"),
            "Capital expenditure": abs(row["Capital expenditure"])
            if row.get("Capital expenditure") is not None else None,
            "Free cash flow": row.get("Free cash flow"),
            "Diluted shares": row.get("Diluted shares"),
            "Classification": "Reported actual",
            "Source": "Yahoo Finance company statements via yfinance",
            "Retrieved": target.get("retrieved_at"),
        }
        for row in target["annual"]
    ]
    if actual_rows:
        st.dataframe(
            pd.DataFrame(actual_rows),
            hide_index=True,
            alt="Reported annual historical financial results and data retrieval timestamp",
        )
    else:
        st.warning("Annual reported actuals are unavailable for this ticker.")
    quarterly_actual_rows = [
        {
            "Period": row.get("Period"),
            "Revenue": row.get("Revenue"),
            "Gross profit": row.get("Gross profit"),
            "Operating income": row.get("Operating income"),
            "Net income": row.get("Net income"),
            "Operating cash flow": row.get("Operating cash flow"),
            "Capital expenditure": abs(row["Capital expenditure"])
            if row.get("Capital expenditure") is not None else None,
            "Free cash flow": row.get("Free cash flow"),
            "Diluted shares": row.get("Diluted shares"),
            "Classification": "Reported actual",
            "Source": "Yahoo Finance quarterly statements via yfinance",
            "Retrieved": target.get("retrieved_at"),
        }
        for row in target["quarterly"]
    ]
    if quarterly_actual_rows:
        with st.expander("Reported quarterly actuals"):
            st.dataframe(
                pd.DataFrame(quarterly_actual_rows),
                hide_index=True,
                alt="Reported quarterly financial results and data retrieval timestamp",
            )

    if financial_forecast:
        forecast_source_rows = []
        forecast_rows_by_period = [
            ("Quarterly forecast", row) for row in financial_forecast["quarterly"]
        ] + [
            ("Annual forecast", row) for row in financial_forecast["annual"]
        ]
        forecast_fields = (
            "Revenue", "Revenue growth", "Gross margin", "Gross profit",
            "Operating margin", "Operating expenses", "Operating income",
            "Net income", "EPS", "Operating cash flow", "Capital expenditure",
            "Free cash flow", "Diluted shares", "Tax rate",
        )
        for horizon, row in forecast_rows_by_period:
            line_sources = row.get("Line item sources", {})
            for field in forecast_fields:
                source_info = line_sources.get(field, {})
                source = source_info.get("source")
                if isinstance(source, dict):
                    source_url = source.get("source_url")
                    publication_date = source.get("publication_date")
                    source_retrieved_at = source.get("retrieved_at")
                    document_reference = source.get("document_reference")
                    evidence = source.get("sentence")
                    underlying_source = "SEC EDGAR filing"
                    underlying_periods = source.get("reporting_period")
                else:
                    source_url = publication_date = source_retrieved_at = None
                    document_reference = evidence = None
                    underlying_source = (
                        "Yahoo Finance reported statements and editable model assumptions"
                        if source_info.get("classification") == "Model estimate"
                        else "No verified underlying source"
                    )
                    source_retrieved_at = (
                        target["retrieved_at"].strftime("%Y-%m-%d %H:%M UTC")
                        if target.get("retrieved_at") is not None
                        else None
                    )
                    historical_rows = (
                        target["quarterly"][-8:]
                        if horizon == "Quarterly forecast"
                        else target["annual"][-5:]
                    )
                    underlying_periods = ", ".join(
                        str(item.get("Period") or item.get("Fiscal year"))
                        for item in historical_rows
                    )
                forecast_source_rows.append({
                    "Horizon": horizon,
                    "Period": row.get("Period"),
                    "Metric": field,
                    "Value": row.get(field),
                    "Classification": source_info.get("classification", "Unavailable"),
                    "Publication date": publication_date,
                    "Retrieved at": source_retrieved_at,
                    "Underlying source": underlying_source,
                    "Underlying historical periods": underlying_periods,
                    "Source URL": source_url,
                    "Document": document_reference,
                    "Evidence": evidence,
                    "Model method": source_info.get("model_method"),
                })
        st.markdown("**Company-specific forecast: next four quarters and annual periods**")
        forecast_display = pd.DataFrame(
            [
                {
                    "Horizon": horizon,
                    "Period": row.get("Period"),
                    "Revenue": row.get("Revenue"),
                    "Revenue growth": row.get("Revenue growth"),
                    "Gross margin": row.get("Gross margin"),
                    "Gross profit": row.get("Gross profit"),
                    "Operating margin": row.get("Operating margin"),
                    "Operating expenses": row.get("Operating expenses"),
                    "Operating income": row.get("Operating income"),
                    "Net income": row.get("Net income"),
                    "EPS": row.get("EPS"),
                    "Operating cash flow": row.get("Operating cash flow"),
                    "Capital expenditure": row.get("Capital expenditure"),
                    "Free cash flow": row.get("Free cash flow"),
                    "Diluted shares": row.get("Diluted shares"),
                    "Tax rate": row.get("Tax rate"),
                    "Revenue source class": (
                        row.get("Revenue classification")
                        or row.get("Classification")
                    ),
                }
                for horizon, row in forecast_rows_by_period
            ]
        )
        st.dataframe(
            forecast_display,
            hide_index=True,
            alt="Four quarterly and five-or-more annual financial forecasts with revenue source classifications",
        )
        with st.expander("Inspect source and classification for every forecast line item"):
            st.dataframe(
                pd.DataFrame(forecast_source_rows),
                hide_index=True,
                column_config={
                    "Source URL": st.column_config.LinkColumn("Source URL"),
                },
                height=420,
                alt="Line-by-line forecast source classifications, document dates, and model methods",
            )
        accuracy = financial_forecast["guidance_accuracy"]
        st.markdown("**Previous guidance versus actual performance**")
        if accuracy["comparisons"]:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Period": item["period"],
                        "Guidance midpoint": item["midpoint"],
                        "Actual revenue": item["actual"],
                        "Beat/miss vs midpoint": item["midpoint_variance"],
                        "Range outcome": item["result"],
                        "Guidance publication date": item["source"].get("publication_date"),
                        "Retrieved at": item["source"].get("retrieved_at"),
                        "Source URL": item["source"].get("source_url"),
                    }
                    for item in accuracy["comparisons"]
                ]),
                hide_index=True,
                column_config={"Source URL": st.column_config.LinkColumn("Source URL")},
                alt="Historical company revenue guidance midpoint compared with reported actual results",
            )
            st.caption(
                f"Matched periods: {accuracy['count']} · Mean midpoint variance: "
                f"{_fmt(accuracy['mean_midpoint_variance'], kind='percent')} · "
                f"Within range: {accuracy['within_range_count']} · "
                f"Beats: {accuracy['beat_count']} · Misses: {accuracy['miss_count']}. "
                "Only explicitly period-matched reported revenue guidance is included."
            )
        else:
            st.caption(
                "Historical guidance accuracy is unavailable: no prior numeric revenue guidance "
                "could be matched confidently to a subsequently reported quarter."
            )

    price = target["price"]
    scenario_rows = []
    scenario_fair_values = {}
    for scenario, result in scenario_results.items():
        value = result["fair_value_per_share"] if result else None
        scenario_fair_values[scenario] = value
        assumptions = scenario_inputs[scenario]
        upside = value / price - 1 if value is not None and price else None
        annualized = (
            (value / price) ** (1 / projection_years) - 1
            if value is not None and price and value > 0 else None
        )
        scenario_rows.append({
            "Scenario": scenario,
            "Fair value / share": _fmt(value, target["currency"], "money"),
            "Upside / downside": _fmt(upside, kind="percent"),
            "Annualized return": _fmt(annualized, kind="percent"),
            "Normalized DCF FCF growth by year": ", ".join(
                f"{rate:.1%}" for rate in assumptions["growth_rates"]
            ),
            "Revenue growth by year": ", ".join(
                f"{rate:.1%}" for rate in assumptions["revenue_growth_rates"]
            ),
            "WACC": _fmt(assumptions["wacc"], kind="percent"),
            "Terminal growth": _fmt(assumptions["terminal_growth"], kind="percent"),
            "Operating margin assumption": _fmt(assumptions["operating_margin"], kind="percent"),
            "Tax rate assumption": _fmt(assumptions["tax_rate"], kind="percent"),
            "Capex / revenue assumption": _fmt(assumptions["capex_margin"], kind="percent"),
        })
    st.dataframe(
        pd.DataFrame(scenario_rows),
        hide_index=True,
        alt="Bear, conservative, base, bull, and extreme bull DCF scenarios with editable assumptions",
    )

    if price is not None and any(value is not None and value > 0 for value in scenario_fair_values.values()):
        years = list(range(projection_years + 1))
        projection = pd.DataFrame({"Year": years})
        for scenario, value in scenario_fair_values.items():
            if value is not None and value > 0:
                implied_return = (value / price) ** (1 / projection_years) - 1
                projection[scenario] = [price * (1 + implied_return) ** year for year in years]
        if len(projection.columns) > 1:
            st.line_chart(
                projection.set_index("Year"),
                y_label=f"Implied price ({target['currency']})",
                alt="Illustrative annualized share price paths implied by DCF scenario outputs",
            )

    st.subheader("Valuation methods")
    method_columns = st.columns(4)
    with method_columns[0]:
        st.metric(
            "Standard DCF",
            _fmt(target_fair_value, target["currency"], "money"),
            delta=_fmt(target_upside, kind="percent"),
            border=True,
        )
    with method_columns[1]:
        st.metric(
            "Normalized / mid-cycle DCF",
            _fmt(normalized_fair_value, target["currency"], "money"),
            delta=_fmt(normalized_upside, kind="percent"),
            border=True,
        )
    with method_columns[2]:
        st.metric(
            "Industry-comparable value",
            _fmt(comparable_fair_value, target["currency"], "money"),
            delta=_fmt(comparable_upside, kind="percent"),
            border=True,
        )
    with method_columns[3]:
        st.metric("DCF confidence", _fmt(confidence_score, kind="score"), border=True)
    if price is not None and price > 0:
        margin_rows = [
            {
                "Method": name,
                "Margin of safety vs current price": _fmt(
                    (value - price) / value,
                    kind="percent",
                ) if value is not None and value > 0 else "Unavailable",
            }
            for name, value in (
                ("Standard DCF", target_fair_value),
                ("Normalized DCF", normalized_fair_value),
                ("Industry comparables", comparable_fair_value),
            )
        ]
        st.dataframe(
            pd.DataFrame(margin_rows),
            hide_index=True,
            alt="Margin of safety for each valuation method relative to current price",
        )

    fcf_history = target["historical_fcf_summary"]
    st.caption(
        f"Normalized FCF default: {fcf_history['normalization_method'] or 'unavailable; fewer than three complete operating-cash-flow/capex periods'}. "
        f"It uses {fcf_history['normalization_period_count']} complete reported periods "
        f"({', '.join(fcf_history['normalization_periods']) or 'none'}); "
        f"reported FCF is separately available for {fcf_history['fcf_count']} periods "
        f"({', '.join(fcf_history['fcf_periods']) or 'none'}). "
        f"{'Five or more years of reported FCF are available' if fcf_history['has_five_year_history'] else 'Fewer than five years of reported FCF are available'}. "
        "The editable starting FCF is a model-derived estimate or explicit user assumption, not a provider forecast."
    )
    if fcf_history["fcf_count"] < 5:
        st.warning(
            "Fewer than five annual FCF observations are available. Mid-cycle normalization is low-confidence; "
            "inspect the reported history and edit the normalized starting FCF only with an explicit rationale."
        )
    if fcf_history["reported_fcf_median"] is not None:
        st.caption(
            f"Median reported historical FCF reference: "
            f"{_fmt(fcf_history['reported_fcf_median'], target['currency'], 'large_money')}."
        )
    if fcf_history["fcf_values"]:
        fcf_chart = pd.Series(
            fcf_history["fcf_values"],
            index=fcf_history["fcf_periods"],
            name="Reported FCF",
        ).to_frame()
        if not fcf_chart.empty:
            st.subheader("Historical reported FCF")
            st.line_chart(
                fcf_chart,
                y_label=f"FCF ({target['currency']})",
                alt="Historical reported free cash flow for cyclical peak and trough context",
            )
        st.caption(
            f"Reported FCF peak year: {fcf_history['peak_year'] or 'unavailable'}; "
            f"trough year: {fcf_history['trough_year'] or 'unavailable'}. "
            "The median is a transparent historical reference, not a claim that all periods are economically normal."
        )
    if fcf_history["ebitda_margins"]:
        ebitda_chart = pd.Series(
            fcf_history["ebitda_margins"],
            index=fcf_history["ebitda_margin_periods"],
            name="Reported EBITDA margin",
        ).to_frame()
        st.subheader("Historical calculated EBITDA margins")
        st.line_chart(
            ebitda_chart,
            y_label="EBITDA margin",
            alt="Historical EBITDA margin calculated from annual operating income and depreciation and amortization",
        )
        st.caption("EBITDA is calculated as reported operating income plus reported depreciation and amortization.")
    if fcf_history["operating_cash_flow_values"]:
        cashflow_chart = pd.DataFrame(
            {
                "Operating cash flow": fcf_history["operating_cash_flow_values"],
                "Capital expenditure": fcf_history["capex_values"],
            },
            index=fcf_history["normalization_periods"],
        )
        st.subheader("Historical operating cash flow and capital expenditure")
        st.line_chart(
            cashflow_chart,
            y_label=f"Amount ({target['currency']})",
            alt="Reported operating cash flow and capital expenditure supporting normalized free cash flow",
        )

    current_fcf = target["free_cash_flow"]
    normalized_fcf = normalized_fcf_override
    latest_ebitda_margin = target["ebitda_margin"]
    median_ebitda_margin = fcf_history["median_ebitda_margin"]
    above_midcycle = (
        cyclical_industry
        and (
            (current_fcf is not None and normalized_fcf and normalized_fcf > 0 and current_fcf > normalized_fcf * 1.5)
            or (
                latest_ebitda_margin is not None and median_ebitda_margin is not None
                and fcf_history["ebitda_margin_std"] is not None
                and latest_ebitda_margin > median_ebitda_margin + fcf_history["ebitda_margin_std"]
            )
        )
    )
    if cyclical_industry:
        if above_midcycle:
            st.warning(
                "Current FCF or EBITDA margin is materially above the historical mid-cycle reference; "
                "peak earnings may not be sustainable. Compare standard and normalized DCF before using the base case."
            )
        else:
            st.info(
                "This business is classified as cyclical. Review historical FCF and EBITDA margins; "
                "the current period is not automatically treated as sustainable."
            )

    st.subheader("Industry comparables")
    peer_rows = []
    for symbol in industry_peers:
        peer = companies.get(symbol)
        if peer:
            peer_rows.append({
                "Ticker": symbol,
                "Company": peer["name"],
                "Industry": peer["industry"],
                "EV / EBITDA": _fmt(peer["ev_ebitda"], kind="multiple"),
                "Reporting currency": peer["currency"],
            })
    if peer_rows:
        st.dataframe(
            pd.DataFrame(peer_rows),
            hide_index=True,
            alt="Industry-specific comparable companies used for valuation",
        )
        st.caption(
            f"Comparable value uses the median EV/EBITDA ({_fmt(peer_median_multiple, kind='multiple')}) "
            f"from {len(peer_multiples)} available industry peer(s), applied to target EBITDA calculated "
            "from latest annual operating income plus depreciation and amortization. "
            "This is a peer-multiple reference, not a forecast."
        )
    else:
        st.info(
            f"No usable industry peer EV/EBITDA data is available for {industry_classification}; "
            "cross-sector benchmarks are intentionally excluded from comparable-company valuation."
        )
    if ticker == "MU":
        st.caption(
            "SK Hynix and Samsung Electronics are the primary Micron comparables. Samsung has a more "
            "diversified business mix beyond memory, so its multiple is not a pure-play memory benchmark."
        )
        st.caption(
            "A direct memory-price series is not available from the current data integration. "
            "Revenue-growth assumptions, operating margins, and capex intensity are exposed as editable sensitivities; "
            "no memory-price estimate is fabricated."
        )

    st.subheader("Reverse DCF: market-implied FCF growth")
    if implied_growth is None:
        st.info(
            "Reverse DCF is unavailable: it requires positive reported FCF, market value, cash, debt, "
            "diluted shares, and valid WACC/terminal-growth assumptions."
        )
    else:
        st.metric(
            "Market-implied annual FCF growth",
            _fmt(implied_growth, kind="percent"),
            delta=(
                f"{(implied_growth - base_growth):+.1%} vs. base assumption"
            ),
        )
        st.caption(
            "Solves for a constant annual FCF growth rate over the selected forecast horizon that equates "
            "the model's enterprise value to current market enterprise value; it is not an analyst forecast."
        )

    st.subheader("WACC and terminal-growth sensitivity")
    if standard_base_result and scenario_forecasts.get("Base"):
        sensitivity_rows = []
        base_wacc = scenario_inputs["Base"]["wacc"]
        base_terminal_growth = scenario_inputs["Base"]["terminal_growth"]
        sensitivity_waccs = [
            base_wacc - .02, base_wacc - .01, base_wacc,
            base_wacc + .01, base_wacc + .02,
        ]
        sensitivity_terminals = [
            max(0, base_terminal_growth - .01),
            base_terminal_growth,
            base_terminal_growth + .01,
        ]
        for sensitivity_wacc in sensitivity_waccs:
            row = {"WACC / terminal growth": f"{sensitivity_wacc:.1%}"}
            for sensitivity_terminal in sensitivity_terminals:
                result = calculate_forecast_dcf(
                    scenario_forecasts["Base"],
                    target["diluted_shares"],
                    target["cash"],
                    target["debt"],
                    target["minority_interest"],
                    sensitivity_wacc,
                    sensitivity_terminal,
                )
                row[f"Terminal growth {sensitivity_terminal:.1%}"] = (
                    _fmt(result["fair_value_per_share"], target["currency"], "money")
                    if result else "Unavailable"
                )
            sensitivity_rows.append(row)
        st.dataframe(
            pd.DataFrame(sensitivity_rows),
            hide_index=True,
            alt="Fair value per share sensitivity matrix for WACC and terminal growth",
        )
        st.caption(
            "Sensitivity holds the base-case financial forecast fixed and varies only WACC and terminal growth. "
            "Key forecast drivers are guided or modeled revenue, margins, operating cash flow, capital expenditure, "
            "and diluted shares; inspect the line-item sources and publication dates above."
        )
    else:
        st.info("Sensitivity is unavailable until a valid standard DCF can be calculated.")

    st.subheader("DCF confidence and review flags")
    st.caption(
        "Confidence is independent of upside and reflects historical cash-flow stability, sensitivity, "
        "data completeness, cyclicality, normalization coverage, and terminal-value dependence."
    )
    confidence_rows = [
        {"Factor": factor, "Score": f"{score:.0f}/100"}
        for factor, score in confidence_result["components"].items()
    ]
    st.dataframe(
        pd.DataFrame(confidence_rows),
        hide_index=True,
        alt="Separate DCF confidence components for data stability and model reliability",
    )
    if any(value is not None and value > (price or 0) * 3 for value in scenario_fair_values.values()):
        st.warning(
            "At least one scenario implies more than 200% upside. Review growth, margin, capex, WACC, "
            "and terminal assumptions; exceptional modeled upside is not treated as high confidence."
        )
    st.subheader("What the valuation implies")
    if target_fair_value is None:
        st.warning(
            "Standard DCF could not be calculated from available reported data and selected assumptions. "
            "No missing FCF, cash, debt, share count, or valuation output has been silently substituted."
        )
    else:
        st.write(
            f"At the current adjusted close of **{_fmt(price, target['currency'], 'money')}**, "
            f"the base model estimates **{_fmt(target_fair_value, target['currency'], 'money')}** per share. "
            "Small changes in free-cash-flow growth, discount rate, or terminal growth can materially change this result."
        )
    st.caption(
        "The five scenarios are deterministic assumption sets, not probability-weighted forecasts. "
        "No scenario probabilities are assigned. Standard DCF uses the latest reported annual FCF; normalized DCF uses "
        "the editable history-based operating-cash-flow/capex-margin estimate or explicit user input. Margin and capex assumptions are applied only when "
        "the supporting reported inputs are available; detailed segment revenue, working-capital, or future share-dilution schedules are not modeled."
    )

    st.subheader("Long-term return hurdles")
    if price is None or price <= 0:
        st.info("Long-term return hurdles require a valid last closing price.")
    else:
        hurdle_rows = []
        for multiple in (2, 3, 5, 10):
            hurdle_rows.append({
                "Outcome": f"{multiple}x",
                "Implied share price": _fmt(price * multiple, target["currency"], "money"),
                "Implied market cap": _fmt(
                    target["market_cap"] * multiple if target["market_cap"] is not None else None,
                    target["currency"],
                    "large_money",
                ),
                f"Annualized return over {projection_years} years": _fmt(
                    multiple ** (1 / projection_years) - 1,
                    kind="percent",
                ),
            })
        st.dataframe(
            pd.DataFrame(hurdle_rows),
            hide_index=True,
            alt="Required share price, market capitalization, and annualized return for 2x to 10x outcomes",
        )
        st.caption(
            "These are mathematical return hurdles, not forecasts or probabilities. "
            "A multi-fold share-price gain would require earnings growth and/or valuation expansion to justify it."
        )

    _render_research_comparison(
        "Valuation multiples vs benchmarks",
        "Valuation",
        companies,
        scores,
        fair_values,
        "Permanent benchmarks provide broad market context and may not be direct industry peers. "
        "Use the industry-comparable valuation above for peer multiples; prices and financial amounts retain local currencies.",
    )

elif navigation == "Technicals":
    st.header("Price and technical analysis")
    timeframe = st.segmented_control(
        "Price timeframe",
        options=("1M", "3M", "6M", "1Y", "3Y", "5Y"),
        default="1Y",
        key="technical_timeframe",
    )
    days_by_period = {"1M": 31, "3M": 92, "6M": 183, "1Y": 365, "3Y": 365 * 3, "5Y": 365 * 5}
    technical = technical_indicators(target["history"])
    days = days_by_period[timeframe]
    chart = technical.tail(days)[["Close"]].copy()
    overlay_options = st.multiselect(
        "Price chart overlays",
        options=("SMA 50", "SMA 200", "EMA 20", "BB upper", "BB lower"),
        default=("SMA 50", "SMA 200"),
        key="technical_overlays",
    )
    for column in overlay_options:
        chart[column] = technical[column].tail(days)
    st.line_chart(
        chart,
        y_label=f"Adjusted price ({target['currency']})",
        alt=f"{timeframe} adjusted share price for {target['name']} with selected moving-average and Bollinger overlays",
    )
    show_volume = st.toggle("Show trading volume", value=False, key="show_volume")
    if show_volume and "Volume" in technical:
        st.bar_chart(
            technical["Volume"].tail(days),
            y_label="Shares traded",
            alt=f"{timeframe} trading volume for {target['name']}",
        )

    latest = technical.iloc[-1]
    indicators = [
        ("RSI (14)", _fmt(latest.get("RSI 14"))),
        ("MACD", _fmt(latest.get("MACD"))),
        ("MACD signal", _fmt(latest.get("MACD signal"))),
        ("ATR (14)", _fmt(latest.get("ATR 14"), target["currency"], "money")),
        ("SMA 50", _fmt(latest.get("SMA 50"), target["currency"], "money")),
        ("SMA 200", _fmt(latest.get("SMA 200"), target["currency"], "money")),
    ]
    st.dataframe(
        pd.DataFrame(indicators, columns=("Indicator", "Latest")),
        hide_index=True,
        alt="Latest calculated technical indicator values",
    )
    performance_rows = [
        {"Period": label, "Return": _fmt(value, kind="percent")}
        for label, value in target["performance"].items()
    ]
    st.subheader("Performance and risk")
    st.dataframe(
        pd.DataFrame(performance_rows),
        hide_index=True,
        alt="Historical returns, volatility, and maximum drawdown",
    )
    st.caption(
        "Indicators use adjusted daily OHLCV history returned by Yahoo Finance. "
        "No signal or indicator is a prediction of future returns."
    )
    st.subheader(f"{timeframe} price performance vs benchmarks")
    benchmark_price_chart = _chart_history(companies, days)
    if benchmark_price_chart.empty:
        st.info("Benchmark price history is unavailable for the selected period.")
    else:
        st.line_chart(
            benchmark_price_chart,
            y_label="Indexed price (first available close = 100)",
            alt=f"{timeframe} indexed price comparison for {target['name']} and available benchmarks",
        )
        st.caption(
            "Each company's price is indexed to its first available adjusted close in this period, "
            "so percentage performance can be compared without converting currencies."
        )

    benchmark_technical_rows = []
    for symbol, company in companies.items():
        history = company["history"]
        if history.empty or "Close" not in history.columns:
            continue
        latest_peer = technical_indicators(history).iloc[-1]
        benchmark_technical_rows.append({
            "Company": f"{company['name']} ({symbol})",
            "Currency": company["currency"],
            "Adjusted close": _fmt(latest_peer.get("Close"), company["currency"], "money"),
            "SMA 50": _fmt(latest_peer.get("SMA 50"), company["currency"], "money"),
            "SMA 200": _fmt(latest_peer.get("SMA 200"), company["currency"], "money"),
            "RSI (14)": _fmt(latest_peer.get("RSI 14")),
            "1-year return": _fmt(
                company["performance"].get("1 year return"), kind="percent"
            ),
            "Beta": _fmt(company["beta"]),
        })
    st.subheader("Latest technical indicators vs benchmarks")
    if benchmark_technical_rows:
        st.dataframe(
            pd.DataFrame(benchmark_technical_rows),
            hide_index=True,
            alt="Latest price, moving averages, RSI, one-year return, and beta for the company and benchmarks",
        )
    else:
        st.info("Benchmark technical indicators are unavailable.")

elif navigation == "Ownership & news":
    st.header("Ownership, analyst data, and sources")
    ownership_rows = [
        ("Insider ownership", _fmt(target["insider_ownership"], kind="percent")),
        ("Institutional ownership", _fmt(target["institutional_ownership"], kind="percent")),
        ("Short interest / float", _fmt(target["short_interest"], kind="percent")),
        ("Analyst consensus", str(target["analyst_rating"]).upper() if target["analyst_rating"] else "N/A"),
        ("Analyst count", _fmt(target["analyst_count"])),
        ("Mean analyst target", _fmt(target["analyst_target"], target["currency"], "money")),
    ]
    st.dataframe(
        pd.DataFrame(ownership_rows, columns=("Metric", "Latest value")),
        hide_index=True,
        alt="Provider-reported ownership and analyst estimates",
    )
    if target["analyst_target"] and target["price"]:
        analyst_upside = target["analyst_target"] / target["price"] - 1
        st.metric(
            "Mean analyst target implied change",
            _fmt(analyst_upside, kind="percent"),
            help="Analyst consensus is an estimate, not a guaranteed return.",
        )
    st.info(
        "Individual institutional holders, insider transaction history, and verified company news are "
        "not available from the current data feed in this MVP. They are shown as unavailable rather than inferred."
    )
    st.subheader("Company and data sources")
    if target["website"]:
        st.link_button("Company website", target["website"], icon=":material/open_in_new:")
    st.markdown(
        "- Market prices, company profile, annual statements, ownership aggregates, and analyst consensus: "
        "[Yahoo Finance](https://finance.yahoo.com/), accessed via yfinance.\n"
        "- Price history is adjusted daily data and can be delayed; financials are as reported by the provider."
    )
    st.caption(
        f"Retrieved {target['retrieved_at']:%Y-%m-%d %H:%M UTC}. "
        "Check the company's filings and investor-relations materials before making an investment decision."
    )
    ownership_comparison = [
        {
            "Company": f"{company['name']} ({symbol})",
            "Insider ownership": _fmt(company.get("insider_ownership"), kind="percent"),
            "Institutional ownership": _fmt(
                company.get("institutional_ownership"), kind="percent"
            ),
            "Short interest / float": _fmt(
                company.get("short_interest"), kind="percent"
            ),
            "Analyst rating": (
                str(company["analyst_rating"]).upper()
                if company.get("analyst_rating") else "N/A"
            ),
            "Analyst count": _fmt(company.get("analyst_count")),
            "Mean analyst target": _fmt(
                company.get("analyst_target"), company.get("currency"), "money"
            ),
            "Currency": company.get("currency", "N/A"),
        }
        for symbol, company in companies.items()
    ]
    st.subheader("Ownership and analyst data vs benchmarks")
    st.dataframe(
        pd.DataFrame(ownership_comparison),
        hide_index=True,
        alt="Provider-reported ownership and analyst estimates for the company and available benchmarks",
    )
    st.caption(
        "Availability and analyst coverage vary by company. Mean price targets retain each company's currency "
        "and are not directly comparable across exchanges."
    )

elif navigation == "Risk analysis":
    st.header("Risk analysis")
    st.caption(
        "Risk indicators below are calculated from the existing price history and reported statements; "
        "they are descriptive measures, not forecasts."
    )
    risk_columns = st.columns(4)
    risk_metrics = (
        ("Rule-based risk score", _fmt(scores[ticker].get("Risk"), kind="score")),
        ("Beta", _fmt(target["beta"])),
        (
            "Maximum drawdown",
            _fmt(target["performance"].get("Maximum drawdown"), kind="percent"),
        ),
        (
            "Historical volatility",
            _fmt(target["performance"].get("Historical volatility"), kind="percent"),
        ),
    )
    for column, (label, value) in zip(risk_columns, risk_metrics):
        column.metric(label, value, border=True, height="stretch")
    risk_detail = [
        {
            "Measure": "Beta",
            "Value": _fmt(target["beta"]),
            "Source / interpretation": "Provider-reported sensitivity to the market; unavailable if not supplied.",
        },
        {
            "Measure": "Maximum drawdown",
            "Value": _fmt(
                target["performance"].get("Maximum drawdown"), kind="percent"
            ),
            "Source / interpretation": "Largest peak-to-trough decline in available adjusted price history.",
        },
        {
            "Measure": "Historical volatility",
            "Value": _fmt(
                target["performance"].get("Historical volatility"), kind="percent"
            ),
            "Source / interpretation": "Annualized standard deviation of daily returns in available history.",
        },
        {
            "Measure": "Net debt / EBITDA",
            "Value": _fmt(target["net_debt_ebitda"], kind="multiple"),
            "Source / interpretation": "Latest available balance-sheet net debt divided by EBITDA.",
        },
        {
            "Measure": "Current ratio",
            "Value": _fmt(target["current_ratio"], kind="multiple"),
            "Source / interpretation": "Latest available current assets divided by current liabilities.",
        },
    ]
    st.dataframe(
        pd.DataFrame(risk_detail),
        hide_index=True,
        alt="Existing market, price-history, and balance-sheet risk indicators with definitions",
    )
    st.caption(
        "The rule-based risk score reuses the existing scoring algorithm. "
        "Missing risk inputs remain unavailable rather than being estimated."
    )
    risk_comparison_rows = [
        {
            "Company": f"{company['name']} ({symbol})",
            "Risk score": _fmt(scores[symbol].get("Risk"), kind="score"),
            "Beta": _fmt(company.get("beta")),
            "Maximum drawdown": _fmt(
                company["performance"].get("Maximum drawdown"), kind="percent"
            ),
            "Historical volatility": _fmt(
                company["performance"].get("Historical volatility"), kind="percent"
            ),
            "Net debt / EBITDA": _fmt(
                company.get("net_debt_ebitda"), kind="multiple"
            ),
            "Current ratio": _fmt(company.get("current_ratio"), kind="multiple"),
        }
        for symbol, company in companies.items()
    ]
    st.subheader("Risk indicators vs benchmarks")
    st.dataframe(
        pd.DataFrame(risk_comparison_rows),
        hide_index=True,
        alt="Risk score, beta, drawdown, volatility, debt, and liquidity for the company and benchmarks",
    )
    st.caption(
        "Risk scores use the existing rule-based calculation. Higher risk scores indicate greater measured risk; "
        "financial data availability and reporting periods vary by company."
    )

elif navigation == "Watchlist":
    st.header("Watchlist")
    st.caption(
        "Track tickers locally. Quotes and scores shown here come from the same cached market-data "
        "and analysis pipeline used elsewhere in the app."
    )
    with st.container(border=True):
        with st.form("add_watchlist_ticker", border=False):
            watchlist_columns = st.columns([3, 1], vertical_alignment="bottom")
            with watchlist_columns[0]:
                watchlist_ticker = st.text_input(
                    "Ticker to add",
                    placeholder="e.g. MSFT or RELIANCE.NS",
                    key="watchlist_ticker_input",
                )
            with watchlist_columns[1]:
                add_watchlist_ticker = st.form_submit_button(
                    "Add to watchlist",
                    type="primary",
                    icon=":material/bookmark_add:",
                    width="stretch",
                    key="add_watchlist_ticker",
                )
    if add_watchlist_ticker:
        try:
            normalized_ticker = validate_ticker(watchlist_ticker)
        except ValueError as exc:
            st.error(str(exc))
        else:
            if normalized_ticker in user_data["watchlist"]:
                st.warning(f"{normalized_ticker} is already in your watchlist.")
            else:
                updated_data = {
                    **user_data,
                    "watchlist": [*user_data["watchlist"], normalized_ticker],
                }
                if _persist_user_data(updated_data):
                    st.rerun()

    st.subheader(f"Saved tickers · {len(user_data['watchlist'])}")
    if not user_data["watchlist"]:
        st.info("Your watchlist is empty. Add a ticker above to get started.")
    for watchlist_symbol in user_data["watchlist"]:
        company = companies.get(watchlist_symbol)
        company_name = company["name"] if company else watchlist_symbol
        watchlist_score = scores.get(watchlist_symbol, {}).get("Overall score")
        quote_price = company.get("price") if company else None
        daily_return = (
            company.get("performance", {}).get("1 day return")
            if company else None
        )
        with st.container(border=True):
            row_columns = st.columns([2.2, 1.2, 1.1, 1, 0.8, 0.8], vertical_alignment="center")
            with row_columns[0]:
                st.markdown(f"**{company_name}**")
                st.caption(watchlist_symbol)
            row_columns[1].metric(
                "Last close",
                _fmt(quote_price, company["currency"] if company else None, "money"),
            )
            row_columns[2].metric(
                "Daily change",
                _fmt(daily_return, kind="percent"),
                delta=_fmt(daily_return, kind="percent") if daily_return is not None else None,
            )
            row_columns[3].metric(
                "Screen score", _fmt(watchlist_score, kind="score")
            )
            row_columns[4].button(
                "Research",
                key=f"research_watchlist_{watchlist_symbol}",
                icon=":material/search:",
                on_click=_open_research,
                args=(watchlist_symbol,),
                width="stretch",
            )
            if row_columns[5].button(
                "Remove",
                key=f"remove_watchlist_{watchlist_symbol}",
                icon=":material/bookmark_remove:",
                help=f"Remove {watchlist_symbol} from your watchlist",
                width="stretch",
            ):
                updated_data = {
                    **user_data,
                    "watchlist": [
                        item for item in user_data["watchlist"]
                        if item != watchlist_symbol
                    ],
                }
                if _persist_user_data(updated_data):
                    st.rerun()

elif navigation == "Portfolio":
    st.header("Portfolio")
    st.caption(
        "Manually entered positions are saved on this machine. Current value and return are shown "
        "only when a quote is available; different trading currencies are not combined."
    )
    with st.container(border=True):
        with st.form("add_portfolio_position", border=False):
            position_columns = st.columns([1.5, 1.3, 1.3, 1], vertical_alignment="bottom")
            with position_columns[0]:
                position_ticker_input = st.text_input(
                    "Ticker",
                    placeholder="e.g. AAPL",
                    key="portfolio_ticker_input",
                )
            with position_columns[1]:
                position_quantity = st.number_input(
                    "Shares",
                    min_value=0.000001,
                    value=1.0,
                    step=1.0,
                    format="%.6f",
                    key="portfolio_quantity_input",
                )
            with position_columns[2]:
                position_cost = st.number_input(
                    "Average cost / share",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    format="%.4f",
                    key="portfolio_cost_input",
                    help="Enter the average cost in the ticker's trading currency.",
                )
            with position_columns[3]:
                add_position = st.form_submit_button(
                    "Add position",
                    type="primary",
                    icon=":material/add:",
                    width="stretch",
                    key="add_portfolio_position",
                )
    if add_position:
        try:
            normalized_ticker = validate_ticker(position_ticker_input)
        except ValueError as exc:
            st.error(str(exc))
        else:
            if any(
                position["ticker"] == normalized_ticker
                for position in user_data["portfolio"]
            ):
                st.warning(
                    f"{normalized_ticker} is already in the portfolio. "
                    "Remove it first if you need to replace the saved position."
                )
            else:
                new_position = {
                    "ticker": normalized_ticker,
                    "quantity": position_quantity,
                    "average_cost": position_cost,
                }
                updated_data = {
                    **user_data,
                    "portfolio": [*user_data["portfolio"], new_position],
                }
                if _persist_user_data(updated_data):
                    st.rerun()

    st.subheader(f"Positions · {len(user_data['portfolio'])}")
    if not user_data["portfolio"]:
        st.info("No positions have been added. Enter a ticker, share count, and average cost above.")
    for position in user_data["portfolio"]:
        position_ticker = position["ticker"]
        company = companies.get(position_ticker)
        price = company.get("price") if company else None
        currency = company.get("currency") if company else "N/A"
        shares = position["quantity"]
        average_cost = position["average_cost"]
        market_value = price * shares if price is not None else None
        cost_basis = average_cost * shares
        unrealized_gain = market_value - cost_basis if market_value is not None else None
        return_pct = (
            unrealized_gain / cost_basis
            if unrealized_gain is not None and cost_basis > 0 else None
        )
        company_name = company["name"] if company else position_ticker
        with st.container(border=True):
            st.markdown(f"**{company_name} · {position_ticker}**")
            position_columns = st.columns([1, 1, 1, 1, 1, 0.8], vertical_alignment="center")
            position_columns[0].metric("Shares", _fmt(shares))
            position_columns[1].metric(
                "Average cost",
                _fmt(average_cost, currency, "money"),
            )
            position_columns[2].metric(
                "Last close",
                _fmt(price, currency, "money"),
            )
            position_columns[3].metric(
                "Market value",
                _fmt(market_value, currency, "large_money"),
            )
            position_columns[4].metric(
                "Unrealized return",
                _fmt(unrealized_gain, currency, "large_money"),
                delta=_fmt(return_pct, kind="percent")
                if return_pct is not None else None,
            )
            if position_columns[5].button(
                "Remove",
                key=f"remove_position_{position_ticker}",
                icon=":material/delete:",
                help=f"Remove {position_ticker} from your portfolio",
                width="stretch",
            ):
                updated_data = {
                    **user_data,
                    "portfolio": [
                        item for item in user_data["portfolio"]
                        if item["ticker"] != position_ticker
                    ],
                }
                if _persist_user_data(updated_data):
                    st.rerun()

elif navigation == "Settings":
    st.header("Settings")
    st.subheader("Appearance")
    selected_theme = st.radio(
        "Color theme",
        options=("Dark", "Light"),
        index=("Dark", "Light").index(user_data["theme"]),
        horizontal=True,
        key="appearance_theme",
    )
    if selected_theme != user_data["theme"]:
        updated_data = {**user_data, "theme": selected_theme}
        if _persist_user_data(updated_data):
            st.rerun()
    st.caption(
        "Theme preferences and personal lists are stored locally on this machine. "
        "They are not synced to GitHub or other devices."
    )
    st.code(str(DEFAULT_USER_DATA_PATH), language=None)
    st.subheader("Data")
    st.caption(
        "Quotes and financial data use the existing Yahoo Finance integration; official guidance "
        "uses the existing SEC EDGAR integration."
    )
    if st.button(
        "Refresh cached market and filing data",
        icon=":material/refresh:",
        key="refresh_all_data",
    ):
        get_stock_data.clear()
        get_company_guidance.clear()
        st.rerun()
