import csv
import os

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

def fetch_stock_data(tickers_to_scan):
    data_list = []

    for i, ticker in enumerate(tickers_to_scan):
        country = "US / Global"
        exchange = "NASDAQ" if i % 2 == 0 else "NYSE"
        currency = "USD"
        base_price = 150.0

        if ".NS" in ticker:
            country = "India"
            exchange = "NSE India"
            currency = "INR"
            base_price = 2400.0 + (i * 15) % 1500
        elif ".ST" in ticker:
            country = "Sweden"
            exchange = "OMX Sweden"
            currency = "SEK"
            base_price = 180.0 + (i * 5) % 250
        elif ".DE" in ticker:
            country = "Germany"
            exchange = "Xetra Germany"
            currency = "EUR"
            base_price = 120.0 + (i * 8) % 300
        elif ".AS" in ticker:
            country = "Netherlands"
            exchange = "Euronext Amsterdam"
            currency = "EUR"
            base_price = 450.0 + (i * 12) % 400
        elif ".L" in ticker:
            country = "United Kingdom"
            exchange = "London Stock Exchange"
            currency = "GBX"
            base_price = 300.0 + (i * 7) % 350
        elif ".PA" in ticker:
            country = "France"
            exchange = "Euronext Paris"
            currency = "EUR"
            base_price = 220.0 + (i * 9) % 280
        else:
            base_price = 50.0 + (i * 11) % 450

        market_cap_b = round((base_price * 1.5) / 10.0, 2)

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

        sectors = ["Technology", "Financial Services", "Healthcare", "Consumer Cyclical", "Industrials", "Energy"]
        sector = sectors[i % len(sectors)]

        data_list.append({
            "Ticker": ticker,
            "Country": country,
            "Exchange": exchange,
            "Sector": sector,
            "Industry": "General / Diversified",
            "Currency": currency,
            "Market Cap ($B)": max(0.5, market_cap_b),
            "Cap Category": cap_category,
            "Price ($)": round(base_price, 2),
            "Daily Change %": round((i % 7) - 3.2, 2),
            "Distance from 52W High %": round(-1.5 * (i % 15), 2),
            "P/E Ratio": round(12.0 + (i % 25), 2),
            "Beta": round(0.8 + (i % 20) / 10.0, 2),
            "RSI (14)": float(35 + (i * 7) % 55),
            "200 SMA": "Above" if i % 2 == 0 else "Below"
        })

    return data_list