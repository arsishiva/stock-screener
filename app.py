import streamlit as st
import yfinance as yf
import pandas as pd

# ---------------------------------------------------------
# 1. Webpage Configuration & Title
# ---------------------------------------------------------
st.set_page_config(page_title="Live Stock Screener Tool", layout="wide")
st.title("📈 Real-Time Python Stock Screener")
st.write("Fetching live market data, statistics, and technical metrics dynamically from Yahoo Finance.")

# ---------------------------------------------------------
# 2. Dynamic Ticker List (Real Global Stocks)
# ---------------------------------------------------------
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "JNJ", "V",
    "VOLV-B.ST", "ERIC-B.ST", "AZN.ST", "INVE-B.ST", "SEB-A.ST",  # Sweden (OMX)
    "SAP.DE", "SIE.DE", "BMW.DE", "ADS.DE",  # Germany (Xetra)
    "7203.T", "6758.T", "9984.T"  # Japan (Tokyo)
]


# ---------------------------------------------------------
# 3. Live Data Fetching & Technical Metrics Calculation
# ---------------------------------------------------------
@st.cache_data(ttl=3600)  # Cache results for 1 hour
def fetch_live_stock_data(tickers):
    data = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(tickers)
    for i, ticker in enumerate(tickers):
        status_text.text(f"Fetching live data for: {ticker} ({i + 1}/{total})...")
        progress_bar.progress((i + 1) / total)

        try:
            stock = yf.Ticker(ticker)
            fast_info = stock.fast_info  # Reliable fast metadata dictionary

            # Fetch 1 year of historical daily data for technical calculations
            hist = stock.history(period="1y")

            if hist.empty or len(hist) < 50:
                continue

            current_price = float(hist['Close'].iloc[-1])

            # --- Robust Market Cap Extraction ---
            # Try fast_info first, then calculate manually (Price * Shares), then fallback to info dictionary
            market_cap_raw = 0
            try:
                market_cap_raw = fast_info.market_cap
            except:
                pass

            if not market_cap_raw or market_cap_raw == 0:
                try:
                    shares = fast_info.shares
                    market_cap_raw = current_price * shares
                except:
                    pass

            if not market_cap_raw or market_cap_raw == 0:
                try:
                    info = stock.info
                    market_cap_raw = info.get("marketCap", 0)
                except:
                    pass

            market_cap_b = round(market_cap_raw / 1e9, 2) if market_cap_raw else 0.0

            # --- Technical Calculations ---
            window_size = min(200, len(hist))
            sma200 = float(hist['Close'].rolling(window=window_size).mean().iloc[-1])
            vs_sma200 = "Above" if current_price > sma200 else "Below"

            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            rsi_val = round(float(rsi), 1) if not pd.isna(rsi) else 50.0

            # P/E Ratio extraction with safe handling
            pe_rounded = None
            try:
                info_dict = stock.info
                pe_ratio = info_dict.get("trailingPE", None)
                if pe_ratio:
                    pe_rounded = round(float(pe_ratio), 2)
            except:
                pass

            # Country & Sector fallbacks
            country_name = "Global / Unknown"
            sector_name = "Various"
            try:
                inf = stock.info
                country_name = inf.get("country", "Global / Unknown")
                sector_name = inf.get("sector", "Various")
            except:
                pass

            data.append({
                "Ticker": ticker,
                "Name": ticker,
                "Country": country_name,
                "Sector": sector_name,
                "Market Cap ($B)": market_cap_b,
                "Price ($)": round(current_price, 2),
                "P/E Ratio": pe_rounded,
                "RSI (14)": rsi_val,
                "200 SMA": vs_sma200
            })
        except Exception as e:
            continue

    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(data)


# Load data into DataFrame
with st.spinner("Connecting to Yahoo Finance API to pull live market statistics..."):
    df = fetch_live_stock_data(TICKERS)

# ---------------------------------------------------------
# 4. Interactive Sidebar Filters
# ---------------------------------------------------------
st.sidebar.header("🔍 Screener Filters")

if df.empty:
    st.error("Could not retrieve live data. Please check your internet connection and try refreshing.")
else:
    # Country Filter
    all_countries = ["All"] + sorted(list(df["Country"].dropna().unique()))
    selected_country = st.sidebar.selectbox("Country", all_countries)

    # Sector Filter
    all_sectors = ["All"] + sorted(list(df["Sector"].dropna().unique()))
    selected_sector = st.sidebar.selectbox("Sector", all_sectors)

    # Market Cap Filter Slider (Filtered safely to exclude 0-values if any remain)
    valid_cap_df = df[df["Market Cap ($B)"] > 0]
    min_market_cap = float(valid_cap_df["Market Cap ($B)"].min()) if not valid_cap_df.empty else 0.0
    max_market_cap = float(valid_cap_df["Market Cap ($B)"].max()) if not valid_cap_df.empty else 100.0

    if min_market_cap >= max_market_cap:
        max_market_cap = min_market_cap + 1.0

    selected_cap = st.sidebar.slider("Minimum Market Cap ($B)", min_value=min_market_cap, max_value=max_market_cap,
                                     value=min_market_cap)

    # Max P/E Ratio Slider
    selected_pe = st.sidebar.slider("Maximum P/E Ratio", min_value=5.0, max_value=100.0, value=100.0)

    # RSI Status Filter
    rsi_filter = st.sidebar.selectbox("RSI (14) Status",
                                      ["Any", "Oversold (< 30)", "Neutral (30-70)", "Overbought (> 70)"])

    # 200 SMA Filter
    sma_filter = st.sidebar.selectbox("Position vs 200 SMA", ["Any", "Above", "Below"])

    # ---------------------------------------------------------
    # 5. Apply Filters Dynamically
    # ---------------------------------------------------------
    filtered_df = df.copy()

    if selected_country != "All":
        filtered_df = filtered_df[filtered_df["Country"] == selected_country]

    if selected_sector != "All":
        filtered_df = filtered_df[filtered_df["Sector"] == selected_sector]

    filtered_df = filtered_df[filtered_df["Market Cap ($B)"] >= selected_cap]

    if selected_pe < 100:
        filtered_df = filtered_df[filtered_df["P/E Ratio"].notnull() & (filtered_df["P/E Ratio"] <= selected_pe)]

    if rsi_filter == "Oversold (< 30)":
        filtered_df = filtered_df[filtered_df["RSI (14)"] < 30]
    elif rsi_filter == "Neutral (30-70)":
        filtered_df = filtered_df[(filtered_df["RSI (14)"] >= 30) & (filtered_df["RSI (14)"] <= 70)]
    elif rsi_filter == "Overbought (> 70)":
        filtered_df = filtered_df[filtered_df["RSI (14)"] > 70]

    if sma_filter != "Any":
        filtered_df = filtered_df[filtered_df["200 SMA"] == sma_filter]

    # ---------------------------------------------------------
    # 6. Display Live Results Table
    # ---------------------------------------------------------
    st.write(f"### Live Results Matching Criteria ({len(filtered_df)} stocks found)")
    st.dataframe(filtered_df, use_container_width=True)

    # Download option for results
    csv_data = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Filtered Results as CSV",
        data=csv_data,
        file_name="live_stock_screener_results.csv",
        mime="text/csv",
    )