"""Official SEC filing discovery and conservative numeric-guidance extraction."""

from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import requests
import pandas as pd

LOGGER = logging.getLogger(__name__)
SEC_BASE = "https://www.sec.gov"
SEC_DATA = "https://data.sec.gov"
SEC_USER_AGENT = os.getenv(
    "STOCK_SCREENER_SEC_USER_AGENT",
    "StockScreener/1.0 (contact: https://github.com/arsishiva/stock-screener)",
)
REQUEST_TIMEOUT = 20
MAX_DOCUMENT_BYTES = 3_000_000
MAX_FILINGS_TO_SCAN = 8

GUIDANCE_CUES = re.compile(
    r"\b(?:guid(?:ance|ed)|expect(?:s|ed)?|anticipat(?:e|es|ed)|"
    r"forecast|project(?:s|ed)?|outlook|target(?:s|ed)?|"
    r"will\s+(?:be|range|increase|decrease)|plan(?:s|ned)?\s+to|"
    r"approximately|about|between|range\s+of)\b",
    re.IGNORECASE,
)
RANGE_PATTERN = re.compile(
    r"(?P<first>(?:US\$|[$€£¥])?\s*\(?-?\d[\d,]*(?:\.\d+)?\)?"
    r"\s*(?:%|percent|billion|bn|million|mn|thousand|mm)?)"
    r"\s*(?:to|through|and|[-–—])\s*"
    r"(?P<second>(?:US\$|[$€£¥])?\s*\(?-?\d[\d,]*(?:\.\d+)?\)?"
    r"\s*(?:%|percent|billion|bn|million|mn|thousand|mm)?)",
    re.IGNORECASE,
)
VALUE_PATTERN = re.compile(
    r"(?P<value>(?:US\$|[$€£¥])?\s*\(?-?\d[\d,]*(?:\.\d+)?\)?"
    r"\s*(?:%|percent|billion|bn|million|mn|thousand|mm)?)",
    re.IGNORECASE,
)
FISCAL_QUARTER_PATTERN = re.compile(
    r"\b(?:Q([1-4])\s*(?:FY\s*)?(20\d{2})|"
    r"(first|second|third|fourth)\s+quarter\s+of\s+"
    r"(?:fiscal\s+)?(?:FY\s*)?(20\d{2}))\b",
    re.IGNORECASE,
)
NEXT_QUARTER_PATTERN = re.compile(
    r"\b(?:next|upcoming|following)\s+(?:fiscal\s+)?quarter\b",
    re.IGNORECASE,
)

METRICS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("revenue_growth", re.compile(r"\b(?:revenue|sales)\s+growth\b|\bgrowth\s+in\s+(?:revenue|sales)\b", re.I)),
    ("gross_margin", re.compile(r"\bgross\s+(?:profit\s+)?margin\b", re.I)),
    ("operating_margin", re.compile(r"\boperating\s+margin\b", re.I)),
    ("operating_expenses", re.compile(r"\b(?:operating expenses|research and development expenses|selling, general and administrative expenses)\b", re.I)),
    ("operating_cash_flow", re.compile(r"\b(?:operating cash flow|cash flow from operations)\b", re.I)),
    ("free_cash_flow", re.compile(r"\bfree cash flow\b", re.I)),
    ("capital_expenditure", re.compile(r"\b(?:capital expenditures|capital expenditure|capital spending|capex)\b", re.I)),
    ("tax_rate", re.compile(r"\b(?:effective )?tax rate\b", re.I)),
    ("diluted_shares", re.compile(r"\b(?:diluted shares|weighted average shares|share dilution)\b", re.I)),
    ("eps", re.compile(r"\b(?:diluted )?(?:earnings|income) per share\b|\bEPS\b", re.I)),
    ("segment_revenue", re.compile(r"\bsegment\b.{0,50}\b(?:revenue|sales)\b|\b(?:revenue|sales)\b.{0,50}\bsegment\b", re.I)),
    ("production_volume", re.compile(r"\b(?:production|shipments|bit shipments|capacity|utilization|yield)\b", re.I)),
    ("backlog_orders", re.compile(r"\b(?:backlog|orders|demand|bookings)\b", re.I)),
    ("capital_allocation", re.compile(r"\b(?:buyback|repurchase|dividend|capital allocation|debt repayment)\b", re.I)),
    ("revenue", re.compile(r"\b(?:revenue|net sales|total sales)\b", re.I)),
    ("medium_term_target", re.compile(r"\b(?:long.term|medium.term|multi.year)\b.{0,60}\b(?:target|goal|revenue|margin|growth)\b", re.I)),
)


class _DocumentText(HTMLParser):
    """Extract readable document text without executing or retaining markup."""

    BLOCK_TAGS = {
        "br", "div", "p", "tr", "td", "th", "li", "h1", "h2", "h3",
        "h4", "section", "article",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.ignored_depth += 1
        elif tag in self.BLOCK_TAGS and not self.ignored_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignored_depth:
            self.ignored_depth -= 1
        elif tag in self.BLOCK_TAGS and not self.ignored_depth:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
    })
    return session


def _get_json(session: requests.Session, url: str) -> dict[str, Any]:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise ValueError(f"Unexpected SEC response format from {url}")
    return result


def _ticker_map(session: requests.Session) -> dict[str, dict[str, Any]]:
    data = _get_json(session, f"{SEC_BASE}/files/company_tickers.json")
    companies: dict[str, dict[str, Any]] = {}
    for item in data.values():
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper()
        if ticker:
            companies[ticker] = {
                "cik": int(item["cik_str"]),
                "name": item.get("title"),
            }
    return companies


def _find_company(session: requests.Session, ticker: str) -> dict[str, Any] | None:
    normalized = ticker.upper().strip()
    companies = _ticker_map(session)
    exact = companies.get(normalized)
    if exact:
        return exact
    aliases = {
        normalized.replace(".", "-"),
        normalized.replace("-", "."),
    }
    return next((company for alias in aliases if (company := companies.get(alias))), None)


