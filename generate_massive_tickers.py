import pandas as pd
import requests
import io

print("Downloading massive global stock lists from free public sources...")

all_stocks = []

# 1. Fetching US Stocks (NASDAQ, NYSE, AMEX - ~8,000+ stocks)
try:
    print("Fetching US stocks...")
    url_us = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
    response = requests.get(url_us)
    if response.status_code == 200:
        us_tickers = response.text.splitlines()
        for t in us_tickers:
            t = t.strip().upper()
            if t and len(t) <= 5: # Filter out weird symbols
                all_stocks.append({"ticker": t, "exchange": "US"})
        print(f"-> Added {len(us_tickers)} US stocks.")
except Exception as e:
    print(f"Could not fetch US stocks: {e}")

# 2. Fetching India NSE Stocks (.NS - ~2,000+ stocks)
try:
    print("Fetching Indian NSE stocks...")
    url_india = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url_india, headers=headers)
    if response.status_code == 200:
        df_india = pd.read_csv(io.StringIO(response.text))
        for symbol in df_india['SYMBOL']:
            all_stocks.append({"ticker": f"{symbol.strip()}.NS", "exchange": "NSE"})
        print(f"-> Added {len(df_india)} Indian stocks.")
except Exception as e:
    print(f"Could not fetch India stocks: {e}")

# 3. Adding Major European Stocks (Sweden .ST, Germany .DE, France .PA, UK .L)
eu_tickers = [
    # Sweden (.ST)
    "VOLV-B.ST", "ERIC-B.ST", "AZN.ST", "INVE-B.ST", "SEB-A.ST", "SAND.ST", "ATCO-A.ST", "HM-B.ST", "TELIA.ST", "ABB.ST",
    # Germany (.DE)
    "SAP.DE", "SIE.DE", "AIR.DE", "DTE.DE", "BMW.DE", "MBG.DE", "ALV.DE", "BAS.DE", "VOW3.DE", "DBK.DE", "IFX.DE",
    # France (.PA)
    "TTE.PA", "MC.PA", "OR.PA", "AIR.PA", "BN.PA", "SAN.PA", "SU.PA", "AI.PA", "KER.PA", "GLE.PA",
    # UK (.L) & Netherlands (.AS)
    "SHEL.L", "AZN.L", "HSBC.L", "ULVR.L", "BP.L", "GSK.L", "DGE.L", "RIO.L", "ASML.AS", "AD.AS", "INGA.AS"
]
for t in eu_tickers:
    all_stocks.append({"ticker": t, "exchange": "Europe"})

# Save everything into tickers.csv
df_final = pd.DataFrame(all_stocks).drop_duplicates(subset=["ticker"])
df_final.to_csv("tickers.csv", index=False)

print(f"\nSUCCESS! Created 'tickers.csv' with {len(df_final)} total global stocks ready for screening!")