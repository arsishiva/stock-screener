from __future__ import annotations

import streamlit as st

THEMES = {
    "Dark": {
        "background": "#0B1118",
        "surface": "#111A24",
        "surface_alt": "#172330",
        "text": "#E8EEF4",
        "muted": "#9BAAB8",
        "border": "#253342",
        "accent": "#20B887",
        "accent_soft": "#12392F",
        "negative": "#F06C73",
        "warning": "#E9B85C",
    },
    "Light": {
        "background": "#F3F6F8",
        "surface": "#FFFFFF",
        "surface_alt": "#F8FAFB",
        "text": "#18232D",
        "muted": "#60717F",
        "border": "#DDE5EA",
        "accent": "#07875F",
        "accent_soft": "#E1F3ED",
        "negative": "#C9404A",
        "warning": "#9A6900",
    },
}


def apply_theme(theme_name: str) -> None:
    theme = THEMES.get(theme_name, THEMES["Dark"])
    dark = theme_name == "Dark"
    st.html(
        f"""
        <style>
        :root {{
          color-scheme: {"dark" if dark else "light"};
          --primary-color: {theme["accent"]};
          --background-color: {theme["background"]};
          --secondary-background-color: {theme["surface"]};
          --text-color: {theme["text"]};
          --border-color: {theme["border"]};
          --research-bg: {theme["background"]};
          --research-surface: {theme["surface"]};
          --research-surface-alt: {theme["surface_alt"]};
          --research-text: {theme["text"]};
          --research-muted: {theme["muted"]};
          --research-border: {theme["border"]};
          --research-accent: {theme["accent"]};
          --research-accent-soft: {theme["accent_soft"]};
          --research-negative: {theme["negative"]};
          --research-warning: {theme["warning"]};
        }}
        .stApp,
        [data-testid="stAppViewContainer"] {{
          background: var(--research-bg);
          color: var(--research-text);
          font-family: Inter, "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        [data-testid="stMain"],
        [data-testid="stSidebar"] {{
          color: var(--research-text);
        }}
        [data-testid="stHeader"] {{
          background: transparent;
        }}
        [data-testid="stSidebar"] {{
          background: var(--research-surface);
          border-right: 1px solid var(--research-border);
        }}
        [data-testid="stSidebar"] > div:first-child {{
          padding-top: 1.2rem;
        }}
        .stApp [data-testid="stMainBlockContainer"] {{
          max-width: 1560px;
          padding-top: 1.35rem;
          padding-bottom: 3rem;
        }}
        [data-testid="stMetric"] {{
          background: var(--research-surface);
          border: 1px solid var(--research-border);
          border-radius: 12px;
          padding: 1rem 1.05rem;
        }}
        [data-testid="stMetricLabel"] p {{
          color: var(--research-muted);
          font-size: 0.78rem;
          font-weight: 600;
          letter-spacing: 0.025em;
        }}
        [data-testid="stMetricValue"] {{
          color: var(--research-text);
          font-size: clamp(1.1rem, 1.6vw, 1.55rem);
          font-weight: 650;
        }}
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3,
        [data-testid="stMarkdownContainer"] h4,
        [data-testid="stMarkdownContainer"] blockquote,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stRadio"] label,
        [data-testid="stCheckbox"] label,
        [data-testid="stToggle"] label,
        [data-testid="stCaptionContainer"],
        [data-testid="stText"] {{
          color: var(--research-text);
        }}
        [data-testid="stCaptionContainer"] {{
          color: var(--research-muted);
        }}
        [data-testid="stVerticalBlockBorderWrapper"] > div {{
          border-color: var(--research-border);
          border-radius: 12px;
        }}
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {{
          border: 1px solid var(--research-border);
          border-radius: 10px;
          overflow: hidden;
        }}
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
          background-color: var(--research-surface);
          color: var(--research-text);
          border-color: var(--research-border);
          border-radius: 9px;
        }}
        [data-testid="stSelectbox"] [data-baseweb="select"] *,
        [data-testid="stMultiSelect"] [data-baseweb="select"] * {{
          color: var(--research-text);
        }}
        [data-testid="stTextInput"] input::placeholder,
        [data-testid="stTextArea"] textarea::placeholder {{
          color: var(--research-muted);
        }}
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button,
        [data-testid="stDownloadButton"] button {{
          border-radius: 9px;
          font-weight: 600;
          min-height: 2.55rem;
          transition: border-color 120ms ease, background 120ms ease;
        }}
        [data-testid="stButton"] button:not([kind="primary"]),
        [data-testid="stFormSubmitButton"] button:not([kind="primary"]),
        [data-testid="stDownloadButton"] button {{
          background: var(--research-surface);
          color: var(--research-text);
          border-color: var(--research-border);
        }}
        [data-testid="stButton"] button[kind="primary"],
        [data-testid="stFormSubmitButton"] button[kind="primary"] {{
          background: var(--research-accent);
          border-color: var(--research-accent);
          color: #FFFFFF;
        }}
        [data-testid="stButton"] button:hover,
        [data-testid="stFormSubmitButton"] button:hover,
        [data-testid="stDownloadButton"] button:hover {{
          border-color: var(--research-accent);
        }}
        h1, h2, h3 {{
          letter-spacing: -0.025em;
        }}
        h1 {{
          font-size: clamp(1.7rem, 3vw, 2.45rem);
        }}
        h2 {{
          font-size: clamp(1.3rem, 2.2vw, 1.8rem);
        }}
        [data-testid="stAlert"] {{
          border-radius: 10px;
        }}
        @media (max-width: 760px) {{
          .stApp [data-testid="stMainBlockContainer"] {{
            padding: 0.8rem 0.85rem 2rem;
          }}
          [data-testid="stMetric"] {{
            padding: 0.75rem;
          }}
        }}
        @media (prefers-reduced-motion: reduce) {{
          *, *::before, *::after {{
            scroll-behavior: auto !important;
            transition-duration: 0.01ms !important;
          }}
        }}
        </style>
        """
    )
