import yfinance as yf
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

    for ticker in tickers_to_scan:
        try:
            stock = yf.Ticker(ticker)
            fast_info = stock.fast_info
            hist = stock.history(period="3mo")

            if hist.empty or len(hist) < 10:
                continue

            current_price = float(hist['Close'].iloc[-1])
            prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            daily_change_pct = round(((current_price - prev_close) / prev_close) * 100, 2)

            # 52-Week High Distance
            high_52w = float(hist['High'].max()) if 'High' in hist else current_price
            dist_from_high = round(((current_price - high_52w) / high_52w) * 100, 2)

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
            pe_ratio = None
            sector = "Various"
            industry = "Various"
            exchange = "Unknown"
            currency = "USD"
            beta = 1.0
            try:
                info = stock.info
                pe_ratio = info.get("trailingPE", None)
                sector = info.get("sector", "Various")
                industry = info.get("industry", "Various")
                exchange = info.get("exchange", "Unknown")
                currency = info.get("currency", "USD")
                beta = float(info.get("beta", 1.0))
            except:
                pass
            pe_rounded = round(float(pe_ratio), 2) if pe_ratio and pe_ratio > 0 else 0.0

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

            # Technicals (RSI & 200 SMA)
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            rsi_val = round(float(rsi), 1) if not str(rsi).lower() == 'nan' else 50.0

            window_size = min(200, len(hist))
            sma200 = float(hist['Close'].rolling(window=window_size).mean().iloc[-1])
            vs_sma200 = "Above" if current_price > sma200 else "Below"

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
        except:
            continue
    return data_list