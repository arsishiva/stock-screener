import streamlit as st
from data_loader import load_ticker_universe, fetch_stock_data
from filters import render_sidebar_filters

# 1. Webpage Config
st.set_page_config(page_title="Global Pure-Python Stock Screener", layout="wide")
st.title("📈 Global Stock Screener (Pure Python / No Pandas)")
st.write(
    "Scanning international tickers across US, India, UK, Sweden, Germany, Netherlands, and France safely without compiled binaries.")

# 2. Load Tickers & Performance Control
all_tickers = load_ticker_universe()

st.sidebar.header("⚙️ Performance Control")
max_stocks = st.sidebar.slider(
    "Max Stocks to Scan Live",
    min_value=50,
    max_value=min(3000, len(all_tickers)),
    value=500,  # Increased default scan depth to capture all global markets
    step=50,
    help="Select how many global stocks to load live into the screener."
)

tickers_to_scan = all_tickers[:max_stocks]


# 3. Fetch Data (Cached)
@st.cache_data(ttl=3600)
def get_cached_data(tickers):
    return fetch_stock_data(tickers)


with st.spinner(f"Loading live data for {len(tickers_to_scan)} global stocks..."):
    stocks_data = get_cached_data(tickers_to_scan)

# 4. Render Filters & Results
if not stocks_data:
    st.error("No stock data could be loaded. Try increasing the scan slider or check your internet connection.")
else:
    filtered_results = render_sidebar_filters(stocks_data)

    st.write(f"### Matching Results ({len(filtered_results)} stocks displayed)")
    if filtered_results:
        # st.table works directly with pure Python list of dicts (no pandas dependency)
        st.table(filtered_results)
    else:
        st.warning("No stocks matched the selected filter criteria. Try setting Country and Exchange to 'All'.")