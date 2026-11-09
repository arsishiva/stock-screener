from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

LATEST_VIEW = "latest_stock_scores"
SNAPSHOT_TABLE = "stock_score_snapshots"
PAGE_SIZE = 1000
SCORE_FIELDS = {
    "business_quality": "Business quality",
    "financial_health": "Financial health",
    "moat_proxy": "Moat proxy",
    "growth": "Growth",
    "valuation": "Valuation",
    "technical_strength": "Technical strength",
    "risk": "Risk",
    "overall_score": "Overall score",
    "coverage": "Coverage",
}


@dataclass(frozen=True)
class ScoreStoreConfig:
    url: str
    service_role_key: str


class ScoreStoreError(RuntimeError):
    pass


def load_score_store_config(
    secrets: Mapping[str, Any] | None = None,
) -> ScoreStoreConfig | None:
    if secrets is None:
        try:
            secrets = st.secrets
            secret_url = secrets.get("SUPABASE_URL")
            secret_key = secrets.get("SUPABASE_SERVICE_ROLE_KEY")
        except StreamlitSecretNotFoundError:
            secret_url = None
            secret_key = None
    else:
        secret_url = secrets.get("SUPABASE_URL")
        secret_key = secrets.get("SUPABASE_SERVICE_ROLE_KEY")
    url = os.getenv("SUPABASE_URL") or secret_url
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or secret_key
    )
    if not url and not key:
        return None
    if not isinstance(url, str) or not url.strip():
        raise ScoreStoreError("SUPABASE_URL is missing or invalid.")
    if not isinstance(key, str) or not key.strip():
        raise ScoreStoreError("SUPABASE_SERVICE_ROLE_KEY is missing or invalid.")
    url = url.strip().rstrip("/")
    parsed_url = urlsplit(url)
    if (
        not parsed_url.netloc
        or parsed_url.query
        or parsed_url.fragment
        or parsed_url.path not in ("", "/")
        or (
            parsed_url.scheme != "https"
            and not (
                parsed_url.scheme == "http"
                and parsed_url.hostname in {"localhost", "127.0.0.1"}
            )
        )
    ):
        raise ScoreStoreError(
            "SUPABASE_URL must be an HTTPS project URL (HTTP is allowed only for localhost)."
        )
    return ScoreStoreConfig(url=url, service_role_key=key.strip())


def _headers(config: ScoreStoreConfig) -> dict[str, str]:
    return {
        "apikey": config.service_role_key,
        "Authorization": f"Bearer {config.service_role_key}",
        "Content-Type": "application/json",
    }


def _request(
    session: requests.Session,
    method: str,
    url: str,
    **kwargs: Any,
) -> requests.Response:
    try:
        response = session.request(method, url, timeout=20, **kwargs)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise ScoreStoreError("Supabase request timed out.") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        raise ScoreStoreError(
            f"Supabase returned HTTP {status}. Check the table/view schema and server secrets."
        ) from exc
    except requests.RequestException as exc:
        raise ScoreStoreError(f"Could not reach Supabase: {exc}") from exc
    return response


def _number(value: Any) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return numeric


def build_score_snapshots(
    companies: Mapping[str, Mapping[str, Any]],
    scores: Mapping[str, Mapping[str, Any]],
    *,
    snapshot_date: date | None = None,
    analyzed_at: datetime | None = None,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    snapshot_date = snapshot_date or now.date()
    analyzed_at = analyzed_at or now
    if analyzed_at.tzinfo is None:
        analyzed_at = analyzed_at.replace(tzinfo=timezone.utc)
    analyzed_at = analyzed_at.astimezone(timezone.utc)

    snapshots = []
    for ticker, company in companies.items():
        score = scores.get(ticker)
        if score is None:
            continue
        record: dict[str, Any] = {
            "ticker": ticker.strip().upper(),
            "company_name": company.get("name"),
            "sector": company.get("sector"),
            "industry": company.get("industry"),
            "currency": company.get("currency"),
            "score_date": snapshot_date.isoformat(),
            "analyzed_at": analyzed_at.isoformat(),
            "methodology_version": "scorecard-v1",
        }
        for field, score_key in SCORE_FIELDS.items():
            record[field] = _number(score.get(score_key))
        snapshots.append(record)
    return snapshots


def save_daily_snapshots(
    config: ScoreStoreConfig,
    snapshots: list[dict[str, Any]],
    *,
    session: requests.Session | None = None,
) -> None:
    if not snapshots:
        return
    session = session or requests.Session()
    url = f"{config.url}/rest/v1/{SNAPSHOT_TABLE}"
    headers = {
        **_headers(config),
        "Prefer": "resolution=ignore-duplicates,return=minimal",
    }
    for start in range(0, len(snapshots), 500):
        _request(
            session,
            "POST",
            url,
            params={"on_conflict": "ticker,score_date"},
            headers=headers,
            json=snapshots[start:start + 500],
        )


def _fetch_all(
    config: ScoreStoreConfig,
    resource: str,
    *,
    order: str,
    filters: Mapping[str, str] | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    session = session or requests.Session()
    url = f"{config.url}/rest/v1/{resource}"
    headers = {**_headers(config), "Range-Unit": "items"}
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        headers["Range"] = f"{offset}-{offset + PAGE_SIZE - 1}"
        response = _request(
            session,
            "GET",
            url,
            params={"select": "*", "order": order, **(filters or {})},
            headers=headers,
        )
        try:
            page = response.json()
        except ValueError as exc:
            raise ScoreStoreError("Supabase returned invalid JSON.") from exc
        if not isinstance(page, list) or any(not isinstance(row, dict) for row in page):
            raise ScoreStoreError("Supabase returned an unexpected score-history format.")
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def fetch_latest_snapshots(
    config: ScoreStoreConfig,
    *,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    return _fetch_all(
        config,
        LATEST_VIEW,
        order="ticker.asc",
        session=session,
    )


def fetch_snapshot_history(
    config: ScoreStoreConfig,
    *,
    ticker: str | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    return _fetch_all(
        config,
        SNAPSHOT_TABLE,
        order="score_date.desc,ticker.asc",
        filters={"ticker": f"eq.{ticker.strip().upper()}"} if ticker else None,
        session=session,
    )
