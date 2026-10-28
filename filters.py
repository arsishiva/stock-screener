import streamlit as st


def render_sidebar_filters(stocks_data):
    st.sidebar.header("🔍 Screener Filter Library")

    # --- Pre-populated Master Global Markets & Exchanges ---
    MASTER_COUNTRIES = [
        "All", "US / Global", "India", "Sweden", "Germany",
        "United Kingdom", "France", "Netherlands", "Switzerland"
    ]

    MASTER_EXCHANGES = [
        "All", "NASDAQ", "NYSE", "AMEX", "NSE India",
        "OMX Sweden", "Xetra Germany", "London Stock Exchange",
        "Euronext Paris", "Euronext Amsterdam", "SIX Swiss Exchange"
    ]

    MASTER_SECTORS = [
        "All", "Technology", "Financial Services", "Healthcare",
        "Consumer Cyclical", "Consumer Defensive", "Industrials",
        "Energy", "Utilities", "Basic Materials", "Real Estate", "Communication Services"
    ]

    # Dynamically merge master lists with any incoming fetched data values
    fetched_countries = list(set(item["Country"] for item in stocks_data)) if stocks_data else []
    fetched_exchanges = list(set(item["Exchange"] for item in stocks_data)) if stocks_data else []
    fetched_sectors = list(set(item["Sector"] for item in stocks_data)) if stocks_data else []

    all_countries = sorted(list(set(MASTER_COUNTRIES + fetched_countries)))
    all_exchanges = sorted(list(set(MASTER_EXCHANGES + fetched_exchanges)))
    all_sectors = sorted(list(set(MASTER_SECTORS + fetched_sectors)))

    # --- A. Market & Security Info ---
    st.sidebar.subheader("A. Market & Security Info")
    sel_country = st.sidebar.selectbox("Country / Market", all_countries)
    sel_exchange = st.sidebar.selectbox("Exchange", all_exchanges)
    sel_sector = st.sidebar.selectbox("Sector", all_sectors)

    industries = ["All"] + sorted(list(set(item["Industry"] for item in stocks_data))) if stocks_data else ["All"]
    sel_industry = st.sidebar.selectbox("Industry / Sub-industry", industries)

    cap_categories = ["All", "Mega-cap (> $200B)", "Large-cap ($10B - $200B)", "Mid-cap ($2B - $10B)",
                      "Small-cap ($300M - $2B)", "Micro-cap (< $300M)"]
    sel_cap_cat = st.sidebar.selectbox("Market Capitalization Size", cap_categories)

    currencies = ["All", "USD", "INR", "EUR", "GBP", "SEK"]
    sel_currency = st.sidebar.selectbox("Trading Currency", currencies)

    # --- B. Price & Trading Activity ---
    st.sidebar.subheader("B. Price & Trading Activity")
    sel_min_marketcap = st.sidebar.slider("Min Market Cap ($B)", min_value=0.0, max_value=2000.0, value=0.0)
    sel_max_pe = st.sidebar.slider("Maximum P/E Ratio", min_value=5.0, max_value=100.0, value=100.0)
    sel_min_daily_change = st.sidebar.slider("Min Daily Change (%)", min_value=-50.0, max_value=50.0, value=-50.0)
    max_dist_high = st.sidebar.slider("Max Distance from 52W High (%)", min_value=-100.0, max_value=0.0, value=-100.0)
    sel_max_beta = st.sidebar.slider("Max Beta (Volatility Sensitivity)", min_value=0.2, max_value=5.0, value=5.0)

    # --- C. Technical Filters ---
    st.sidebar.subheader("C. Technical Filters")
    rsi_filter = st.sidebar.selectbox("RSI (14) Status",
                                      ["Any", "Oversold (< 30)", "Neutral (30-70)", "Overbought (> 70)"])
    sma_filter = st.sidebar.selectbox("Price vs 200 SMA", ["Any", "Above", "Below"])

    # --- Apply Filtering Logic ---
    filtered = stocks_data if stocks_data else []
    if sel_country != "All":
        filtered = [i for i in filtered if i.get("Country") == sel_country]
    if sel_exchange != "All":
        filtered = [i for i in filtered if sel_exchange.lower() in i.get("Exchange", "").lower()]
    if sel_sector != "All":
        filtered = [i for i in filtered if i.get("Sector") == sel_sector]
    if sel_industry != "All":
        filtered = [i for i in filtered if i.get("Industry") == sel_industry]
    if sel_cap_cat != "All":
        filtered = [i for i in filtered if i.get("Cap Category") == sel_cap_cat]
    if sel_currency != "All":
        filtered = [i for i in filtered if i.get("Currency") == sel_currency]

    filtered = [i for i in filtered if i.get("Market Cap ($B)", 0) >= sel_min_marketcap]
    if sel_max_pe < 100:
        filtered = [i for i in filtered if 0 < i.get("P/E Ratio", 0) <= sel_max_pe]
    filtered = [i for i in filtered if i.get("Daily Change %", 0) >= sel_min_daily_change]
    filtered = [i for i in filtered if i.get("Distance from 52W High %", 0) >= max_dist_high]
    filtered = [i for i in filtered if i.get("Beta", 1.0) <= sel_max_beta]

    if rsi_filter == "Oversold (< 30)":
        filtered = [i for i in filtered if i.get("RSI (14)", 50) < 30]
    elif rsi_filter == "Neutral (30-70)":
        filtered = [i for i in filtered if 30 <= i.get("RSI (14)", 50) <= 70]
    elif rsi_filter == "Overbought (> 70)":
        filtered = [i for i in filtered if i.get("RSI (14)", 50) > 70]

    if sma_filter != "Any":
        filtered = [i for i in filtered if i.get("200 SMA") == sma_filter]

    return filtered