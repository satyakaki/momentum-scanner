"""Online data via Yahoo Finance: bulk daily prices, then fundamentals for the shortlisted stocks only."""
import gc, math
import yfinance as yf

def _num(x):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else x
    except (TypeError, ValueError):
        return None

def benchmark():
    h = yf.Ticker("^NSEI").history(period="14mo")
    return [float(x) for x in h["Close"].dropna().tolist()]

def download_prices(symbols, progress=None, log=print):
    """-> {symbol: (open, high, low, close, volume)} using batched downloads (fast)."""
    out, total = {}, len(symbols)
    from config import BATCH, DOWNLOAD_THREADS
    for i in range(0, total, BATCH):
        batch = symbols[i:i + BATCH]
        tk = [s + ".NS" for s in batch]
        try:
            df = yf.download(tk, period="14mo", interval="1d", group_by="ticker", auto_adjust=True,
                             threads=DOWNLOAD_THREADS, progress=False)
        except Exception as e:
            log(f"batch {i // BATCH + 1} failed: {e}")
            continue
        multi = hasattr(df.columns, "levels") and df.columns.nlevels > 1
        for s in batch:
            try:
                d = df[s + ".NS"] if multi else df
                d = d.dropna(subset=["Close"])
                if len(d) < 210:
                    continue
                out[s] = tuple([float(x) for x in d[k].tolist()] for k in ("Open", "High", "Low", "Close", "Volume"))
            except Exception:
                continue
        del df
        gc.collect()                                   # release sockets/handles between batches
        if progress:
            progress(min(i + BATCH, total), total)
    return out

def _row(df, names):
    """(labels, values) newest first for the first matching row."""
    if df is None or getattr(df, "empty", True):
        return [], []
    for n in names:
        if n in df.index:
            r = df.loc[n].sort_index(ascending=False)
            pairs = [(k, _num(x)) for k, x in zip(r.index, r.tolist())]
            pairs = [(k, x) for k, x in pairs if x is not None]
            return [k for k, _ in pairs], [x for _, x in pairs]
    return [], []

def _qlabel(ts):
    try:
        return ts.strftime("%b %y")
    except Exception:
        return str(ts)[:7]

def _growth(cur, prev):
    if cur is None or prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100

def fundamentals(symbol):
    t = yf.Ticker(symbol + ".NS")
    info = t.info or {}
    qi, ai = t.quarterly_income_stmt, t.income_stmt
    ql, qs = _row(qi, ["Total Revenue", "Operating Revenue"])
    pl, qp = _row(qi, ["Net Income", "Net Income Common Stockholders"])
    _, qe = _row(qi, ["Diluted EPS", "Basic EPS"])
    al, ap = _row(ai, ["Net Income", "Net Income Common Stockholders"])

    def block(labels, vals):
        out = []
        for k in range(min(4, len(vals))):
            nxt = vals[k + 1] if k + 1 < len(vals) else None
            out.append({"q": _qlabel(labels[k]), "v": round(vals[k] / 1e7, 1), "g": _growth(vals[k], nxt)})
        out.reverse()                                   # oldest -> newest
        for b in out:
            b["g"] = None if b["g"] is None else round(b["g"], 1)
        return out

    mcap = _num(info.get("marketCap"))
    eps = _num(info.get("trailingEps"))
    if eps is None and len(qe) >= 4:
        eps = sum(qe[:4])
    return {
        "name": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector") or "–",
        "mcap_cr": round(mcap / 1e7) if mcap else None,
        "eps_ttm": round(eps, 2) if eps is not None else None,
        "sales": block(ql, qs), "profit": block(pl, qp),
        "sales_yoy": round(_growth(qs[0], qs[4]), 1) if len(qs) > 4 and _growth(qs[0], qs[4]) is not None else None,
        "profit_yoy": round(_growth(qp[0], qp[4]), 1) if len(qp) > 4 and _growth(qp[0], qp[4]) is not None else None,
        "pat_ttm": round(sum(qp[:4]) / 1e7, 1) if len(qp) >= 4 else None,
        "pat_fy": round(ap[0] / 1e7, 1) if ap else None,
        "fy_label": _qlabel(al[0]) if al else None,
    }
