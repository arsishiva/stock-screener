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
    value=500,
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

# 4. Render Filters & Results using Pure Python HTML (Zero Pandas Dependency)
if not stocks_data:
    st.error("No stock data could be loaded. Try increasing the scan slider or check your internet connection.")
else:
    filtered_results = render_sidebar_filters(stocks_data)

    st.write(f"### Matching Results ({len(filtered_results)} stocks displayed)")

    if filtered_results:
        # Build a pure HTML table to avoid Streamlit/Pandas internal dependencies
        headers = list(filtered_results[0].keys())
        html_code = "<div style='overflow-x: auto;'><table style='width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px;'>"
        html_code += "<tr style='background-color: #262730; color: white; text-align: left;'>"
        for h in headers:
            html_code += f"<th style='padding: 8px; border: 1px solid #444;'>{h}</th>"
        html_code += "</tr>"

        for row in filtered_results:
            html_code += "<tr style='border-bottom: 1px solid #ddd;'>"
            for h in headers:
                val = row.get(h, "")
                html_code += f"<td style='padding: 8px; border: 1px solid #ddd;'>{val}</td>"
            html_code += "</tr>"
        html_code += "</table></div>"

        st.markdown(html_code, unsafe_allow_html=True)
    else:
        st.warning("No stocks matched the selected filter criteria. Try setting Country and Exchange to 'All'.")