def _filing_rows(submissions: dict[str, Any]) -> list[dict[str, Any]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    rows = []
    for index, form in enumerate(forms):
        if form not in {"8-K", "6-K", "10-Q", "10-K", "20-F", "40-F"}:
            continue
        try:
            rows.append({
                "form": form,
                "filing_date": recent["filingDate"][index],
                "report_date": recent.get("reportDate", [""] * len(forms))[index],
                "accession": recent["accessionNumber"][index],
                "primary_document": recent["primaryDocument"][index],
                "primary_description": (
                    recent.get("primaryDocDescription", [""] * len(forms))[index]
                ),
            })
        except (IndexError, KeyError, TypeError):
            LOGGER.warning("Skipping malformed SEC filing entry at index %s", index)
    return rows


def _filing_url(cik: int, accession: str, filename: str) -> str:
    accession_path = accession.replace("-", "")
    return (
        f"{SEC_BASE}/Archives/edgar/data/{cik}/{accession_path}/"
        f"{requests.utils.quote(filename)}"
    )


def _document_text(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
    response.raise_for_status()
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_content(chunk_size=64_000):
        size += len(chunk)
        if size > MAX_DOCUMENT_BYTES:
            break
        chunks.append(chunk)
    content = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    if "<" in content[:1000]:
        parser = _DocumentText()
        parser.feed(content)
        content = "".join(parser.parts)
    content = html.unescape(content)
    return re.sub(r"[ \t\r\f\v]+", " ", content).strip()


def _period_from_sentence(
    sentence: str, report_date: str, document_index: int
) -> tuple[str | None, str]:
    quarter = FISCAL_QUARTER_PATTERN.search(sentence)
    if quarter:
        quarter_number = quarter.group(1)
        year = quarter.group(2)
        if quarter_number is None:
            quarter_number = {
                "first": "1", "second": "2", "third": "3", "fourth": "4",
            }[quarter.group(3).casefold()]
            year = quarter.group(4)
        return f"FY{year} Q{quarter_number}", "Explicit fiscal quarter in source text"
    if NEXT_QUARTER_PATTERN.search(sentence) and report_date:
        try:
            report_period = datetime.strptime(report_date, "%Y-%m-%d")
            month = report_period.month + 3
            year = report_period.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            quarter_number = (month - 1) // 3 + 1
            return f"FY{year} Q{quarter_number}", "Next quarter relative to filing reporting period"
        except ValueError:
            pass
    if re.search(r"\bfull\s+(?:fiscal\s+)?year\b|\bFY\s*20\d{2}\b", sentence, re.I):
        year_match = re.search(r"\b(?:FY\s*)?(20\d{2})\b", sentence, re.I)
        year = year_match.group(1) if year_match else (
            report_date[:4] if report_date else None
        )
        return (f"FY{year}" if year else None), "Full-year period mentioned in source text"
    return None, "Forecast period not explicitly identified"


def _parse_value(token: str, metric: str, sentence: str) -> tuple[float | None, str, str]:
    number_match = re.search(r"-?\d[\d,]*(?:\.\d+)?", token)
    if not number_match:
        return None, "", ""
    try:
        value = float(number_match.group(0).replace(",", ""))
    except ValueError:
        return None, "", ""

    token_casefold = token.casefold()
    sentence_casefold = sentence.casefold()
    if "%" in token or "percent" in token_casefold:
        unit = "percent"
        multiplier = 1.0
    elif any(term in token_casefold for term in ("billion", " bn")) or "billion" in sentence_casefold:
        unit = "billion"
        multiplier = 1_000_000_000.0
    elif any(term in token_casefold for term in ("million", " mn", " mm")) or "million" in sentence_casefold:
        unit = "million"
        multiplier = 1_000_000.0
    elif "thousand" in token_casefold or "thousand" in sentence_casefold:
        unit = "thousand"
        multiplier = 1_000.0
    elif metric == "eps":
        unit = "per share"
        multiplier = 1.0
    elif metric == "diluted_shares":
        unit = "shares"
        multiplier = 1.0
    else:
        unit = "company currency"
        multiplier = 1.0

    currency_symbol = next((symbol for symbol in ("US$", "$", "€", "£", "¥") if symbol in token), "")
    return value * multiplier, unit, currency_symbol


def _extract_numeric_guidance(sentence: str, metric: str) -> dict[str, Any]:
    metric_match = next(
        (pattern.search(sentence) for key, pattern in METRICS if key == metric),
        None,
    )
    if metric_match is None:
        return {"low": None, "high": None, "display": None, "unit": None}

    remaining = sentence[metric_match.end():]
    range_match = RANGE_PATTERN.search(remaining)
    if range_match:
        first_token = range_match.group("first")
        second_token = range_match.group("second")
        low_value, unit, currency_symbol = _parse_value(first_token, metric, sentence)
        high_value, _, high_currency_symbol = _parse_value(second_token, metric, sentence)
        if low_value is not None and high_value is not None:
            display = f"{first_token.strip()} to {second_token.strip()}"
            return {
                "low": min(low_value, high_value),
                "high": max(low_value, high_value),
                "display": display,
                "unit": unit,
                "currency_symbol": currency_symbol or high_currency_symbol,
            }

    value_match = VALUE_PATTERN.search(remaining)
    if not value_match:
        return {"low": None, "high": None, "display": None, "unit": None}
    token = value_match.group("value")
    if re.search(r"\b20\d{2}\b", token):
        return {"low": None, "high": None, "display": None, "unit": None}
    value, unit, currency_symbol = _parse_value(token, metric, sentence)
    if value is None:
        return {"low": None, "high": None, "display": None, "unit": None}
    return {
        "low": value,
        "high": value,
        "display": token.strip(),
        "unit": unit,
        "currency_symbol": currency_symbol,
    }


def extract_guidance_from_document(
    text: str,
    *,
    ticker: str,
    currency: str,
    document: dict[str, Any],
    document_index: int,
) -> list[dict[str, Any]]:
    """Extract only numeric ranges or exact figures in explicitly forward-looking sentences."""
    extracted: list[dict[str, Any]] = []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    seen: set[tuple[str, str, str | None]] = set()
    for raw_sentence in sentences:
        sentence = re.sub(r"\s+", " ", raw_sentence).strip()
        if not sentence or len(sentence) > 1800 or not GUIDANCE_CUES.search(sentence):
            continue
        for metric, pattern in METRICS:
            if not pattern.search(sentence):
                continue
            numeric = _extract_numeric_guidance(sentence, metric)
            period, period_basis = _period_from_sentence(
                sentence, document.get("reporting_period", ""), document_index
            )
            unique_key = (metric, sentence[:180], period)
            if unique_key in seen:
                continue
            seen.add(unique_key)
            basis_context = sentence.casefold()
            accounting_basis = (
                "Non-GAAP" if re.search(r"\bnon[\s-]?gaap\b|\badjusted\b", basis_context)
                else "GAAP" if re.search(r"\bGAAP\b", sentence, re.I)
                else "Not specified in source sentence"
            )
            has_numeric = numeric["low"] is not None
            extracted.append({
                "ticker": ticker,
                "metric": metric,
                "classification": "Company guidance" if has_numeric else "Qualitative management commentary",
                "low": numeric["low"],
                "high": numeric["high"],
                "display_value": numeric["display"],
                "unit": numeric["unit"],
                "currency": currency,
                "currency_symbol": numeric.get("currency_symbol"),
                "accounting_basis": accounting_basis,
                "period": period,
                "period_basis": period_basis,
                "sentence": sentence[:1200],
                "source_url": document["source_url"],
                "publication_date": document["publication_date"],
                "reporting_period": document["reporting_period"],
                "retrieved_at": document["retrieved_at"],
                "document_reference": document["document_reference"],
                "form": document["form"],
            })
    return extracted


def _document_candidates(
    session: requests.Session, cik: int, filing: dict[str, Any]
) -> list[dict[str, Any]]:
    accession = filing["accession"]
    filing_directory = (
        f"{SEC_BASE}/Archives/edgar/data/{cik}/{accession.replace('-', '')}"
    )
    try:
        index_data = _get_json(session, f"{filing_directory}/index.json")
        files = index_data.get("directory", {}).get("item", [])
    except (requests.RequestException, ValueError, KeyError) as exc:
        LOGGER.warning("SEC filing index unavailable for %s: %s", accession, exc)
        files = []

    candidates: list[tuple[int, str, str]] = []
    for file_info in files:
        name = file_info.get("name", "")
        description = " ".join(
            str(file_info.get(key, ""))
            for key in ("type", "description", "name")
        ).casefold()
        if not name.lower().endswith((".htm", ".html", ".txt")):
            continue
        if name.casefold() == filing["primary_document"].casefold():
            candidates.append((0, name, description))
        elif filing["form"] in {"8-K", "6-K"} and (
            "99.1" in description or "earnings" in description
            or "press release" in description or "results" in description
            or "presentation" in description or "prepared remarks" in description
            or "transcript" in description
        ):
            priority = 1 if any(
                term in description for term in ("99.1", "earnings", "press release", "results")
            ) else 2
            candidates.append((priority, name, description))

    if not candidates and filing.get("primary_document"):
        candidates.append((0, filing["primary_document"], filing.get("primary_description", "")))

    unique: dict[str, tuple[int, str, str]] = {}
    for candidate in candidates:
        unique[candidate[1]] = candidate
    selected = sorted(unique.values(), key=lambda row: row[0])[:3]
    now = datetime.now(timezone.utc).isoformat()
    documents = []
    for _, name, description in selected:
        is_presentation = "presentation" in description or "slides" in description
        is_transcript = "transcript" in description or "prepared remarks" in description
        if filing["form"] in {"10-K", "20-F", "40-F"}:
            document_type = "Annual report"
        elif filing["form"] == "10-Q":
            document_type = "Quarterly regulatory filing"
        elif is_presentation:
            document_type = "Earnings presentation"
        elif is_transcript:
            document_type = "Prepared remarks or transcript"
        elif filing["form"] in {"8-K", "6-K"}:
            document_type = "Current report / earnings-release exhibit"
        else:
            document_type = "Regulatory filing"
        documents.append({
            "form": filing["form"],
            "filing_date": filing["filing_date"],
            "report_date": filing["report_date"],
            "accession": accession,
            "document_reference": name,
            "description": description,
            "document_type": document_type,
            "is_earnings_release": (
                filing["form"] in {"8-K", "6-K"}
                and any(
                    term in description.casefold()
                    for term in ("99.1", "earnings", "press release", "results")
                )
            ),
            "source_url": _filing_url(cik, accession, name),
            "retrieved_at": now,
        })
    return documents


def fetch_official_guidance(
    ticker: str, currency: str = "N/A"
) -> dict[str, Any]:
    """Retrieve recent SEC filings and extract auditable numeric forward-looking data."""
    symbol = ticker.upper().strip()
    session = _session()
    retrieved_at = datetime.now(timezone.utc).isoformat()
    try:
        company = _find_company(session, symbol)
        if company is None:
            return {
                "ticker": symbol,
                "provider": "SEC EDGAR",
                "status": "unavailable",
                "reason": (
                    "No matching SEC registrant was found for this ticker. "
                    "Non-US companies not reporting to the SEC require a national-regulator source integration."
                ),
                "retrieved_at": retrieved_at,
                "documents": [],
                "guidance": [],
                "company_name": None,
                "cik": None,
            }
        cik = company["cik"]
        submissions = _get_json(
            session,
            f"{SEC_DATA}/submissions/CIK{cik:010d}.json",
        )
        filings = _filing_rows(submissions)
        filings.sort(key=lambda row: row["filing_date"], reverse=True)

        relevant: list[dict[str, Any]] = []
        recent_current_filings = [
            row for row in filings if row["form"] in {"8-K", "6-K"}
        ][:MAX_FILINGS_TO_SCAN]
        relevant.extend(recent_current_filings)
        for form in ("10-Q", "10-K", "20-F", "40-F"):
            filing = next((row for row in filings if row["form"] == form), None)
            if filing and filing not in relevant:
                relevant.append(filing)

        documents: list[dict[str, Any]] = []
        for filing in relevant:
            try:
                documents.extend(_document_candidates(session, cik, filing))
            except requests.RequestException as exc:
                LOGGER.warning("Could not index SEC filing %s: %s", filing["accession"], exc)

        guidance: list[dict[str, Any]] = []
        for document in documents:
            if document["form"] not in {"8-K", "6-K"}:
                continue
            try:
                text = _document_text(session, document["source_url"])
            except (requests.RequestException, UnicodeError) as exc:
                LOGGER.warning("Could not retrieve SEC document %s: %s", document["source_url"], exc)
                continue
            normalized_document = {
                **document,
                "publication_date": document["filing_date"],
                "reporting_period": document["report_date"],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
            guidance.extend(extract_guidance_from_document(
                text,
                ticker=symbol,
                currency=currency,
                document=normalized_document,
                document_index=len(documents),
            ))

        release_accessions = {
            document["accession"] for document in documents
            if document["is_earnings_release"]
        }
        latest_earnings_filing = next(
            (row for row in recent_current_filings if row["accession"] in release_accessions),
            None,
        )
        days_old = None
        if latest_earnings_filing:
            try:
                days_old = (
                    datetime.now(timezone.utc).date()
                    - datetime.strptime(
                        latest_earnings_filing["filing_date"], "%Y-%m-%d"
                    ).date()
                ).days
            except ValueError:
                pass
        if not latest_earnings_filing:
            status = "no earnings release filing located"
            reason = (
                "No recent SEC 8-K/6-K exhibit identifiable as an earnings release was located. "
                "Other current reports are not treated as earnings guidance."
            )
        elif days_old is not None and days_old > 150:
            status = "potentially expired"
            reason = (
                f"The newest 8-K/6-K filing located is {days_old} days old. "
                "Guidance may have expired; no newer SEC earnings filing was located."
            )
        else:
            status = "available"
            reason = None
        if not guidance and status == "available":
            reason = (
                "Recent SEC earnings filings were found, but no numeric guidance ranges "
                "or exact figures could be confidently extracted. Qualitative statements are not converted."
            )
        return {
            "ticker": symbol,
            "provider": "SEC EDGAR",
            "status": status,
            "reason": reason,
            "retrieved_at": retrieved_at,
            "documents": documents,
            "guidance": guidance,
            "company_name": submissions.get("name") or company.get("name"),
            "cik": cik,
            "latest_earnings_filing_date": (
                latest_earnings_filing["filing_date"] if latest_earnings_filing else None
            ),
            "latest_earnings_report_date": (
                latest_earnings_filing["report_date"] if latest_earnings_filing else None
            ),
        }
    except (requests.RequestException, ValueError, KeyError, json.JSONDecodeError) as exc:
        LOGGER.warning("SEC filing retrieval failed for %s: %s", symbol, exc)
        return {
            "ticker": symbol,
            "provider": "SEC EDGAR",
            "status": "unavailable",
            "reason": f"SEC data could not be retrieved: {exc}",
            "retrieved_at": retrieved_at,
            "documents": [],
            "guidance": [],
            "company_name": None,
            "cik": None,
        }


def _guidance_midpoint(
    guidance: list[dict[str, Any]], metric: str, period_prefix: str
) -> dict[str, Any] | None:
    candidates = [
        item for item in guidance
        if item["metric"] == metric
        and item["classification"] == "Company guidance"
        and item.get("period")
        and item["period"] == period_prefix
    ]
    return max(candidates, key=lambda item: item["publication_date"]) if candidates else None


def _median(values: list[float]) -> float | None:
    values = [value for value in values if value is not None]
    return float(pd.Series(values).median()) if values else None


def build_financial_forecast(
    annual_history: list[dict[str, Any]],
    quarterly_history: list[dict[str, Any]],
    guidance_data: dict[str, Any],
    *,
    years: int = 5,
    quarters: int = 4,
    analyst_estimates: dict[str, Any] | None = None,
    model_assumptions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build auditable quarterly and annual forecasts from reported history and available guidance."""
    annual_history = sorted(annual_history, key=lambda row: row.get("Period", ""))
    quarterly_history = sorted(quarterly_history, key=lambda row: row.get("Period", ""))
    all_guidance = (
        guidance_data.get("guidance", [])
        if guidance_data.get("status") == "available"
        else []
    )
    latest_earnings_date = guidance_data.get("latest_earnings_filing_date")
    guidance = [
        item for item in all_guidance
        if latest_earnings_date
        and item.get("publication_date") == latest_earnings_date
    ]
    latest_annual = annual_history[-1] if annual_history else {}
    latest_quarter = quarterly_history[-1] if quarterly_history else {}
    historical_revenue_growth = [
        row["Revenue growth"] for row in annual_history
        if row.get("Revenue growth") is not None
    ]
    recent_growth = historical_revenue_growth[-3:]
    annual_growth_assumption = _median(recent_growth)
    if annual_growth_assumption is None and len(annual_history) > 3:
        start = annual_history[-4].get("Revenue")
        end = annual_history[-1].get("Revenue")
        if start is not None and end is not None and start > 0 and end > 0:
            annual_growth_assumption = (end / start) ** (1 / 3) - 1

    annual_rows: list[dict[str, Any]] = []
    base_revenue = latest_annual.get("Revenue")
    base_margin = _median([
        row["Gross margin"] for row in annual_history[-5:]
        if row.get("Gross margin") is not None
    ])
    operating_margin = _median([
        row["Operating margin"] for row in annual_history[-5:]
        if row.get("Operating margin") is not None
    ])
    net_margin = _median([
        row["Net margin"] for row in annual_history[-5:]
        if row.get("Net margin") is not None
    ])
    ocf_margin = _median([
        row["Operating cash flow"] / row["Revenue"]
        for row in annual_history[-5:]
        if row.get("Operating cash flow") is not None and row.get("Revenue")
    ])
    capex_margin = _median([
        abs(row["Capital expenditure"]) / row["Revenue"]
        for row in annual_history[-5:]
        if row.get("Capital expenditure") is not None and row.get("Revenue")
    ])
    latest_ocf_margin = (
        latest_annual["Operating cash flow"] / latest_annual["Revenue"]
        if latest_annual.get("Operating cash flow") is not None
        and latest_annual.get("Revenue") else ocf_margin
    )
    latest_capex_margin = (
        abs(latest_annual["Capital expenditure"]) / latest_annual["Revenue"]
        if latest_annual.get("Capital expenditure") is not None
        and latest_annual.get("Revenue") else capex_margin
    )
    share_history = [
        row["Diluted shares"] for row in annual_history[-5:]
        if row.get("Diluted shares") is not None
    ]
    diluted_shares = share_history[-1] if share_history else None

    latest_year = int(latest_annual["Fiscal year"]) if latest_annual.get("Fiscal year", "").isdigit() else datetime.now().year - 1
    model_assumptions = model_assumptions or {}
    annual_growth_rates = model_assumptions.get("annual_revenue_growth_rates", [])
    annual_base_revenue = base_revenue
    for offset in range(1, years + 1):
        fiscal_year = latest_year + offset
        annual_period = f"FY{fiscal_year}"
        company_revenue_guidance = _guidance_midpoint(
            guidance, "revenue", annual_period
        )
        if company_revenue_guidance:
            revenue = (company_revenue_guidance["low"] + company_revenue_guidance["high"]) / 2
            revenue_source = company_revenue_guidance
            revenue_classification = "Company guidance"
        elif (
            revenue_growth_guidance := _guidance_midpoint(
                guidance, "revenue_growth", annual_period
            )
        ):
            growth = (
                revenue_growth_guidance["low"]
                + revenue_growth_guidance["high"]
            ) / 200
            revenue = annual_base_revenue * (1 + growth) if annual_base_revenue is not None else None
            revenue_source = revenue_growth_guidance
            revenue_classification = (
                "Company guidance" if revenue is not None else "Unavailable"
            )
        elif analyst_estimates and fiscal_year in analyst_estimates.get("annual_revenue", {}):
            estimate = analyst_estimates["annual_revenue"][fiscal_year]
            revenue = estimate.get("value")
            revenue_source = estimate
            revenue_classification = "Analyst consensus"
        elif annual_base_revenue is not None and (
            annual_growth_rates[offset - 1]
            if offset <= len(annual_growth_rates) else annual_growth_assumption
        ) is not None:
            selected_growth = (
                annual_growth_rates[offset - 1]
                if offset <= len(annual_growth_rates) else annual_growth_assumption
            )
            revenue = annual_base_revenue * (1 + selected_growth)
            revenue_source = {
                "source_url": None,
                "publication_date": None,
                "document_reference": None,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
            revenue_classification = "Model estimate"
        else:
            revenue = None
            revenue_source = None
            revenue_classification = "Unavailable"
        if revenue is not None:
            annual_base_revenue = revenue

        def line_item(
            metric: str, computed: float | None, unit: str
        ) -> tuple[float | None, str, dict[str, Any] | None]:
            candidate = _guidance_midpoint(guidance, metric, annual_period)
            if candidate and candidate.get("period"):
                return (
                    (candidate["low"] + candidate["high"]) / 2,
                    "Company guidance",
                    candidate,
                )
            return computed, "Model estimate" if computed is not None else "Unavailable", None

        forecast_gross_margin = model_assumptions.get("gross_margin", base_margin)
        forecast_operating_margin = model_assumptions.get(
            "operating_margin", operating_margin
        )
        forecast_tax_rate = model_assumptions.get(
            "tax_rate",
            _median([
                row["Tax provision"] / row["Pretax income"]
                for row in annual_history[-5:]
                if row.get("Tax provision") is not None
                and row.get("Pretax income") is not None
                and row["Pretax income"] > 0
            ]),
        )
        forecast_ocf_margin = model_assumptions.get(
            "operating_cash_flow_margin", latest_ocf_margin
        )
        forecast_capex_margin = model_assumptions.get(
            "capital_expenditure_margin", latest_capex_margin
        )
        gross_profit = revenue * forecast_gross_margin if revenue is not None and forecast_gross_margin is not None else None
        operating_income = revenue * forecast_operating_margin if revenue is not None and forecast_operating_margin is not None else None
        net_income = revenue * net_margin if revenue is not None and net_margin is not None else None
        ocf = revenue * forecast_ocf_margin if revenue is not None and forecast_ocf_margin is not None else None
        capex = revenue * forecast_capex_margin if revenue is not None and forecast_capex_margin is not None else None
        values: dict[str, Any] = {
            "Gross margin": forecast_gross_margin,
            "Operating margin": forecast_operating_margin,
            "Operating expenses": (
                gross_profit - operating_income
                if gross_profit is not None and operating_income is not None else None
            ),
            "EPS": (net_income / diluted_shares if net_income is not None and diluted_shares else None),
            "Operating cash flow": ocf,
            "Capital expenditure": capex,
            "Free cash flow": ocf - capex if ocf is not None and capex is not None else None,
            "Diluted shares": diluted_shares,
            "Tax rate": forecast_tax_rate,
        }
        guidance_field_map = {
            "Gross margin": ("gross_margin", values["Gross margin"], "percent"),
            "Operating margin": ("operating_margin", values["Operating margin"], "percent"),
            "Operating expenses": ("operating_expenses", values["Operating expenses"], "company currency"),
            "EPS": ("eps", values["EPS"], "per share"),
            "Operating cash flow": ("operating_cash_flow", ocf, "company currency"),
            "Capital expenditure": ("capital_expenditure", capex, "company currency"),
            "Free cash flow": ("free_cash_flow", values["Free cash flow"], "company currency"),
            "Diluted shares": ("diluted_shares", diluted_shares, "shares"),
            "Tax rate": ("tax_rate", forecast_tax_rate, "percent"),
        }
        line_sources: dict[str, dict[str, Any]] = {}
        for field, (metric, computed, unit) in guidance_field_map.items():
            amount, classification, source = line_item(metric, computed, unit)
            if metric in {"gross_margin", "operating_margin", "tax_rate"} and source is not None and amount is not None:
                amount /= 100
            values[field] = amount
            line_sources[field] = {
                "classification": classification,
                "source": source,
                "model_method": (
                    f"Historical five-period median {field.casefold()} margin/ratio"
                    if classification == "Model estimate" else None
                ),
            }
        values["Gross profit"] = (
            revenue * values["Gross margin"]
            if revenue is not None and values["Gross margin"] is not None else None
        )
        values["Operating income"] = (
            values["Gross profit"] - values["Operating expenses"]
            if values["Gross profit"] is not None and values["Operating expenses"] is not None
            else (
                revenue * values["Operating margin"]
                if revenue is not None and values["Operating margin"] is not None else None
            )
        )
        values["Operating margin"] = (
            values["Operating income"] / revenue
            if values["Operating income"] is not None and revenue
            else values["Operating margin"]
        )
        interest_margin = _median([
            (row["Operating income"] - row["Pretax income"]) / row["Revenue"]
            for row in annual_history[-5:]
            if row.get("Operating income") is not None
            and row.get("Pretax income") is not None
            and row.get("Revenue")
        ])
        pretax_margin = _median([
            row["Pretax income"] / row["Revenue"]
            for row in annual_history[-5:]
            if row.get("Pretax income") is not None and row.get("Revenue")
        ])
        if (
            revenue is not None and values["Operating income"] is not None
            and interest_margin is not None and values["Tax rate"] is not None
        ):
            values["Net income"] = (
                values["Operating income"] - revenue * interest_margin
            ) * (1 - values["Tax rate"])
        elif revenue is not None and pretax_margin is not None and values["Tax rate"] is not None:
            values["Net income"] = revenue * pretax_margin * (1 - values["Tax rate"])
        else:
            values["Net income"] = net_income
        if values["EPS"] is not None and values["Diluted shares"] is not None:
            values["Net income"] = values["EPS"] * values["Diluted shares"]
        values["EPS"] = (
            values["Net income"] / values["Diluted shares"]
            if values["Net income"] is not None and values["Diluted shares"]
            else values["EPS"]
        )
        values["Free cash flow"] = (
            values["Operating cash flow"] - values["Capital expenditure"]
            if values["Operating cash flow"] is not None and values["Capital expenditure"] is not None
            else None
        )
        line_sources["Gross profit"] = {
            "classification": line_sources["Gross margin"]["classification"],
            "source": line_sources["Gross margin"]["source"],
            "model_method": "Revenue multiplied by projected gross margin",
        }
        line_sources["Operating income"] = {
            "classification": (
                line_sources["Operating expenses"]["classification"]
                if line_sources["Operating expenses"]["classification"] == "Company guidance"
                else line_sources["Operating margin"]["classification"]
            ),
            "source": (
                line_sources["Operating expenses"]["source"]
                or line_sources["Operating margin"]["source"]
            ),
            "model_method": "Gross profit less operating expenses, or revenue multiplied by operating margin",
        }
        line_sources["Net income"] = {
            "classification": (
                "Company guidance" if line_sources["EPS"]["classification"] == "Company guidance"
                else "Model estimate" if values["Net income"] is not None else "Unavailable"
            ),
            "source": line_sources["EPS"]["source"],
            "model_method": (
                "Guided EPS multiplied by projected diluted shares"
                if line_sources["EPS"]["classification"] == "Company guidance"
                else "Projected operating income, historical interest burden, and forecast tax rate"
            ),
        }
        line_sources["Free cash flow"] = {
            **line_sources["Free cash flow"],
            "model_method": (
                "Operating cash flow less capital expenditure"
                if values["Free cash flow"] is not None else "Unavailable: OCF or capex is missing"
            ),
        }
        line_sources["Revenue"] = {
            "classification": revenue_classification,
            "source": revenue_source,
            "model_method": (
                "Company-reported annual revenue guidance"
                if revenue_classification == "Company guidance"
                else "Historical annual revenue growth assumption"
                if revenue_classification == "Model estimate"
                else None
            ),
        }
        line_sources["Revenue growth"] = {
            "classification": revenue_classification,
            "source": revenue_source,
            "model_method": "Forecast revenue compared with prior annual revenue",
        }
        free_cash_flow_source = line_sources["Free cash flow"]["source"]
        operating_cash_flow_is_guided = (
            line_sources["Operating cash flow"]["classification"] == "Company guidance"
        )
        capex_is_guided = (
            line_sources["Capital expenditure"]["classification"] == "Company guidance"
        )
        if free_cash_flow_source:
            guided_fcf = (free_cash_flow_source["low"] + free_cash_flow_source["high"]) / 2
            if not operating_cash_flow_is_guided and values["Capital expenditure"] is not None:
                values["Operating cash flow"] = guided_fcf + abs(values["Capital expenditure"])
                values["Free cash flow"] = guided_fcf
                line_sources["Operating cash flow"] = {
                    "classification": "Model estimate implied by company FCF guidance",
                    "source": free_cash_flow_source,
                    "model_method": "Company FCF guidance plus modeled capital expenditure",
                }
            elif values["Operating cash flow"] is not None and not capex_is_guided:
                values["Capital expenditure"] = max(
                    0.0, values["Operating cash flow"] - guided_fcf
                )
                values["Free cash flow"] = (
                    values["Operating cash flow"] - values["Capital expenditure"]
                )
                line_sources["Capital expenditure"] = {
                    "classification": "Model estimate implied by company FCF guidance",
                    "source": free_cash_flow_source,
                    "model_method": "Modeled operating cash flow less company FCF guidance",
                }
            elif operating_cash_flow_is_guided and capex_is_guided:
                guidance_gap = values["Free cash flow"] - guided_fcf
                line_sources["Free cash flow"]["guidance_reconciliation_difference"] = guidance_gap
        annual_rows.append({
            "Period": f"FY{fiscal_year}",
            "Revenue": revenue,
            "Revenue growth": (
                revenue / (annual_rows[-1]["Revenue"] if annual_rows else base_revenue) - 1
                if revenue is not None
                and (annual_rows[-1]["Revenue"] if annual_rows else base_revenue)
                else None
            ),
            "Revenue classification": revenue_classification,
            "Revenue source": revenue_source,
            **values,
            "Line item sources": line_sources,
            "Model assumptions": {
                "annual revenue growth": (
                    annual_growth_rates[offset - 1]
                    if offset <= len(annual_growth_rates) else annual_growth_assumption
                ),
                "gross margin": forecast_gross_margin,
                "operating margin": forecast_operating_margin,
                "net margin": net_margin,
                "operating cash flow margin": forecast_ocf_margin,
                "capital expenditure / revenue": forecast_capex_margin,
                "tax rate": forecast_tax_rate,
            },
        })

    quarter_rows: list[dict[str, Any]] = []
    base_quarter_revenue = latest_quarter.get("Revenue")
    quarter_growth = (
        (
            1 + (
                annual_growth_rates[0]
                if annual_growth_rates else annual_growth_assumption
            )
        ) ** 0.25 - 1
        if (annual_growth_rates or annual_growth_assumption is not None) else None
    )
    quarter_anchor_date = latest_quarter.get("Period")
    anchor_year, anchor_quarter = latest_year, 0
    if quarter_anchor_date:
        try:
            anchor_period = datetime.strptime(quarter_anchor_date[:10], "%Y-%m-%d")
            anchor_year = anchor_period.year
            anchor_quarter = (anchor_period.month - 1) // 3 + 1
        except ValueError:
            pass
    for index in range(1, quarters + 1):
        q_index = anchor_quarter + index
        forecast_year = anchor_year + (q_index - 1) // 4
        forecast_quarter = (q_index - 1) % 4 + 1
        period = f"FY{forecast_year} Q{forecast_quarter}"
        quarter_guidance = _guidance_midpoint(guidance, "revenue", period)
        quarter_growth_guidance = _guidance_midpoint(
            guidance, "revenue_growth", period
        )
        if index == 1 and quarter_guidance is None:
            next_quarter_guidance = [
                item for item in guidance
                if item["metric"] == "revenue"
                and item["classification"] == "Company guidance"
                and item.get("period_basis")
                == "Next quarter relative to filing reporting period"
            ]
            if next_quarter_guidance:
                quarter_guidance = max(
                    next_quarter_guidance,
                    key=lambda item: item["publication_date"],
                )
        if index == 1 and quarter_growth_guidance is None:
            next_quarter_growth_guidance = [
                item for item in guidance
                if item["metric"] == "revenue_growth"
                and item["classification"] == "Company guidance"
                and item.get("period_basis")
                == "Next quarter relative to filing reporting period"
            ]
            if next_quarter_growth_guidance:
                quarter_growth_guidance = max(
                    next_quarter_growth_guidance,
                    key=lambda item: item["publication_date"],
                )
        if quarter_guidance:
            revenue = (quarter_guidance["low"] + quarter_guidance["high"]) / 2
            classification = "Company guidance"
            source = quarter_guidance
        elif (
            quarter_growth_guidance
            and base_quarter_revenue is not None
        ):
            growth = (
                quarter_growth_guidance["low"]
                + quarter_growth_guidance["high"]
            ) / 200
            revenue = base_quarter_revenue * (1 + growth)
            classification = "Company guidance"
            source = quarter_growth_guidance
        elif (
            base_quarter_revenue is not None and quarter_growth is not None
        ):
            revenue = base_quarter_revenue * (1 + quarter_growth) ** index
            classification = "Model estimate"
            source = None
        else:
            revenue = None
            classification = "Unavailable"
            source = None

        def historical_ratio(field: str) -> float | None:
            return _median([
                row[field] / row["Revenue"]
                for row in quarterly_history[-8:]
                if row.get(field) is not None and row.get("Revenue")
            ])

        quarter_gross_margin = historical_ratio("Gross profit")
        quarter_operating_margin = historical_ratio("Operating income")
        quarter_net_margin = historical_ratio("Net income")
        quarter_ocf_margin = historical_ratio("Operating cash flow")
        quarter_capex_margin = historical_ratio("Capital expenditure")
        quarter_gross_margin = model_assumptions.get("gross_margin", quarter_gross_margin)
        quarter_operating_margin = model_assumptions.get("operating_margin", quarter_operating_margin)
        quarter_ocf_margin = model_assumptions.get("operating_cash_flow_margin", quarter_ocf_margin)
        quarter_capex_margin = model_assumptions.get("capital_expenditure_margin", quarter_capex_margin)
        gross_profit = revenue * quarter_gross_margin if revenue is not None and quarter_gross_margin is not None else None
        operating_income = revenue * quarter_operating_margin if revenue is not None and quarter_operating_margin is not None else None
        net_income = revenue * quarter_net_margin if revenue is not None and quarter_net_margin is not None else None
        ocf = revenue * quarter_ocf_margin if revenue is not None and quarter_ocf_margin is not None else None
        capex = abs(revenue * quarter_capex_margin) if revenue is not None and quarter_capex_margin is not None else None
        quarter_shares = latest_quarter.get("Diluted shares") or diluted_shares
        quarter_eps = (
            net_income / quarter_shares
            if net_income is not None and quarter_shares else None
        )
        quarter_tax_rate = model_assumptions.get("tax_rate")
        def quarter_guidance_for(metric: str) -> dict[str, Any] | None:
            candidate = _guidance_midpoint(guidance, metric, period)
            if candidate is None and index == 1:
                next_quarter_candidates = [
                    item for item in guidance
                    if item["metric"] == metric
                    and item["classification"] == "Company guidance"
                    and item.get("period_basis")
                    == "Next quarter relative to filing reporting period"
                ]
                if next_quarter_candidates:
                    candidate = max(
                        next_quarter_candidates,
                        key=lambda item: item["publication_date"],
                    )
            return candidate

        quarterly_line_sources: dict[str, dict[str, Any]] = {}
        quarterly_fields = {
            "Revenue": ("revenue", revenue, "company currency"),
            "Gross margin": ("gross_margin", quarter_gross_margin, "percent"),
            "Operating margin": ("operating_margin", quarter_operating_margin, "percent"),
            "Operating expenses": (
                "operating_expenses",
                gross_profit - operating_income
                if gross_profit is not None and operating_income is not None else None,
                "company currency",
            ),
            "EPS": ("eps", quarter_eps, "per share"),
            "Operating cash flow": ("operating_cash_flow", ocf, "company currency"),
            "Capital expenditure": ("capital_expenditure", capex, "company currency"),
            "Free cash flow": ("free_cash_flow", None, "company currency"),
            "Diluted shares": ("diluted_shares", latest_quarter.get("Diluted shares") or diluted_shares, "shares"),
            "Tax rate": ("tax_rate", model_assumptions.get("tax_rate"), "percent"),
        }
        for field, (metric, computed, unit) in quarterly_fields.items():
            item = quarter_guidance_for(metric)
            if field == "Revenue" and quarter_guidance:
                item = quarter_guidance
            if item:
                amount = (item["low"] + item["high"]) / 2
                if metric in {"gross_margin", "operating_margin", "tax_rate"}:
                    amount /= 100 if amount > 1 else 1
                computed = amount
                classification = "Company guidance"
                if field == "Revenue":
                    revenue = amount
            else:
                classification = "Model estimate" if computed is not None else "Unavailable"
            quarterly_line_sources[field] = {
                "classification": classification,
                "source": item,
                "model_method": None if item else "Trailing eight reported-quarter median ratio",
            }
            if field == "Revenue":
                pass
            elif field == "Gross margin":
                quarter_gross_margin = computed
                gross_profit = revenue * computed if revenue is not None and computed is not None else None
            elif field == "Operating margin":
                quarter_operating_margin = computed
                operating_income = revenue * computed if revenue is not None and computed is not None else None
            elif field == "Operating expenses":
                operating_income = gross_profit - computed if gross_profit is not None and computed is not None else operating_income
            elif field == "Operating cash flow":
                ocf = computed
            elif field == "Capital expenditure":
                capex = abs(computed) if computed is not None else None
            elif field == "Free cash flow":
                pass
            elif field == "Diluted shares":
                quarter_shares = computed
            elif field == "Tax rate":
                quarter_tax_rate = computed
            elif field == "EPS" and item:
                net_income = computed * quarter_shares if computed is not None and quarter_shares else net_income
                quarter_eps = computed
        if (
            revenue is not None
            and quarterly_line_sources["Gross margin"]["classification"] != "Company guidance"
        ):
            gross_profit = (
                revenue * quarter_gross_margin if quarter_gross_margin is not None else None
            )
        if (
            revenue is not None
            and quarterly_line_sources["Operating margin"]["classification"] != "Company guidance"
            and quarterly_line_sources["Operating expenses"]["classification"] != "Company guidance"
        ):
            operating_income = (
                revenue * quarter_operating_margin
                if quarter_operating_margin is not None else None
            )
        if (
            revenue is not None
            and quarterly_line_sources["Operating cash flow"]["classification"] != "Company guidance"
        ):
            ocf = revenue * quarter_ocf_margin if quarter_ocf_margin is not None else None
        if (
            revenue is not None
            and quarterly_line_sources["Capital expenditure"]["classification"] != "Company guidance"
        ):
            capex = (
                abs(revenue * quarter_capex_margin)
                if quarter_capex_margin is not None else None
            )
        if (
            revenue is not None
            and quarterly_line_sources["EPS"]["classification"] != "Company guidance"
        ):
            net_income = (
                revenue * quarter_net_margin if quarter_net_margin is not None else None
            )
        quarter_fcf = ocf - capex if ocf is not None and capex is not None else None
        guided_fcf_source = quarterly_line_sources.get("Free cash flow", {}).get("source")
        ocf_guided = (
            quarterly_line_sources.get("Operating cash flow", {}).get("classification")
            == "Company guidance"
        )
        capex_guided = (
            quarterly_line_sources.get("Capital expenditure", {}).get("classification")
            == "Company guidance"
        )
        if guided_fcf_source:
            guided_fcf = (guided_fcf_source["low"] + guided_fcf_source["high"]) / 2
            if not ocf_guided and capex is not None:
                ocf = guided_fcf + capex
                quarter_fcf = guided_fcf
                quarterly_line_sources["Operating cash flow"] = {
                    "classification": "Model estimate implied by company FCF guidance",
                    "source": guided_fcf_source,
                    "model_method": "Company FCF guidance plus modeled capital expenditure",
                }
            elif ocf is not None and not capex_guided:
                capex = max(0.0, ocf - guided_fcf)
                quarter_fcf = ocf - capex
                quarterly_line_sources["Capital expenditure"] = {
                    "classification": "Model estimate implied by company FCF guidance",
                    "source": guided_fcf_source,
                    "model_method": "Modeled operating cash flow less company FCF guidance",
                }
        quarter_interest_margin = _median([
            (row["Operating income"] - row["Pretax income"]) / row["Revenue"]
            for row in annual_history[-5:]
            if row.get("Operating income") is not None
            and row.get("Pretax income") is not None
            and row.get("Revenue")
        ])
        if (
            net_income is not None and operating_income is not None
            and quarter_tax_rate is not None and quarter_interest_margin is not None
        ):
            net_income = (
                operating_income - revenue * quarter_interest_margin
            ) * (1 - quarter_tax_rate)
        if quarterly_line_sources.get("EPS", {}).get("classification") == "Company guidance":
            eps_source = quarterly_line_sources["EPS"]["source"]
            eps_midpoint = (eps_source["low"] + eps_source["high"]) / 2
            net_income = eps_midpoint * quarter_shares if quarter_shares else net_income
            quarter_eps = eps_midpoint
        else:
            quarter_eps = (
                net_income / quarter_shares
                if net_income is not None and quarter_shares else None
            )
            quarterly_line_sources["EPS"] = {
                "classification": "Model estimate" if quarter_eps is not None else "Unavailable",
                "source": None,
                "model_method": (
                    "Projected net income divided by diluted shares"
                    if quarter_eps is not None else None
                ),
            }
        quarterly_line_sources["Net income"] = {
            "classification": (
                "Company guidance" if quarterly_line_sources.get("EPS", {}).get("classification") == "Company guidance"
                else "Model estimate" if net_income is not None else "Unavailable"
            ),
            "source": quarterly_line_sources.get("EPS", {}).get("source"),
            "model_method": (
                "Guided EPS multiplied by projected diluted shares"
                if quarterly_line_sources.get("EPS", {}).get("classification") == "Company guidance"
                else "Reported operating income, historical interest burden, and tax-rate assumption"
            ),
        }
        quarterly_line_sources["Gross profit"] = {
            "classification": quarterly_line_sources["Gross margin"]["classification"],
            "source": quarterly_line_sources["Gross margin"]["source"],
            "model_method": "Revenue multiplied by projected gross margin",
        }
        quarterly_line_sources["Operating income"] = {
            "classification": (
                "Company guidance"
                if quarterly_line_sources["Operating expenses"]["classification"] == "Company guidance"
                else quarterly_line_sources["Operating margin"]["classification"]
            ),
            "source": (
                quarterly_line_sources["Operating expenses"]["source"]
                or quarterly_line_sources["Operating margin"]["source"]
            ),
            "model_method": "Gross profit less guided operating expenses, or revenue multiplied by operating margin",
        }
        quarterly_line_sources["Gross profit"] = {
            "classification": quarterly_line_sources["Gross margin"]["classification"],
            "source": quarterly_line_sources["Gross margin"]["source"],
            "model_method": "Revenue multiplied by projected gross margin",
        }
        quarterly_line_sources["Free cash flow"] = {
            **quarterly_line_sources.get("Free cash flow", {}),
            "model_method": (
                "Operating cash flow less capital expenditure"
                if quarter_fcf is not None else "Unavailable: OCF or capex is missing"
            ),
        }
        quarterly_line_sources["Revenue growth"] = {
            "classification": quarterly_line_sources["Revenue"]["classification"],
            "source": quarterly_line_sources["Revenue"]["source"],
            "model_method": "Forecast revenue compared with prior quarter",
        }
        quarter_rows.append({
            "Period": period,
            "Revenue": revenue,
            "Revenue growth": (
                revenue / base_quarter_revenue - 1
                if revenue is not None and base_quarter_revenue else None
            ),
            "Gross margin": quarter_gross_margin,
            "Gross profit": gross_profit,
            "Operating margin": quarter_operating_margin,
            "Operating expenses": (
                gross_profit - operating_income
                if gross_profit is not None and operating_income is not None else None
            ),
            "Operating income": operating_income,
            "Net income": net_income,
            "EPS": quarter_eps,
            "Tax rate": quarter_tax_rate,
            "Operating cash flow": ocf,
            "Capital expenditure": capex,
            "Free cash flow": quarter_fcf,
            "Diluted shares": quarter_shares,
            "Classification": classification,
            "Source": source,
            "Line item sources": quarterly_line_sources,
            "Model assumptions": {
                "quarterly revenue growth": quarter_growth,
                "gross margin": quarter_gross_margin,
                "operating margin": quarter_operating_margin,
                "net margin": quarter_net_margin,
                "operating cash flow margin": quarter_ocf_margin,
                "capital expenditure / revenue": quarter_capex_margin,
            },
        })
        if revenue is not None:
            base_quarter_revenue = revenue

    accuracy = guidance_accuracy(all_guidance, quarterly_history)
    return {
        "annual": annual_rows,
        "quarterly": quarter_rows,
        "guidance_accuracy": accuracy,
        "analyst_estimates_status": (
            "Unavailable: no licensed analyst-consensus provider is configured."
            if analyst_estimates is None else "Provider estimates supplied."
        ),
        "assumption_summary": {
            "annual revenue growth": annual_growth_assumption,
            "annual gross margin": base_margin,
            "annual operating margin": operating_margin,
            "annual net margin": net_margin,
            "annual operating cash flow margin": ocf_margin,
            "annual capital expenditure / revenue": capex_margin,
        },
    }


def guidance_accuracy(
    guidance: list[dict[str, Any]], quarterly_history: list[dict[str, Any]]
) -> dict[str, Any]:
    """Match prior period-specific revenue ranges to reported actuals only when periods align."""
    actuals: dict[str, float] = {}
    for row in quarterly_history:
        if row.get("Revenue") is None or not row.get("Period"):
            continue
        try:
            period_date = datetime.strptime(row["Period"][:10], "%Y-%m-%d")
            quarter = (period_date.month - 1) // 3 + 1
            actuals[f"FY{period_date.year} Q{quarter}"] = row["Revenue"]
        except ValueError:
            continue
    latest_by_period: dict[str, dict[str, Any]] = {}
    for item in guidance:
        period = item.get("period")
        if (
            item.get("metric") != "revenue"
            or item.get("classification") != "Company guidance"
            or not period
            or item.get("low") is None
            or item.get("high") is None
        ):
            continue
        previous = latest_by_period.get(period)
        if previous is None or item.get("publication_date", "") > previous.get("publication_date", ""):
            latest_by_period[period] = item

    comparisons = []
    now = datetime.now(timezone.utc).date()
    for period, item in latest_by_period.items():
        if period not in actuals:
            continue
        actual = actuals[period]
        midpoint = (item["low"] + item["high"]) / 2
        if midpoint == 0:
            continue
        publication = item.get("publication_date")
        if publication:
            try:
                if datetime.strptime(publication, "%Y-%m-%d").date() >= now:
                    continue
            except ValueError:
                continue
        result = "beat" if actual > item["high"] else "miss" if actual < item["low"] else "within range"
        comparisons.append({
            "period": period,
            "actual": actual,
            "midpoint": midpoint,
            "midpoint_variance": actual / midpoint - 1,
            "result": result,
            "source": item,
        })
    return {
        "comparisons": comparisons,
        "count": len(comparisons),
        "beat_count": sum(row["result"] == "beat" for row in comparisons),
        "miss_count": sum(row["result"] == "miss" for row in comparisons),
        "within_range_count": sum(row["result"] == "within range" for row in comparisons),
        "beat_rate": (
            sum(row["result"] == "beat" for row in comparisons) / len(comparisons)
            if comparisons else None
        ),
        "mean_midpoint_variance": (
            sum(row["midpoint_variance"] for row in comparisons) / len(comparisons)
            if comparisons else None
        ),
    }
