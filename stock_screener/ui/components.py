from __future__ import annotations

from typing import Any

import streamlit as st


def render_company_heading(company: dict[str, Any], ticker: str) -> None:
    st.markdown(f"## {company['name']}")
    st.caption(
        f"{ticker} · {company['exchange']} · {company['country']} · "
        f"{company['currency']} · Market status: unavailable from current data"
    )
