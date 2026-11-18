#!/usr/bin/env python3
"""How names did after they newly joined the joint-bull or joint-bear list.

One episode per entry. A name that stays on the list does not open another
episode until it drops off and comes back. Entry is the close of the next US
session that had not finished when the window ended. Hold for 10 sessions.
Bull excess is the stock minus QQQ. Bear excess is QQQ minus the stock, the
result of being short. Split excess is the stock minus QQQ. Writes
data/followthrough.json, including a by_ticker index for stock pages.
Split rows stay out of `rows` so the homepage table does not label them bearish.
If prices cannot be loaded, keeps the previous file and exits 0.
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "consensus-history.json"
OUT = ROOT / "data" / "followthrough.json"
HKT = ZoneInfo("Asia/Hong_Kong")
ET = ZoneInfo("America/New_York")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
HORIZON = 10


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read()
    except Exception:
        return None


def yahoo(sym):
    q = urllib.parse.quote(sym, safe="")
    body = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?range=6mo&interval=1d&includePrePost=false")
    if not body:
        return None
    try:
        res = json.loads(body)["chart"]["result"][0]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    ts = res.get("timestamp") or []
    closes = ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    off = (res.get("meta") or {}).get("gmtoffset") or 0
    out = {}
    for t, c in zip(ts, closes):
        if c is None:
            continue
        day = datetime.fromtimestamp(t + off, timezone.utc).date().isoformat()
        out[day] = c
    return out or None


def sym_of(t):
    if t in ("BRK.B", "BRK.A"):
        return t.replace(".", "-")
    return t


def entry_date(window_end, sessions):
    if "T" not in str(window_end):
        day = str(window_end)[:10]
        return next((d for d in sessions if d > day), None)
    dt = datetime.fromisoformat(window_end).replace(tzinfo=HKT).astimezone(ET)
    day = dt.date().isoformat()
    passed = dt.hour > 16 or (dt.hour == 16 and dt.minute > 0)
    return next((d for d in sessions if d > day), None) if passed else next((d for d in sessions if d >= day), None)


def px_on(bars, sessions, ticker, day):
    b = bars.get(ticker) or {}
    if day in b:
        return b[day]
    i = next((k for k, d in enumerate(sessions) if d >= day), None)
    if i is None:
        return None
    for d in sessions[i:i + 3]:
        if d in b:
            return b[d]
    return None


def median(xs):
    s = sorted(xs)
    n = len(s)
    if not n:
        return None
    if n % 2:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def side_stats(part):
    """Settled 10-session results for one side. hit is the share with xs > 0."""
    settled = [r for r in part if r.get("status") == "settled"]
    xs = [r["xs"] for r in settled]
    rets = [r["ret"] for r in settled]
    return {
        "opened": len(part),
        "settled": len(settled),
        "immature": sum(1 for r in part if r.get("status") == "immature"),
        "avg_ret": round(sum(rets) / len(rets), 6) if rets else None,
        "avg_xs": round(sum(xs) / len(xs), 6) if xs else None,
        "hit": round(sum(1 for x in xs if x > 0) / len(xs), 6) if xs else None,
    }


def index_by_ticker(rows):
    buckets = {}
    for r in rows:
        buckets.setdefault(r["ticker"], {}).setdefault(r["side"], []).append(r)
    return {
        t: {side: side_stats(part) for side, part in sides.items() if part}
        for t, sides in buckets.items()
    }


def main():
    hist = json.loads(HIST.read_text(encoding="utf-8"))["days"]
    tickers = {"QQQ"}
    for v in hist.values():
        tickers.update(v.get("bull") or [])
        tickers.update(v.get("bear") or [])
        tickers.update(v.get("split") or [])
    bars = {}
    for t in sorted(tickers):
        b = yahoo(sym_of(t))
        if b:
            bars[t] = b
        time.sleep(0.15)
    if "QQQ" not in bars or len(bars) < 40:
        print("prices short, keep previous follow-through")
        return
    sessions = sorted(bars["QQQ"])
    rows = []
    for side in ("bull", "bear", "split"):
        prev = set()
        for day in sorted(hist):
            cur = set(hist[day].get(side) or [])
            window = hist[day].get("window") or []
            end = window[1] if len(window) > 1 else day
            for t in sorted(cur - prev):
                ent = entry_date(end, sessions)
                rec = {"ticker": t, "side": side, "signal": day, "entry": ent, "status": "no_price"}
                if ent and ent in sessions:
                    ei = sessions.index(ent)
                    xi = ei + HORIZON
                    if xi >= len(sessions):
                        rec["status"] = "immature"
                    else:
                        ex = sessions[xi]
                        sp, sq = px_on(bars, sessions, t, ent), px_on(bars, sessions, "QQQ", ent)
                        ep, eq = px_on(bars, sessions, t, ex), px_on(bars, sessions, "QQQ", ex)
                        if not all((sp, sq, ep, eq)) or min(sp, sq) <= 0:
                            rec["status"] = "no_price"
                        else:
                            ret = ep / sp - 1
                            qr = eq / sq - 1
                            xs = (qr - ret) if side == "bear" else (ret - qr)
                            rec.update(exit=ex, ret=round(ret, 6), qqq=round(qr, 6), xs=round(xs, 6), status="settled")
                rows.append(rec)
            prev = cur

    def block(side):
        part = [r for r in rows if r["side"] == side]
        settled = [r for r in part if r["status"] == "settled"]
        xs = [r["xs"] for r in settled]
        return {
            "opened": len(part),
            "settled": len(settled),
            "immature": sum(1 for r in part if r["status"] == "immature"),
            "no_price": sum(1 for r in part if r["status"] == "no_price"),
            "avg_xs": round(sum(xs) / len(xs), 6) if xs else None,
            "median_xs": round(median(xs), 6) if xs else None,
            "hit": round(sum(1 for x in xs if x > 0) / len(xs), 6) if xs else None,
            "avg_ret": round(sum(r["ret"] for r in settled) / len(settled), 6) if settled else None,
        }

    bull = block("bull")
    if OUT.is_file():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        if bull["settled"] < 20 and (old.get("bull") or {}).get("settled", 0) >= 20:
            print("new sample too small, keep previous")
            return
    show = [r for r in rows if r["status"] == "settled" and r["side"] in ("bull", "bear")]
    show.sort(key=lambda r: (r["signal"], r["ticker"]), reverse=True)
    now = datetime.now(HKT).strftime("%Y-%m-%d %H:%M")
    out = {
        "as_of": sessions[-1],
        "from": min(hist),
        "horizon": HORIZON,
        "benchmark": "QQQ",
        "updated_hkt": now,
        "bull": bull,
        "bear": block("bear"),
        "by_ticker": index_by_ticker(rows),
        "rows": [{k: r[k] for k in ("ticker", "side", "signal", "entry", "exit", "ret", "qqq", "xs")} for r in show[:40]],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("follow-through", out["as_of"], "bull", bull["settled"], "bear", out["bear"]["settled"])


if __name__ == "__main__":
    main()
