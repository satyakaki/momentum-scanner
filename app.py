import csv, datetime as dt, gc, json, os, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import config, universe, scan_logic

APP_VERSION = "v1.2.0-theme-timestamp"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

try:                                   # macOS/Linux default of 256 open files is too low for a big scan
    import resource
    _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    _target = 8192 if _hard == resource.RLIM_INFINITY else min(8192, _hard)
    if _soft < _target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (_target, _hard))
except Exception:                      # Windows has no 'resource' module
    pass

app = FastAPI(title="Momentum scanner")
status = {"running": False, "phase": "idle", "done": 0, "total": 0, "message": "", "log": []}
results = {"rows": [], "meta": {}}
_lock = threading.Lock()

def load_instruments():
    """Return NSE tradingsymbol -> instrument_token from data/instruments.csv when present."""
    path = os.path.join(BASE_DIR, "data", "instruments.csv")
    tokens = {}
    if not os.path.exists(path):
        return tokens
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if (row.get("exchange") or "").upper() != "NSE":
                    continue
                sym = (row.get("tradingsymbol") or "").strip()
                token = (row.get("instrument_token") or "").strip()
                if sym and token:
                    tokens[sym] = token
    except Exception as e:
        log(f"Could not load Kite instruments: {e}")
    return tokens

def kite_chart_url(symbol, tokens):
    tradingsymbol = symbol.strip().upper()
    token = tokens.get(tradingsymbol)
    if token:
        return f"https://kite.zerodha.com/chart/ext/tvc/NSE/{tradingsymbol}/{token}"
    return f"https://kite.zerodha.com/marketwatch?search=NSE:{tradingsymbol}"

def log(m):
    status["log"] = (status["log"] + [f"{dt.datetime.now():%H:%M:%S} {m}"])[-30:]
    print(m)

def scan_timestamp(now=None):
    now = now or dt.datetime.now(dt.timezone.utc).astimezone()
    try:
        ist = now.astimezone(dt.timezone(dt.timedelta(hours=5, minutes=30)))
        return {"last_scan_at": now.isoformat(timespec="seconds"),
                "last_scan_at_ist": ist.isoformat(timespec="seconds"),
                "last_scan_display": ist.strftime("%d %b %Y, %I:%M:%S %p IST")}
    except Exception:
        return {"last_scan_at": now.isoformat(timespec="seconds")}

def load_saved():
    if os.path.exists(config.RESULTS_PATH):
        try:
            with open(config.RESULTS_PATH) as f:
                results.update(json.load(f))
            meta = results.setdefault("meta", {})
            if "last_scan_at" not in meta:
                mtime = dt.datetime.fromtimestamp(os.path.getmtime(config.RESULTS_PATH), dt.timezone.utc).astimezone()
                meta.update(scan_timestamp(mtime))
        except Exception:
            pass

def run_scan(name):
    import datasource
    try:
        status.update(phase="universe", done=0, total=0, message="Fetching the stock list from NSE…")
        syms = [s["symbol"] for s in universe.load(name, log)]
        names = {}
        status.update(phase="prices", total=len(syms), message=f"Downloading prices for {len(syms)} stocks…")
        data = datasource.download_prices(syms, lambda d, t: status.update(done=d, total=t), log)
        status.update(phase="scan", message="Applying the scan…")
        rows, scanned = scan_logic.analyse_all(data)
        instruments = load_instruments()
        for r in rows:
            r["kite_url"] = kite_chart_url(r["symbol"], instruments)
        status.update(phase="fundamentals", done=0, total=len(rows),
                      message=f"{len(rows)} setups found. Fetching earnings and sales…")

        def fund(r):
            try:
                r.update(datasource.fundamentals(r["symbol"]))
            except Exception as e:
                log(f"{r['symbol']} fundamentals: {e}")
                r.update({"name": r["symbol"], "sector": "–", "sales": [], "profit": []})
        with ThreadPoolExecutor(config.FUND_WORKERS) as ex:
            for _ in as_completed([ex.submit(fund, r) for r in rows]):
                status["done"] += 1
                if status["done"] % 20 == 0:
                    gc.collect()
        results["rows"] = rows
        scan_time = dt.datetime.now(dt.timezone.utc).astimezone()
        results["meta"] = {"scanned": scanned, "universe": name, "requested": len(syms),
                           "at": scan_time.isoformat(timespec="seconds"), "version": APP_VERSION,
                           **scan_timestamp(scan_time)}
        os.makedirs(os.path.dirname(config.RESULTS_PATH) or ".", exist_ok=True)
        with open(config.RESULTS_PATH, "w") as f:
            json.dump(results, f)
        status.update(message=f"Done: {len(rows)} setups from {scanned} stocks")
    except Exception as e:
        status["message"] = f"Scan failed: {e}"
        log(status["message"])
    finally:
        status.update(running=False, phase="idle")

@app.on_event("startup")
def start(): load_saved()

@app.post("/api/scan")
def scan(universe_name: str = "nifty500"):
    if universe_name not in universe.SOURCES:
        raise HTTPException(400, "unknown universe")
    with _lock:
        if status["running"]:
            raise HTTPException(409, "A scan is already running")
        status["running"] = True
    threading.Thread(target=run_scan, args=(universe_name,), daemon=True).start()
    return {"started": True}

@app.get("/api/status")
def get_status(): return status

@app.get("/api/results")
def get_results():
    meta = {**results.get("meta", {}), "version": APP_VERSION}
    return {**results, "meta": meta, "setups": scan_logic.SETUPS}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def index(): return FileResponse(os.path.join(STATIC_DIR, "index.html"))
