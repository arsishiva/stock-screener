import urllib.request
import csv

print("Downloading and compiling expanded global stock lists...")

all_stocks = []
seen_tickers = set()

def add_stock(ticker, exchange):
    ticker = ticker.strip().upper()
    if ticker and ticker not in seen_tickers and len(ticker) <= 15:
        seen_tickers.add(ticker)
        all_stocks.append({"ticker": ticker, "exchange": exchange})

# 1. US STOCKS (NASDAQ, NYSE, AMEX ~8,000+ stocks)
try:
    print("Fetching US stocks (NASDAQ / NYSE / AMEX)...")
    url_us = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"
    req = urllib.request.Request(url_us, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        for t in content.splitlines():
            add_stock(t, "US")
    print(f"-> Total after US: {len(all_stocks)}")
except Exception as e:
    print(f"US Fetch Error: {e}")

# 2. INDIA STOCKS (NSE ~2,200+ stocks)
try:
    print("Fetching Indian NSE stocks...")
    url_india = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    req = urllib.request.Request(url_india, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        reader = csv.reader(content.splitlines())
        header = next(reader, None)
        symbol_idx = 0
        if header:
            for idx, col in enumerate(header):
                if "SYMBOL" in col.strip().upper():
                    symbol_idx = idx
                    break
        for row in reader:
            if len(row) > symbol_idx:
                sym = row[symbol_idx].strip()
                if sym:
                    add_stock(f"{sym}.NS", "NSE India")
    print(f"-> Total after India NSE: {len(all_stocks)}")
except Exception as e:
    print(f"India Fetch Error: {e}")

# 3. SWEDEN STOCKS (Nasdaq Stockholm .ST)
print("Compiling Swedish stocks (Nasdaq Stockholm)...")
sweden_stocks = [
    "VOLV-A", "VOLV-B", "ERIC-A", "ERIC-B", "AZN", "INVE-A", "INVE-B", "SEB-A", "SEB-C",
    "SAND", "ATCO-A", "ATCO-B", "HM-B", "TELIA", "ABB", "HEXA-B", "ASSA-B", "SKA-B",
    "KINV-A", "KINV-B", "ESSITY-A", "ESSITY-B", "EVO", "GETI-B", "SBB-B", "SINCH", "EMBRAC-B",
    "SWED-A", "SHB-A", "SHB-B", "ALFA", "BOL", "EPI-A", "EPI-B", "LUND-B", "NIBE-B",
    "SCA-A", "SCA-B", "SKF-A", "SKF-B", "SWMA", "TREL-B", "BALD-B", "SAAB-B", "ALLEI"
]
for s in sweden_stocks:
    add_stock(f"{s}.ST", "OMX Sweden")

# 4. GERMANY STOCKS (Xetra .DE)
print("Compiling German stocks (Xetra / Frankfurt)...")
germany_stocks = [
    "SAP", "SIE", "AIR", "DTE", "BMW", "MBG", "ALV", "BAS", "VOW3", "VOW", "DBK", "IFX",
    "RWE", "MRK", "EOAN", "DB1", "HEN3", "SHL", "BEI", "ZAL", "FRE", "FME", "PPA", "HFG",
    "SY1", "LEG", "BNR", "CON", "EVD", "PUM", "TAG", "TUI1", "GXI", "LHA", "MTX", "QIA"
]
for s in germany_stocks:
    add_stock(f"{s}.DE", "Xetra Germany")

# 5. NETHERLANDS STOCKS (Euronext Amsterdam .AS)
print("Compiling Netherlands stocks (Euronext Amsterdam)...")
netherlands_stocks = [
    "ASML", "INGA", "PRX", "AD", "REN", "ASM", "AKZA", "HEIA", "HEIEN", "NN", "KPN",
    "RAND", "AALB", "IMCD", "BESI", "ARCAD", "JDEP", "VOPR", "SBMO", "FLOW", "LIGHT"
]
for s in netherlands_stocks:
    add_stock(f"{s}.AS", "Euronext Amsterdam")

# 6. UNITED KINGDOM STOCKS (London Stock Exchange .L)
print("Compiling UK stocks (London Stock Exchange)...")
uk_stocks = [
    "SHEL", "AZN", "HSBC", "ULVR", "BP", "GSK", "DGE", "RIO", "REL", "GLEN", "BARC",
    "VOD", "LLOY", "NG", "CPG", "AAL", "PRU", "BA", "LSEG", "TSCO", "BATS", "ABF",
    "STAN", "NWG", "SSE", "RR", "MNDI", "LGEN", "EXPN", "CRH", "IAG", "ENT", "BDEV"
]
for s in uk_stocks:
    add_stock(f"{s}.L", "London Stock Exchange")

# 7. FRANCE STOCKS (Euronext Paris .PA)
print("Compiling French stocks (Euronext Paris)...")
france_stocks = [
    "TTE", "MC", "OR", "AIR", "BN", "SAN", "SU", "AI", "KER", "GLE", "VEO", "CA",
    "EN", "DG", "RI", "ML", "ORA", "STM", "VIE", "LR", "EL", "RMS", "CAP", "PUB", "SGO"
]
for s in france_stocks:
    add_stock(f"{s}.PA", "Euronext Paris")

print(f"\nSUCCESS! Generated {len(all_stocks)} total unique tickers across US, India, UK, Sweden, Germany, Netherlands, and France.")

# Save directly to tickers.csv using pure Python
with open("tickers.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["ticker", "exchange"])
    writer.writeheader()
    writer.writerows(all_stocks)

print("Saved cleanly to 'tickers.csv'!")