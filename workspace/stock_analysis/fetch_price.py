#!/usr/bin/env python3
"""
Fetch current AAPL price from Yahoo Finance and save to workspace/stock_analysis/price.txt
This script is a simple, dependency-free fallback if the agents cannot coordinate.
"""
import json
import urllib.request
import os
import sys

# Try multiple sources in order. FinancialModelingPrep provides a demo API that often works
# without an API key: https://financialmodelingprep.com/developer/docs/
FMP_URL = "https://financialmodelingprep.com/api/v3/quote-short/AAPL?apikey=demo"
YAHOO_URL = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=AAPL"
STOOQ_URL = "https://stooq.com/q/l/?s=aapl.us&f=sd2t2ohlcv&h&e=csv"

def _fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def fetch_price():
    # 1) Try FinancialModelingPrep (demo key)
    try:
        data = _fetch_json(FMP_URL)
        if isinstance(data, list) and data:
            price = data[0].get("price")
            if price is not None:
                return price
    except Exception as e:
        print("FMP fetch failed:", repr(e))

    # 2) Try Stooq CSV endpoint (simple CSV response)
    try:
        req = urllib.request.Request(STOOQ_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode(errors="ignore")
        # CSV: Symbol,Date,Time,Open,High,Low,Close,Volume
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            last = lines[1].split(',')
            # Close price is at index 6 in the returned format
            price = last[6]
            try:
                return float(price)
            except Exception:
                return None
    except Exception as e:
        print("Stooq fetch failed:", repr(e))

    # 2) Try Yahoo Finance JSON endpoint
    try:
        data = _fetch_json(YAHOO_URL)
        price = data["quoteResponse"]["result"][0].get("regularMarketPrice")
        if price is not None:
            return price
    except Exception as e:
        print("Yahoo fetch failed:", repr(e))

    # All attempts failed
    return None


def main():
    price = fetch_price()
    if price is None:
        print("ERROR: could not fetch price")
        sys.exit(1)
    out_dir = os.path.join("workspace", "stock_analysis")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "price.txt")
    with open(out_path, "w") as f:
        f.write(str(price))
    print("WROTE", out_path)
    print("PRICE:", price)

if __name__ == '__main__':
    main()
