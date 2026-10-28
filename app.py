import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# 1. Webpage Configuration & Title
# ---------------------------------------------------------
st.set_page_config(page_title="Advanced Pro Stock Screener", layout="wide")
st.title("📈 Professional Multi-Filter Stock Screener")
st.write("Real-time financial data with advanced market, price, fundamental, and technical filters.")

# ---------------------------------------------------------
# 2. Dynamic Ticker Universe
# ---------------------------------------------------------
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "JNJ", "V",
    "VOLV-B.ST", "ERIC-B.ST", "AZN.ST", "INVE-B.ST", "SEB-A.ST",
    "SAP.DE", "SIE.DE", "BMW.DE", "ADS.DE",
    "7203.T", "6758.T", "9984.T"
]


# ---------------------------------------------------------
# 3. Live Data Fetching & Advanced Metrics Engine
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_advanced_stock_data(tickers):
    data = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        status_text.text(f"Processing ticker: {ticker} ({i + 1}/{total})...")
        progress_bar.progress((i + 1) / total)

        try:
            stock = yf.Ticker(ticker)
            fast_info = stock.fast_info

            # Fetch historical data (1 year for technicals/performance)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 30:
                continue

            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            daily_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)

            # --- Performance Metrics ---
            perf_1w = round(((current_price - float(hist['Close'].iloc[-min(5, len(hist))])) / float(
                hist['Close'].iloc[-min(5, len(hist))])) * 100, 2)
            perf_1m = round(((current_price - float(hist['Close'].iloc[-min(21, len(hist))])) / float(
                hist['Close'].iloc[-min(21, len(hist))])) * 100, 2)
            perf_1y = round(((current_price - float(hist['Close'].iloc[0])) / float(hist['Close'].iloc[0])) * 100, 2)

            # --- 52-Week High / Low & Distance ---
            high_52w = float(hist['High'].max())
            low_52w = float(hist['Low'].min())
            dist_from_high = round(((current_price - high_52w) / high_52w) * 100, 2)
            dist_from_low = round(((current_price - low_52w) / low_52w) * 100, 2)

            # --- Volume & ATR ---
            avg_volume = int(hist['Volume'].mean()) if 'Volume' in hist else 0
            # Average True Range (ATR 14) proxy
            high_low = hist['High'] - hist['Low']
            atr_14 = round(float(high_low.rolling(window=14).mean().iloc[-1]), 2) if len(hist) >= 14 else 0.0

            # --- Market Cap Extraction & Categorization ---
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
            if not market_cap_raw:
                try:
                    market_cap_raw = stock.info.get("marketCap", 0)
                except:
                    pass

            market_cap_b = round(market_cap_raw / 1e9, 2) if market_cap_raw else 0.0

            # Market Cap Classification
            if market_cap_b >= 200:
                cap_category = "Mega-cap (> $200B)"
            elif market_cap_b >= 10:
                cap_category = "Large-cap ($10B - $200B)"
            elif market_cap_b >= 2:
                cap_category = "Mid-cap ($2B - $10B)"
            elif market_cap_b >= 0.3:
                cap_category = "Small-cap ($300M - $2B)"
            else:
                cap_category = "Micro-cap (< $300M)"

            # --- Fundamental Metrics (PE Ratio Fix) ---
            pe_ratio = None
            try:
                info_dict = stock.info
                pe_ratio = info_dict.get("trailingPE", None)
                if not pe_ratio:
                    pe_ratio = info_dict.get("forwardPE", None)
                # Fallback calculation if EPS is available
                if not pe_ratio and info_dict.get("trailingEps"):
                    eps = info_dict.get("trailingEps")
                    if eps > 0:
                        pe_ratio = current_price / eps
            except:
                pass
            pe_rounded = round(float(pe_ratio), 2) if pe_ratio and pe_ratio > 0 else None

            # --- Descriptive Info ---
            country = "Global / Unknown"
            sector = "Various"
            industry = "Various"
            exchange = "Unknown"
            currency = "USD"
            try:
                inf = stock.info
                country = inf.get("country", "Global / Unknown")
                sector = inf.get("sector", "Various")
                industry = inf.get("industry", "Various")
                exchange = inf.get("exchange", "Unknown")
                currency = inf.get("currency", "USD")
            except:
                pass

            # --- Technicals (RSI & 200 SMA & Beta) ---
            window_size = min(200, len(hist))
            sma200 = float(hist['Close'].rolling(window=window_size).mean().iloc[-1])
            vs_sma200 = "Above" if current_price > sma200 else "Below"

            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            rsi_val = round(float(rsi), 1) if not pd.isna(rsi) else 50.0

            beta = 1.0
            try:
                beta = float(stock.info.get("beta", 1.0))
            except:
                pass

            data.append({
                "Ticker": ticker,
                "Name": stock.info.get("shortName", ticker) if hasattr(stock, 'info') else ticker,
                "Country": country,
                "Exchange": exchange,
                "Sector": sector,
                "Industry": industry,
                "Currency": currency,
                "Market Cap ($B)": market_cap_b,
                "Cap Category": cap_category,
                "Price ($)": round(current_price, 2),
                "Daily Change %": daily_change_pct,
                "1W Return %": perf_1w,
                "1M Return %": perf_1m,
                "1Y Return %": perf_1y,
                "Distance from 52W High %": dist_from_high,
                "P/E Ratio": pe_rounded,
                "Beta": round(beta, 2),
                "ATR (14)": atr_14,
                "Average Volume": avg_volume,
                "RSI (14)": rsi_val,
                "200 SMA": vs_sma200
            })
        except Exception as e:
            continue

    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(data)


