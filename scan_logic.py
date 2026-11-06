"""Momentum-trader scan: Minervini-style Stage-2 trend template + common setups.
Pure Python on daily bars (oldest -> newest) so it is easy to test."""
from config import MIN_PRICE, MIN_TRADED_VALUE_CR, RS_STRICT, RS_RELAXED

SETUPS = {
    "Breakout":       "Closed above the prior 20-day high on 1.4x+ volume",
    "Tight base":     "Price squeezing in a shrinking range (VCP-style) just under its pivot, volume drying up",
    "Momentum burst": "Up 4%+ today on rising volume (the 4% rule)",
    "Episodic pivot": "Gapped up 8%+ on 3x+ volume in the last 3 days and holding",
    "Pocket pivot":   "Up day on volume bigger than any recent down day, near the 21 EMA",
    "Pullback":       "Leader quietly pulling back to its 21 EMA on light volume",
}

def sma(v, n): return sum(v[-n:]) / n if len(v) >= n else None

def ema(v, n):
    if len(v) < n: return None
    k = 2 / (n + 1); e = sum(v[:n]) / n
    for x in v[n:]: e = x * k + e * (1 - k)
    return e

def atr(h, l, c, n=14):
    trs = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]
    if len(trs) < n: return None
    a = sum(trs[:n]) / n
    for t in trs[n:]: a = (a * (n - 1) + t) / n
    return a

def ret(c, n): return (c[-1] / c[-1 - n] - 1) * 100 if len(c) > n and c[-1 - n] else None

def rng(h, l):
    top = max(h)
    return (top - min(l)) / top * 100 if top else 0

def rs_raw(c):
    """IBD-style weighted return: recent quarter counts double."""
    n = len(c) - 1
    parts = [(0.4, ret(c, min(63, n))), (0.2, ret(c, min(126, n))), (0.2, ret(c, min(189, n))), (0.2, ret(c, min(251, n)))]
    return sum(w * r for w, r in parts if r is not None)

def metrics(o, h, l, c, v):
    n = len(c)
    if n < 210:
        return None
    price, prev = c[-1], c[-2]
    avgv = sum(v[-51:-1]) / 50
    if avgv <= 0:
        return None
    return {
        "price": price, "chg": (price / prev - 1) * 100, "volx": v[-1] / avgv,
        "value_cr": avgv * price / 1e7, "s50": sma(c, 50), "s150": sma(c, 150), "s200": sma(c, 200),
        "s200_prev": sum(c[-221:-21]) / 200 if n >= 221 else None,
        "ema21": ema(c, 21), "atr": atr(h, l, c), "h52": max(h[-252:]), "l52": min(l[-252:]),
        "rs_raw": rs_raw(c),
    }

def template(m, rs):
    """Minervini's 8 trend-template checks. Returns (list of 8 bools, strict_pass, relaxed_pass)."""
    p = m["price"]
    checks = [
        p > m["s150"] and p > m["s200"],
        m["s150"] > m["s200"],
        m["s200_prev"] is not None and m["s200"] > m["s200_prev"],
        m["s50"] > m["s150"] and m["s50"] > m["s200"],
        p > m["s50"],
        p >= 1.3 * m["l52"],
        p >= 0.75 * m["h52"],
        rs >= RS_STRICT,
    ]
    relaxed = p > m["s50"] and p > m["s200"] and p >= 0.70 * m["h52"] and rs >= RS_RELAXED
    return checks, all(checks), relaxed

def detect_setups(o, h, l, c, v, m):
    tags, ep_days = [], None
    p, prev = c[-1], c[-2]
    avgv = sum(v[-51:-1]) / 50
    prior_high = max(h[-21:-1])
    pivot = None

    if p > prior_high and m["volx"] >= 1.4 and p <= prior_high * 1.06:
        tags.append("Breakout"); pivot = prior_high

    r1, r2, r3 = rng(h[-30:-20], l[-30:-20]), rng(h[-20:-10], l[-20:-10]), rng(h[-10:], l[-10:])
    top20 = max(h[-20:])
    if (r3 <= 8 and r3 <= 0.7 * r1 and sum(v[-5:]) / 5 < avgv and p >= 0.95 * top20
            and p <= prior_high * 1.005):
        tags.append("Tight base"); pivot = pivot or top20

    if m["chg"] >= 4 and v[-1] > v[-2] and m["volx"] >= 1.2:
        tags.append("Momentum burst")

    for k in range(3):
        i = -1 - k
        base = sum(v[i - 50:i]) / 50 if len(v) > 52 else avgv
        gap = (o[i] / c[i - 1] - 1) * 100
        if gap >= 8 and base > 0 and v[i] / base >= 3 and c[i] > (h[i] + l[i]) / 2 and p >= l[i]:
            tags.append("Episodic pivot"); ep_days = k; break

    down_vols = [v[-j] for j in range(1, 11) if c[-j] < c[-j - 1]]
    if (p > prev and v[-1] > (max(down_vols) if down_vols else avgv) and m["ema21"]
            and abs(p / m["ema21"] - 1) <= 0.04 and p > m["s50"]):
        tags.append("Pocket pivot")

    if (m["ema21"] > m["s50"] > m["s200"] and 0 <= p / m["ema21"] - 1 <= 0.03 and min(l[-3:]) <= m["ema21"] * 1.01
            and p <= max(c[-8:-1]) * 0.97 and m["volx"] <= 1.1):
        tags.append("Pullback")
    return tags, pivot, ep_days

def trade_levels(l, m, pivot, tags):
    entry = pivot * 1.001 if pivot and "Tight base" in tags and "Breakout" not in tags else m["price"]
    stop = max(min(l[-10:]), entry - 2 * (m["atr"] or 0))
    if stop >= entry:
        stop = entry - 2 * (m["atr"] or entry * 0.05)
    return round(entry, 2), round(stop, 2), round((entry - stop) / entry * 100, 1)

def analyse_all(data):
    """data: {symbol: (o,h,l,c,v)} -> candidate rows (before fundamentals)."""
    ms = {}
    for sym, (o, h, l, c, v) in data.items():
        m = metrics(o, h, l, c, v)
        if m:
            ms[sym] = m
    order = sorted(ms, key=lambda s: ms[s]["rs_raw"])
    rank = {s: round(i / max(1, len(order) - 1) * 99) for i, s in enumerate(order)}   # RS rating 0-99
    rows = []
    for sym, m in ms.items():
        if m["price"] < MIN_PRICE or m["value_cr"] < MIN_TRADED_VALUE_CR:
            continue
        o, h, l, c, v = data[sym]
        rs = rank[sym]
        checks, strict, relaxed = template(m, rs)
        tags, pivot, ep_days = detect_setups(o, h, l, c, v, m)
        if not tags or not (relaxed or "Episodic pivot" in tags):
            continue
        entry, stop, risk = trade_levels(l, m, pivot, tags)
        rows.append({
            "symbol": sym, "price": round(m["price"], 2), "chg": round(m["chg"], 2), "volx": round(m["volx"], 1),
            "rs": rs, "from_high": round((m["price"] / m["h52"] - 1) * 100, 1), "value_cr": round(m["value_cr"], 1),
            "tags": tags, "ep_days": ep_days, "checks": checks, "score": sum(checks), "strict": strict,
            "entry": entry, "stop": stop, "risk_pct": risk,
        })
    return rows, len(ms)
