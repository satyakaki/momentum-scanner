"""Stock list fetched online (cached on disk automatically). No files needed from you."""
import csv, io, os, time, requests
from config import UNIVERSE_CACHE_DAYS

def _idx(fname):
    return [f"https://www.niftyindices.com/IndexConstituent/{fname}",
            f"https://niftyindices.com/IndexConstituent/{fname}",
            f"https://archives.nseindia.com/content/indices/{fname}"]

SOURCES = {
    "nifty500":    _idx("ind_nifty500list.csv"),
    "midsmall400": _idx("ind_niftymidsmallcap400list.csv"),
    "midcap150":   _idx("ind_niftymidcap150list.csv"),
    "smallcap100": _idx("ind_niftysmallcap100list.csv"),
    "all_nse":  ["https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
                 "https://archives.nseindia.com/content/equities/EQUITY_L.csv"],
}
# Last-resort list so the app still works if NSE blocks the download
FALLBACK = ("RELIANCE TCS HDFCBANK ICICIBANK INFY HINDUNILVR ITC SBIN BHARTIARTL KOTAKBANK LT AXISBANK ASIANPAINT "
            "MARUTI SUNPHARMA TITAN ULTRACEMCO BAJFINANCE NESTLEIND WIPRO HCLTECH TECHM POWERGRID NTPC ONGC TATASTEEL "
            "JSWSTEEL ADANIENT ADANIPORTS COALINDIA GRASIM CIPLA DRREDDY EICHERMOT HEROMOTOCO BAJAJ-AUTO TRENT "
            "HAL BEL DIXON POLYCAB PERSISTENT COFORGE MAXHEALTH").split()

def _parse(text):
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        sym = row.get("Symbol") or row.get("SYMBOL")
        series = row.get("SERIES")
        if sym and (not series or series == "EQ"):
            out.append({"symbol": sym, "company": row.get("Company Name") or row.get("NAME OF COMPANY") or sym})
    return out

def load(name, log=print):
    cache = os.path.join("data", f"universe_{name}.csv")
    os.makedirs("data", exist_ok=True)
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < UNIVERSE_CACHE_DAYS * 86400:
        with open(cache, encoding="utf-8-sig") as f:
            got = _parse(f.read())
        if got:
            return got
    for url in SOURCES[name]:
        try:
            with requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"},
                              timeout=30) as r:
                r.raise_for_status()
                content = r.content
            got = _parse(content.decode("utf-8-sig"))
            if got:
                with open(cache, "wb") as f:
                    f.write(content)
                log(f"Loaded {len(got)} stocks from {url.split('/')[2]}")
                return got
        except Exception as e:
            log(f"Could not download {url}: {e}")
    log("Using the built-in short list (NSE download failed). Try again later for the full universe.")
    return [{"symbol": s, "company": s} for s in FALLBACK]
