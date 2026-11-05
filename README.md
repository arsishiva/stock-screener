# Stock Screener

A Streamlit equity-research dashboard for looking up a public stock ticker and comparing its market data, financial statements, valuation, and technical indicators with Microsoft, Alphabet, Meta, and Apple.

## Run locally

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run
```

Streamlit opens the app at [http://localhost:8501](http://localhost:8501). The root `streamlit_app.py` launcher loads the dashboard from `stock_screener/app.py`.

To use an existing virtual environment, you can run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run
```

Enter a ticker in the sidebar. Use Yahoo Finance exchange suffixes for non-US listings, for example `RELIANCE.NS`, `SAP.DE`, or `7203.T`. Optional comparison peers can be entered as comma-separated tickers.

## Features

- Latest available price, company profile, annual statements, ownership aggregates, and analyst consensus from Yahoo Finance through `yfinance`.
- Financial and technical calculations derived from provider data, with missing values left unavailable.
- Side-by-side comparison with MSFT, GOOGL, META, and AAPL, including a seven-shade red-to-yellow-to-green relative heatmap and CSV export.
- A seven-indicator view for growth, margins, moat proxies, financial health, valuation, management, and momentum.
- Editable DCF assumptions, bear/base/bull sensitivities, comparable-company reference, and long-term return hurdles.
- Historical financial charts, indexed price comparisons, technical overlays, and calculated indicators.

## Project layout

```text
.
├── streamlit_app.py                 # Streamlit entry point
├── stock_screener/
│   ├── app.py                       # Dashboard UI
│   ├── analysis.py                  # Market data and calculation functions
│   └── legacy/                      # Retained utilities from the original screener
├── data/
│   └── tickers.csv                  # Optional ticker universe for legacy utilities
├── scripts/
│   ├── generate_massive_tickers.py
│   └── generate_pure_python_tickers.py
├── tests/
│   └── test_stock_analysis.py
├── docs/
│   └── PRD.md
├── requirements.txt
└── README.md
```

The current analysis dashboard does not use the legacy synthetic screener utilities or the ticker CSV; it looks up the entered ticker directly. The legacy data loader and filters are retained under `stock_screener/legacy/` and are not used to produce dashboard results.

## Data and limitations

- Market/fundamental data is retrieved from Yahoo Finance through `yfinance`; availability, timestamps, coverage, and display terms are controlled by that provider. Prices may be delayed.
- Historical statements, ownership aggregates, and analyst estimates may be missing, stale, or based on different reporting periods. Review the displayed currency, period, and retrieval time.
- Data unavailable from the current provider is marked `N/A` or `Unavailable`. Qualitative research, verified news, institutional accumulation, and several governance metrics are not inferred.
- DCF and scoring outputs are rule-based illustrations, sensitive to assumptions, and not investment advice or a prediction of returns.
- This project is for research only; it does not execute trades.

See [docs/PRD.md](docs/PRD.md) for the product requirements.

## Ticker-list utilities

The optional scripts regenerate `data/tickers.csv` and require network access. Run from any working directory:

```powershell
python scripts/generate_pure_python_tickers.py
```

The larger generator uses pandas and requests:

```powershell
python scripts/generate_massive_tickers.py
```

Generated ticker lists are consumed only by the retained legacy screener utilities, not by the current analysis dashboard.

## Tests

Run the calculation unit tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```
