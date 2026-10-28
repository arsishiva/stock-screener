import urllib.request
import json
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
    headers = {'User-Agent': 'Mozilla/5.0'}

    for ticker in tickers_to_scan:
        try:
            # 1. Fetch quote summary from Yahoo Finance public JSON API
            url_quote = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}"
            req = urllib.request.Request(url_quote, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode('utf-8'))
                quote_res = result.get("quoteResponse", {}).get("result", [])

                if not quote_res:
                    continue
                q = quote_res[0]

            current_price = float(q.get("regularMarketPrice", q.get("regularMarketPreviousClose", 0)))
            if not current_price or current_price <= 0:
                continue

            prev_close = float(q.get("regularMarketPreviousClose", current_price))
            daily_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

            # Market Cap
            market_cap_raw = q.get("marketCap", 0)
            market_cap_b = round(market_cap_raw / 1e9, 2) if market_cap_raw else 0.0

            # Cap Category
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

            # Fundamentals & Info
            pe_ratio = q.get("trailingPE", 0.0)
            pe_rounded = round(float(pe_ratio), 2) if pe_ratio and pe_ratio > 0 else 0.0

            sector = q.get("sector", "Various")
            industry = q.get("industry", "Various")
            exchange = q.get("exchange", "Unknown")
            currency = q.get("currency", "USD")
            beta = float(q.get("beta", 1.0) or 1.0)
            high_52w = float(q.get("fiftyTwoWeekHigh", current_price) or current_price)

            dist_from_high = round(((current_price - high_52w) / high_52w) * 100, 2) if high_52w else 0.0

            # Country categorization
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
            elif ".AS" in ticker:
                country = "Netherlands"

            # Dummy/Proxy technical placeholders (fully pure Python)
            rsi_val = 50.0
            vs_sma200 = "Above" if current_price >= prev_close else "Below"

            data_list.append({
                "Ticker": ticker,
                "Country": country,
                "Exchange": exchange,
                "Sector": sector,
                "Industry": industry,
                "Currency": currency,
                "Market Cap ($B)": market_cap_b,
                "Cap Category": cap_category,
                "Price ($)": round(current_price, 2),
                "Daily Change %": daily_change_pct,
                "Distance from 52W High %": dist_from_high,
                "P/E Ratio": pe_rounded,
                "Beta": round(beta, 2),
                "RSI (14)": rsi_val,
                "200 SMA": vs_sma200
            })
        except Exception as e:
            continue

    return data_list