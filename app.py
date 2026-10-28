import streamlit as st
import yfinance as yf
import csv
import os

# ---------------------------------------------------------
# 1. Webpage Configuration
# ---------------------------------------------------------
st.set_page_config(page_title="Global Pure Python Stock Screener", layout="wide")
st.title("📈 Global Stock Screener (Pure Python / No Pandas)")
st.write("Screening thousands of international tickers dynamically without external compiled libraries.")


# ---------------------------------------------------------
# 2. Load Tickers from CSV using Built-in Python
# ---------------------------------------------------------
@st.cache_data
def load_ticker_universe():
    tickers = []
    if os.path.exists("tickers.csv"):
        with open("tickers.csv", mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "ticker" in row:
                    tickers.append(row["ticker"])
    else:
        tickers = ["AAPL", "MSFT", "RELIANCE.NS", "VOLV-B.ST", "SAP.DE"]
    return tickers


ALL_TICKERS = load_ticker_universe()

# Sidebar performance slider to control how many stocks to scan
st.sidebar.header("⚙️ Performance Control")
max_stocks = st.sidebar.slider(
    "Max Stocks to Scan Live",
    min_value=20,
    max_value=min(2000, len(ALL_TICKERS)),
    value=100,
    step=20,
    help="Select how many global stocks to load live into the screener."
)

TICKERS_TO_SCAN = ALL_TICKERS[:max_stocks]


# ---------------------------------------------------------
# 3. Live Data Fetching Engine (Pure Python)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_stock_data_pure_python(tickers):
    data_list = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        status_text.text(f"Fetching live data ({i + 1}/{total}): {ticker}...")
        progress_bar.progress((i + 1) / total)

        try:
            stock = yf.Ticker(ticker)
            fast_info = stock.fast_info
            hist = stock.history(period="3mo")

            if hist.empty or len(hist) < 10:
                continue

            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            daily_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)

            # Market Cap
            market_cap_raw = 0
            try:
                market_cap_raw = fast_info.market_cap
            except:
                pass
            if not market_cap_raw:
                try:
                    market_cap_raw = current_price * fast_info.shares
                except:
                    pass

            market_cap_b = round(market_cap_raw / 1e9, 2) if market_cap_raw else 0.0

            # P/E Ratio
            pe_ratio = None
            try:
                info = stock.info
                pe_ratio = info.get("trailingPE", None)
            except:
                pass
            pe_rounded = round(float(pe_ratio), 2) if pe_ratio and pe_ratio > 0 else 0.0

            # Country categorization based on ticker suffix
            country = "US / Global"
            if ".NS" in ticker:
                country = "India"
            elif ".ST" in ticker:
                country = "Sweden"
            elif ".DE" in ticker:
                country = "Germany"
            elif ".PA" in ticker:
                country = "France"
            elif ".L" in ticker:
                country = "United Kingdom"

            data_list.append({
                "Ticker": ticker,
                "Country": country,
                "Market Cap ($B)": market_cap_b,
                "Price ($)": round(current_price, 2),
                "Daily Change %": daily_change_pct,
                "P/E Ratio": pe_rounded
            })
        except:
            continue

    progress_bar.empty()
    status_text.empty()
    return data_list


with st.spinner(f"Loading live data for {len(TICKERS_TO_SCAN)} global stocks..."):
    stocks_data = fetch_stock_data_pure_python(TICKERS_TO_SCAN)

# ---------------------------------------------------------
# 4. Filters & Display
# ---------------------------------------------------------
st.sidebar.header("🔍 Screener Filters")

if not stocks_data:
    st.error("No stock data could be loaded.")
else:
    # Extract unique countries for filter
    countries = ["All"] + sorted(list(set(item["Country"] for item in stocks_data)))
    sel_country = st.sidebar.selectbox("Country / Market", countries)

    # Filter data using pure Python list comprehension
    filtered_data = stocks_data
    if sel_country != "All":
        filtered_data = [item for item in stocks_data if item["Country"] == sel_country]

    st.write(f"### Matching Results ({len(filtered_data)} stocks displayed)")
    st.dataframe(filtered_data, use_container_width=True)