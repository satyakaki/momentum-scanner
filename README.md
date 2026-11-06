# Momentum Scanner (NSE)

Version: v1.2.0-theme-timestamp

Scans NSE stocks online for Stage-2 leaders showing momentum-trader setups,
then adds market cap, EPS, sales and profit for the last 4 quarters, TTM and last-FY PAT.
Click a stock to open its Kite TV chart in a new browser tab. The UI includes vibrant light and readable dark themes plus a prominent last-scan timestamp.

## Run
```bash
./setup_run_app.sh              # opens http://localhost:8000, press "Scan now"

# or manually:
pip install -r requirements.txt
uvicorn app:app --port 8000
```
Pick a universe in the dropdown: Nifty 500, MidSmallcap 400, Midcap 150, Smallcap 100 or All NSE. Nifty 500 takes about 5 minutes, all NSE about 15. Run it after market close (daily bars).
Results are saved in data/results.json and shown again next time you open the app.
Kite chart URLs use `data/instruments.csv` to map NSE `tradingsymbol` to `instrument_token`.
When a token is present the URL is `https://kite.zerodha.com/chart/ext/tvc/NSE/<tradingsymbol>/<instrument_token>`; otherwise the UI falls back to a Kite marketwatch search URL.
Tests: `python tests/test_logic.py`

## The scan (my interpretation of a Minervini-style momentum approach, not an official rule set)
1. Liquidity: price at least Rs 30 and average daily traded value at least Rs 5 Cr (config.py).
2. Trend template (8 checks): price above 150 and 200 DMA, 150 above 200, 200 DMA rising a month, 50 above 150 and 200,
   price above 50, 30%+ above 52-week low, within 25% of 52-week high, RS rating 70+.
   Default view uses a relaxed version (above 50 and 200 DMA, within 30% of high, RS 60+); the switch makes it strict.
3. RS rating: weighted 3/6/9/12-month return, ranked 0-99 against every stock scanned.
4. Setups: Breakout, Tight base (VCP-style), Momentum burst (4% rule), Episodic pivot, Pocket pivot, Pullback to 21 EMA.
   Episodic pivots are allowed even if the stock was not yet in an uptrend.
5. Stop = higher of the 10-day low and entry minus 2 ATR.

Data is from Yahoo Finance; quarterly figures can be missing or late for some small caps. Not investment advice.

## Troubleshooting
`[Errno 24] Too many open files`: restart the server (the old process keeps its leaked handles). The app now raises the limit itself
and downloads with fewer threads. On macOS you can also run `ulimit -n 8192` before `uvicorn`. Lower DOWNLOAD_THREADS / BATCH in config.py if it still happens.
