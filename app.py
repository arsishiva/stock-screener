import streamlit as st
import yfinance as yf
import pandas as pd

# ---------------------------------------------------------
# 1. Webpage Configuration & Title
# ---------------------------------------------------------
st.set_page_config(page_title="Stock Screener Tool", layout="wide")
st.title("📈 Python Stock Screener")
st.write("Filter stocks by Country, Sector, Market Cap, P/E Ratio, RSI, and Moving Averages.")

# ---------------------------------------------------------
# 2. List of Tickers to Screen
# ---------------------------------------------------------
# A sample list of global stock tickers
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "JNJ",  # USA
    "VOLV-B.ST", "ERIC-B.ST", "AZN.ST", "INVE-B.ST", "SEB-A.ST",  # Sweden
    "SAP", "SIE.DE", "BMW.DE",  # Germany
    "7203.T", "6758.T"  # Japan
]


# ---------------------------------------------------------
# 3. Data Fetching & Technical Calculation Helper Function
# ---------------------------------------------------------
@st.cache_data(ttl=3600)  # Caches data for 1 hour so it loads fast
def get_stock_data(tickers):
    data = []

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period="1y")  # 1 year of daily prices for technicals

            if hist.empty or len(hist) < 200:
                continue

            # --- Technical Calculations ---
            # 200-Day Moving Average
            sma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            current_price = hist['Close'].iloc[-1]
            vs_sma200 = "Above" if current_price > sma200 else "Below"

            # Relative Strength Index (RSI 14)
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))

            # Store extracted information into a dictionary
            data.append({
                "Ticker": ticker,
                "Name": info.get("shortName", ticker),
                "Country": info.get("country", "Unknown"),
                "Sector": info.get("sector", "Unknown"),
                "Industry": info.get("industry", "Unknown"),
                "Market Cap ($B)": round(info.get("marketCap", 0) / 1e9, 2) if info.get("marketCap") else 0,
                "Price ($)": round(current_price, 2),
                "P/E Ratio": round(info.get("trailingPE", 0), 2) if info.get("trailingPE") else None,
                "RSI (14)": round(rsi, 1),
                "200 SMA": vs_sma200
            })
        except Exception as e:
            continue

    return pd.DataFrame(data)


# Fetch data with loading indicator
with st.spinner("Fetching stock data and calculating technical indicators..."):
    df = get_stock_data(TICKERS)

# ---------------------------------------------------------
# 4. Interactive Sidebar Filters
# ---------------------------------------------------------
st.sidebar.header("🔍 Screener Filters")

# Country Filter
all_countries = ["All"] + list(df["Country"].unique())
selected_country = st.sidebar.selectbox("Country", all_countries)

# Sector Filter
all_sectors = ["All"] + list(df["Sector"].unique())
selected_sector = st.sidebar.selectbox("Sector", all_sectors)

# Market Cap Filter
min_cap, max_cap = float(df["Market Cap ($B)"].min()), float(df["Market Cap ($B)"].max())
selected_cap = st.sidebar.slider("Minimum Market Cap ($B)", min_value=0.0, max_value=max_cap, value=0.0)

# Max P/E Ratio Filter
selected_pe = st.sidebar.slider("Maximum P/E Ratio", min_value=5.0, max_value=100.0, value=100.0)

# RSI Status Filter
rsi_filter = st.sidebar.selectbox("RSI (14) Status", ["Any", "Oversold (< 30)", "Neutral (30-70)", "Overbought (> 70)"])

# 200 SMA Filter
sma_filter = st.sidebar.selectbox("Position vs 200 SMA", ["Any", "Above", "Below"])

# ---------------------------------------------------------
# 5. Apply Filters to the Data
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
# 6. Display Results
# ---------------------------------------------------------
st.write(f"### Matching Results ({len(filtered_df)})")
st.dataframe(filtered_df, use_container_width=True)