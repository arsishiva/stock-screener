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

- Fintech-style responsive Streamlit shell with persistent dark/light appearance settings, company overview cards, and global ticker search.
- Local JSON watchlist and manually entered portfolio positions; user data is stored outside the repository at `~\.stock-screener\user_data.json` on Windows (or `~/.stock-screener/user_data.json` on macOS/Linux).
- Latest available price, company profile, annual/quarterly statements, and ownership aggregates from Yahoo Finance through `yfinance`.
- SEC EDGAR filing discovery for supported US-listed issuers, with source-linked numeric guidance extracted from recent earnings-related 8-K/6-K exhibits.
- Quarterly and five-or-more-year annual financial forecasts, with company-guidance, analyst-consensus, model-estimate, and unavailable classifications kept distinct.
- Forecast-derived standard DCF using projected operating cash flow less capital expenditure; a separate normalized-FCF DCF; per-line source/date inspection; and matched historical revenue-guidance accuracy where periods can be aligned.
- Financial and technical calculations derived from provider data, with missing values left unavailable.
- Side-by-side comparison with MSFT, GOOGL, META, and AAPL, including a seven-shade red-to-yellow-to-green relative heatmap and CSV export.
- A seven-indicator view for growth, margins, moat proxies, financial health, valuation, management, and momentum.
- Editable standard and normalized DCF models with annual FCF and revenue growth schedules, five scenarios, industry comparables, reverse DCF, WACC/terminal-growth sensitivity, and an independent confidence score.
- Historical financial charts, indexed price comparisons, technical overlays, and calculated indicators.

## Project layout

```text
.
├── streamlit_app.py                 # Streamlit entry point
├── stock_screener/
│   ├── app.py                       # Dashboard UI
│   ├── analysis.py                  # Market data and calculation functions
│   ├── guidance.py                  # SEC filing guidance and forecast inputs
│   ├── user_data.py                 # Local watchlist, portfolio, and preferences
│   ├── ui/
│   │   ├── components.py            # Reusable presentation components
│   │   └── theme.py                 # Fintech theme tokens and responsive styling
│   └── legacy/                      # Retained utilities from the original screener
├── .streamlit/
│   └── config.toml                  # Default dark theme
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
- SEC guidance retrieval depends on SEC availability and the registrant/ticker mapping. To identify your application to SEC EDGAR, set a descriptive contact value before launch in PowerShell:

  ```powershell
  $env:STOCK_SCREENER_SEC_USER_AGENT = "StockScreener/1.0 (contact: you@example.com)"
  python -m streamlit run
  ```

- This integration currently uses SEC filings only. It does not crawl company investor-relations websites, licensed transcript services, or non-US regulators; an unavailable SEC response or unsupported foreign listing is shown as unavailable rather than replaced with invented guidance. SEC-derived extracted values link to their filing exhibit and retain the evidence sentence, publication date, reporting period, and retrieval time.
- Analyst consensus is unavailable because no licensed analyst-estimates provider is configured. Yahoo Finance profile data is not represented as licensed consensus.
- The forecast prioritizes numeric period-matched SEC guidance, then uses disclosed model assumptions for uncovered periods. Qualitative statements are not converted into numeric commitments. Quarterly period mapping is approximate for companies whose fiscal quarters differ from calendar quarters; review the reported period and source evidence.
- The current filing parser scans recent SEC 8-K/6-K exhibits for numeric guidance and discovers recent annual/quarterly filing references. It does not claim complete coverage of presentations, prepared remarks, transcripts, or guidance published only outside SEC filings.
- DCF and scoring outputs are rule-based illustrations, sensitive to assumptions, and not investment advice or a prediction of returns.
- Watchlist entries, manual portfolio positions, and theme preferences are stored as local JSON in the user's home directory. They are not committed to this repository, encrypted, or synced across machines; portfolio quantities and average costs are user-entered and quotes can be unavailable or delayed.
- Standard DCF forecasts revenue, margins, operating cash flow, and capital expenditure from available reports, period-matched company guidance, and explicit model assumptions; forecast FCF is operating cash flow less capital expenditure. If required inputs are missing, the DCF remains unavailable. Reported/provider cash and debt and diluted shares are used when available.
- Normalized FCF is estimated from median reported revenue multiplied by the difference between median operating-cash-flow margin and median capex/revenue, requiring at least three complete periods. Five years are preferred. Reported FCF history, its median reference, coverage, and peak/trough periods are shown, and the normalized starting FCF is editable.
- DCF scenarios are deterministic assumptions, not probability-weighted forecasts. Annual revenue growth, normalized-DCF FCF growth, WACC, terminal growth, operating margin, tax rate, and capex intensity can be edited. Missing inputs remain unavailable; a basic-share proxy is explicitly identified when diluted shares are unavailable.
- Industry EV/EBITDA references use selected industry peers rather than the permanent cross-sector benchmarks. For Micron, SK Hynix and Samsung Electronics are prioritized; Samsung's diversified business mix is noted. The current integration has no direct memory-price series.
- The DCF confidence score is separate from implied upside and includes historical FCF stability, scenario sensitivity, input completeness, cyclicality, normalized-FCF history, terminal-value dependence, and matched prior-guidance accuracy when enough data exists. Very high modeled upside triggers an assumption-review warning.
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