with st.spinner("Fetching live metrics and building security screening library..."):
    df = fetch_advanced_stock_data(TICKERS)

# ---------------------------------------------------------
# 4. Advanced Interactive Sidebar Filters (Categories A & B)
# ---------------------------------------------------------
st.sidebar.header("🔍 Screener Filter Library")

if df.empty:
    st.error("No data retrieved. Please check your network connection.")
else:
    # --- SECTION A: Security Information & Market Selection ---
    st.sidebar.subheader("A. Market & Security Info")

    countries = ["All"] + sorted(list(df["Country"].dropna().unique()))
    sel_country = st.sidebar.selectbox("Country / Market", countries)

    exchanges = ["All"] + sorted(list(df["Exchange"].dropna().unique()))
    sel_exchange = st.sidebar.selectbox("Exchange", exchanges)

    sectors = ["All"] + sorted(list(df["Sector"].dropna().unique()))
    sel_sector = st.sidebar.selectbox("Sector", sectors)

    industries = ["All"] + sorted(list(df["Industry"].dropna().unique()))
    sel_industry = st.sidebar.selectbox("Industry / Sub-industry", industries)

    cap_categories = ["All"] + sorted(list(df["Cap Category"].dropna().unique()))
    sel_cap_cat = st.sidebar.selectbox("Market Capitalization Size", cap_categories)

    currencies = ["All"] + sorted(list(df["Currency"].dropna().unique()))
    sel_currency = st.sidebar.selectbox("Trading Currency", currencies)

    # --- SECTION B: Price, Market Cap & Trading Activity ---
    st.sidebar.subheader("B. Price & Trading Activity")

    valid_cap = df[df["Market Cap ($B)"] > 0]
    min_c = float(valid_cap["Market Cap ($B)"].min()) if not valid_cap.empty else 0.0
    max_c = float(valid_cap["Market Cap ($B)"].max()) if not valid_cap.empty else 100.0
    if min_c >= max_c: max_c = min_c + 1.0
    sel_min_marketcap = st.sidebar.slider("Min Market Cap ($B)", min_value=min_c, max_value=max_c, value=min_c)

    sel_max_pe = st.sidebar.slider("Maximum P/E Ratio", min_value=5.0, max_value=100.0, value=100.0)

    sel_min_daily_change = st.sidebar.slider("Min Daily Change (%)", min_value=-15.0, max_value=15.0, value=-15.0)

    max_dist_high = st.sidebar.slider("Max Distance from 52W High (%)", min_value=-50.0, max_value=0.0, value=0.0)

    sel_max_beta = st.sidebar.slider("Max Beta (Volatility Sensitivity)", min_value=0.2, max_value=3.0, value=3.0)

    # Technicals quick toggles
    st.sidebar.subheader("C. Technical Filters")
    rsi_filter = st.sidebar.selectbox("RSI (14) Status",
                                      ["Any", "Oversold (< 30)", "Neutral (30-70)", "Overbought (> 70)"])
    sma_filter = st.sidebar.selectbox("Price vs 200 SMA", ["Any", "Above", "Below"])

    # ---------------------------------------------------------
    # 5. Apply All Filters Dynamically
    # ---------------------------------------------------------
    f_df = df.copy()

    if sel_country != "All": f_df = f_df[f_df["Country"] == sel_country]
    if sel_exchange != "All": f_df = f_df[f_df["Exchange"] == sel_exchange]
    if sel_sector != "All": f_df = f_df[f_df["Sector"] == sel_sector]
    if sel_industry != "All": f_df = f_df[f_df["Industry"] == sel_industry]
    if sel_cap_cat != "All": f_df = f_df[f_df["Cap Category"] == sel_cap_cat]
    if sel_currency != "All": f_df = f_df[f_df["Currency"] == sel_currency]

    f_df = f_df[f_df["Market Cap ($B)"] >= sel_min_marketcap]

    if sel_max_pe < 100:
        f_df = f_df[f_df["P/E Ratio"].notnull() & (f_df["P/E Ratio"] <= sel_max_pe)]

    f_df = f_df[f_df["Daily Change %"] >= sel_min_daily_change]
    f_df = f_df[f_df["Distance from 52W High %"] >= max_dist_high]
    f_df = f_df[f_df["Beta"] <= sel_max_beta]

    if rsi_filter == "Oversold (< 30)":
        f_df = f_df[f_df["RSI (14)"] < 30]
    elif rsi_filter == "Neutral (30-70)":
        f_df = f_df[(f_df["RSI (14)"] >= 30) & (f_df["RSI (14)"] <= 70)]
    elif rsi_filter == "Overbought (> 70)":
        f_df = f_df[f_df["RSI (14)"] > 70]

    if sma_filter != "Any":
        f_df = f_df[f_df["200 SMA"] == sma_filter]

    # ---------------------------------------------------------
    # 6. Display Results Table & Export
    # ---------------------------------------------------------
    st.write(f"### Matching Results ({len(f_df)} stocks found)")
    st.dataframe(f_df, use_container_width=True)

    csv_data = f_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Screened Results as CSV",
        data=csv_data,
        file_name="advanced_stock_screener.csv",
        mime="text/csv",
    )