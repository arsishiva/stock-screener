import streamlit as st


def render_sidebar_filters(stocks_data):
    st.sidebar.header("🔍 Screener Filter Library")

    # --- A. Market & Security Info ---
    st.sidebar.subheader("A. Market & Security Info")
    countries = ["All"] + sorted(list(set(item["Country"] for item in stocks_data)))
    sel_country = st.sidebar.selectbox("Country / Market", countries)

    exchanges = ["All"] + sorted(list(set(item["Exchange"] for item in stocks_data)))
    sel_exchange = st.sidebar.selectbox("Exchange", exchanges)

    sectors = ["All"] + sorted(list(set(item["Sector"] for item in stocks_data)))
    sel_sector = st.sidebar.selectbox("Sector", sectors)

    industries = ["All"] + sorted(list(set(item["Industry"] for item in stocks_data)))
    sel_industry = st.sidebar.selectbox("Industry / Sub-industry", industries)

    cap_categories = ["All"] + sorted(list(set(item["Cap Category"] for item in stocks_data)))
    sel_cap_cat = st.sidebar.selectbox("Market Capitalization Size", cap_categories)

    currencies = ["All"] + sorted(list(set(item["Currency"] for item in stocks_data)))
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
    filtered = stocks_data
    if sel_country != "All": filtered = [i for i in filtered if i["Country"] == sel_country]
    if sel_exchange != "All": filtered = [i for i in filtered if i["Exchange"] == sel_exchange]
    if sel_sector != "All": filtered = [i for i in filtered if i["Sector"] == sel_sector]
    if sel_industry != "All": filtered = [i for i in filtered if i["Industry"] == sel_industry]
    if sel_cap_cat != "All": filtered = [i for i in filtered if i["Cap Category"] == sel_cap_cat]
    if sel_currency != "All": filtered = [i for i in filtered if i["Currency"] == sel_currency]

    filtered = [i for i in filtered if i["Market Cap ($B)"] >= sel_min_marketcap]
    if sel_max_pe < 100:
        filtered = [i for i in filtered if i["P/E Ratio"] > 0 and i["P/E Ratio"] <= sel_max_pe]
    filtered = [i for i in filtered if i["Daily Change %"] >= sel_min_daily_change]
    filtered = [i for i in filtered if i["Distance from 52W High %"] >= max_dist_high]
    filtered = [i for i in filtered if i["Beta"] <= sel_max_beta]

    if rsi_filter == "Oversold (< 30)":
        filtered = [i for i in filtered if i["RSI (14)"] < 30]
    elif rsi_filter == "Neutral (30-70)":
        filtered = [i for i in filtered if 30 <= i["RSI (14)"] <= 70]
    elif rsi_filter == "Overbought (> 70)":
        filtered = [i for i in filtered if i["RSI (14)"] > 70]

    if sma_filter != "Any":
        filtered = [i for i in filtered if i["200 SMA"] == sma_filter]

    return filtered