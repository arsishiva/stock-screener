import csv
from pathlib import Path

TICKER_FILE = Path(__file__).resolve().parents[2] / "data" / "tickers.csv"


def load_ticker_universe():
    tickers = []
    if TICKER_FILE.exists():
        with TICKER_FILE.open(mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "ticker" in row:
                    tickers.append(row["ticker"])

    if not tickers:
        tickers = ["AAPL", "MSFT", "RELIANCE.NS", "VOLV-B.ST", "SAP.DE", "ASML.AS", "SHEL.L", "TTE.PA"]

    us_stocks = [t for t in tickers if "." not in t]
    global_stocks = [t for t in tickers if "." in t]

    interleaved = []
    max_len = max(len(us_stocks), len(global_stocks))
    for i in range(max_len):
        if i < len(us_stocks):
            interleaved.append(us_stocks[i])
        if i < len(global_stocks):
            interleaved.append(global_stocks[i])

    return interleaved


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

        # Valuation calculations simulation
        pe_ratio = round(10.0 + (i * 3.5) % 40, 2)
        fwd_pe = round(pe_ratio * 0.85, 2)
        trailing_pe = round(pe_ratio * 1.1, 2)
        peg_ratio = round(pe_ratio / (8.0 + (i % 10)), 2)
        pegy_ratio = round(peg_ratio * 0.9, 2)
        ps_ratio = round(1.5 + (i % 8), 2)
        fwd_ps = round(ps_ratio * 0.9, 2)
        pb_ratio = round(1.2 + (i % 6), 2)
        ptb_ratio = round(pb_ratio * 1.1, 2)
        p_cf = round(8.0 + (i % 12), 2)
        p_fcf = round(12.0 + (i % 15), 2)
        ev_ebitda = round(7.0 + (i % 14), 2)
        ev_ebit = round(9.0 + (i % 16), 2)
        ev_rev = round(2.0 + (i % 5), 2)
        ev_fcf = round(14.0 + (i % 18), 2)
        earnings_yield = round((1 / pe_ratio) * 100, 2)
        fcf_yield = round((1 / p_fcf) * 100, 2)
        bvps = round(base_price / pb_ratio, 2)
        graham_num = round((22.5 * bvps * (base_price / pe_ratio)) ** 0.5, 2) if pe_ratio > 0 else 10.0
        fair_value_discount = round(((base_price - (base_price * 0.9)) / (base_price * 0.9)) * 100, 2)
        pe_percentile = round(20.0 + (i * 4) % 75, 1)
        ev_ebitda_percentile = round(25.0 + (i * 5) % 70, 1)
        peer_discount = round(-15.0 + (i % 30), 1)

        data_list.append({
            "Ticker": ticker,
            "Country": country,
            "Exchange": exchange,
            "Sector": sector,
            "Industry": "General / Diversified",
            "Currency": currency,
            "Price ($)": round(base_price, 2),
            "Market Cap ($B)": max(0.5, market_cap_b),
            "Cap Category": cap_category,
            "P/E Ratio": pe_ratio,
            "Forward P/E": fwd_pe,
            "Trailing P/E": trailing_pe,
            "PEG Ratio": peg_ratio,
            "PEGY Ratio": pegy_ratio,
            "P/S": ps_ratio,
            "Forward P/S": fwd_ps,
            "P/B": pb_ratio,
            "Price-to-Tangible-Book": ptb_ratio,
            "Price-to-Cash-Flow": p_cf,
            "Price-to-FCF": p_fcf,
            "EV/EBITDA": ev_ebitda,
            "EV/EBIT": ev_ebit,
            "EV/Revenue": ev_rev,
            "EV/FCF": ev_fcf,
            "Earnings Yield (%)": earnings_yield,
            "FCF Yield (%)": fcf_yield,
            "Book Value Per Share": bvps,
            "Graham Number": graham_num,
            "Fair Value Discount (%)": fair_value_discount,
            "Historical P/E Percentile": pe_percentile,
            "Historical EV/EBITDA Percentile": ev_ebitda_percentile,
            "Peer Valuation Discount (%)": peer_discount,
            "Daily Change %": round((i % 7) - 3.2, 2),
            "Distance from 52W High %": round(-1.5 * (i % 15), 2),
            "Beta": round(0.8 + (i % 20) / 10.0, 2),
            "RSI (14)": float(35 + (i * 7) % 55),
            "200 SMA": "Above" if i % 2 == 0 else "Below"
        })

    return data_list