import os
RESULTS_PATH = os.getenv("RESULTS_PATH", "data/results.json")
UNIVERSE_CACHE_DAYS = 7
BATCH = int(os.getenv("BATCH", "40"))          # tickers per Yahoo price download
FUND_WORKERS = int(os.getenv("FUND_WORKERS", "3"))

# Liquidity: skip illiquid stocks (momentum traders need to get in and out)
MIN_PRICE = 30.0
MIN_TRADED_VALUE_CR = 5.0                      # average daily traded value, Rs crore

# Trend template thresholds
RS_STRICT = 70
RS_RELAXED = 60
DOWNLOAD_THREADS = int(os.getenv("DOWNLOAD_THREADS", "4"))   # fewer threads = fewer open sockets
