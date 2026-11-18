"""Live market data for SIPS. Mutual funds: mfapi.in (AMFI data, no install needed).
Stocks and indices: Yahoo Finance via the optional 'yfinance' package."""
import json, math, urllib.parse, urllib.request
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

try:
    import yfinance as yf
    HAVE_YF = True
except ImportError:
    HAVE_YF = False

# label, search words, category, risk, min horizon (years), assumed minimum monthly SIP (INR)
MF_WATCHLIST = [
    ("HDFC Liquid", "HDFC Liquid", "Liquid", "Low", 0, 500),
    ("ICICI Prudential Short Term", "ICICI Prudential Short Term", "Debt", "Low", 1, 500),
    ("HDFC Balanced Advantage", "HDFC Balanced Advantage", "Hybrid", "Moderate", 3, 500),
    ("UTI Nifty 50 Index", "UTI Nifty 50 Index", "Index", "Moderate", 5, 500),
    ("Parag Parikh Flexi Cap", "Parag Parikh Flexi Cap", "Equity", "High", 5, 1000),
    ("Motilal Oswal Midcap", "Motilal Oswal Midcap", "Equity", "High", 7, 500),
    ("Nippon India Gold Savings", "Nippon India Gold Savings", "Gold", "Moderate", 3, 500),
]
STOCKS = [("Reliance Industries", "RELIANCE.NS"), ("Tata Consultancy Services", "TCS.NS"), ("Infosys", "INFY.NS"),
          ("HDFC Bank", "HDFCBANK.NS"), ("ICICI Bank", "ICICIBANK.NS"), ("ITC", "ITC.NS"),
          ("Hindustan Unilever", "HINDUNILVR.NS"), ("Larsen & Toubro", "LT.NS"),
          ("State Bank of India", "SBIN.NS"), ("Bharti Airtel", "BHARTIARTL.NS")]
INDICES = [("Nifty 50", "^NSEI", "Indian indices"), ("Sensex", "^BSESN", "Indian indices"), ("Nifty Bank", "^NSEBANK", "Indian indices"),
           ("S&P 500", "^GSPC", "International indices"), ("Dow Jones Industrial Average", "^DJI", "International indices"),
           ("NASDAQ Composite", "^IXIC", "International indices"), ("FTSE 100", "^FTSE", "International indices"),
           ("Nikkei 225", "^N225", "International indices"), ("Hang Seng Index", "^HSI", "International indices"),
           ("Gold ETF (GOLDBEES)", "GOLDBEES.NS", "Gold, silver and currency"),
           ("Silver ETF (SILVERBEES)", "SILVERBEES.NS", "Gold, silver and currency"), ("USD/INR", "INR=X", "Gold, silver and currency")]


def slug(text):
    return "-".join(text.lower().split())


def http_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "SIPS-student-project"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def value_on_or_before(pts, target):
    last = None
    for d, v in pts:
        if d <= target:
            last = v
        else:
            break
    return last


def series_metrics(pts):
    """pts: list of (datetime, price) sorted oldest to newest."""
    end_d, end = pts[-1]
    m = {"latest": round(end, 2), "as_of": end_d.strftime("%d %b %Y")}
    m["chg_1d"] = round((end / pts[-2][1] - 1) * 100, 2) if len(pts) > 1 else None
    for k, days in (("chg_1w", 7), ("chg_1m", 30), ("chg_6m", 182)):
        v = value_on_or_before(pts, end_d - timedelta(days=days))
        m[k] = round((end / v - 1) * 100, 2) if v else None
    for yrs in (1, 3, 5):
        start = value_on_or_before(pts, end_d - timedelta(days=365 * yrs))
        m["ret_%dy" % yrs] = round(((end / start) ** (1.0 / yrs) - 1) * 100, 1) if start else None
    recent = [p for p in pts if p[0] >= end_d - timedelta(days=365 * 3)]
    rets = [recent[i][1] / recent[i - 1][1] - 1 for i in range(1, len(recent))]
    if len(rets) > 20:
        mean = sum(rets) / len(rets)
        sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
        m["volatility"] = round(sd * math.sqrt(252) * 100, 1)
    peak, mdd = 0, 0
    for _, v in recent:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    m["max_drawdown"] = round(mdd * 100, 1)
    span = [p for p in pts if p[0] >= end_d - timedelta(days=365 * 5)]
    step = max(1, len(span) // 80)
    sample = span[::step]
    if sample[-1] != span[-1]:
        sample.append(span[-1])
    fmt = "%b %Y" if (span[-1][0] - span[0][0]).days > 730 else "%d %b"
    m["chart"] = {"labels": [d.strftime(fmt) for d, _ in sample], "values": [round(v, 2) for _, v in sample]}
    m["m13"] = [value_on_or_before(pts, end_d - timedelta(days=round(30.4 * k))) for k in range(12, -1, -1)]
    return m


def resolve_scheme(words):
    found = http_json("https://api.mfapi.in/mf/search?q=" + urllib.parse.quote(words))
    good = [s for s in found if "direct" in s["schemeName"].lower() and "growth" in s["schemeName"].lower()
            and not any(w in s["schemeName"].lower() for w in ("idcw", "dividend", "bonus", "payout"))]
    if not good:
        raise ValueError("no direct growth plan found")
    return min(good, key=lambda s: len(s["schemeName"]))


def build_mf(label, words, category, risk, min_h, min_sip):
    s = resolve_scheme(words)
    d = http_json("https://api.mfapi.in/mf/%s" % s["schemeCode"])
    pts = []
    for x in d["data"]:
        try:
            pts.append((datetime.strptime(x["date"], "%d-%m-%Y"), float(x["nav"])))
        except (ValueError, KeyError):
            continue
    pts = sorted(p for p in pts if p[1] > 0)
    m = series_metrics(pts)
    meta = d.get("meta", {})
    m.update(kind="mf", name=s["schemeName"], label=label, category=category, risk=risk, min_horizon=min_h,
             min_sip=min_sip, scheme_code=s["schemeCode"], fund_house=meta.get("fund_house"),
             sebi_category=meta.get("scheme_category"), scheme_type=meta.get("scheme_type"))
    return "mf:" + slug(label), m


def yf_points(symbol, period):
    h = yf.Ticker(symbol).history(period=period, interval="1d")["Close"].dropna()
    return [(i.to_pydatetime().replace(tzinfo=None), float(v)) for i, v in h.items()]


def build_stock(name, symbol):
    pts = yf_points(symbol, "5y")
    if len(pts) < 100:
        raise ValueError("not enough price history")
    m = series_metrics(pts)
    year = [v for d, v in pts if d >= pts[-1][0] - timedelta(days=365)]
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        info = {}
    roe, de, dy = info.get("returnOnEquity"), info.get("debtToEquity"), info.get("trailingAnnualDividendYield")
    vol = m.get("volatility")
    m.update(kind="stock", name=name, symbol=symbol, category=info.get("sector") or "Stock",
             risk="Moderate" if vol is not None and vol < 25 else "High", min_horizon=3, min_sip=0,
             high52=round(max(year), 2), low52=round(min(year), 2), pe=info.get("trailingPE"),
             pb=info.get("priceToBook"), eps=info.get("trailingEps"), market_cap=info.get("marketCap"),
             roe=roe * 100 if roe is not None else None, debt_equity=de / 100 if de is not None else None,
             div_yield=dy * 100 if dy is not None else None, beta=info.get("beta"))
    return "stock:" + symbol, m


def build_index(name, symbol, group="Other"):
    pts = yf_points(symbol, "2y")
    if len(pts) < 30:
        raise ValueError("not enough price history")
    m = series_metrics(pts)
    m.update(kind="index", name=name, symbol=symbol, group=group, day_change=round((pts[-1][1] / pts[-2][1] - 1) * 100, 2))
    return "index:" + symbol, m


def _news_item(n):
    c = n.get("content") or n
    link = (c.get("canonicalUrl") or {}).get("url") or (c.get("clickThroughUrl") or {}).get("url") or n.get("link")
    pub = (c.get("provider") or {}).get("displayName") or n.get("publisher") or ""
    return {"title": c.get("title"), "link": link, "publisher": pub, "date": str(c.get("pubDate") or "")[:10]}


def build_news():
    items, seen = [], set()
    for sym in ("^NSEI", "^GSPC", "GOLDBEES.NS"):
        try:
            for n in (yf.Ticker(sym).news or [])[:6]:
                it = _news_item(n)
                if it["title"] and it["link"] and it["title"] not in seen:
                    seen.add(it["title"])
                    items.append(it)
        except Exception:
            continue
    if not items:
        raise ValueError("no news found")
    return "news:market", {"kind": "news", "items": items[:10]}


def refresh_all():
    """Returns (results dict key->data, list of names that failed)."""
    tasks, errors = [], []
    for a in MF_WATCHLIST:
        tasks.append((a[0], build_mf, a))
    if HAVE_YF:
        for a in STOCKS:
            tasks.append((a[0], build_stock, a))
        for a in INDICES:
            tasks.append((a[0], build_index, a))
        tasks.append(("market news", build_news, ()))
    else:
        errors.append("stocks and indices (run: pip install yfinance)")

    def run(t):
        try:
            return t[0], t[1](*t[2]), None
        except Exception as e:
            return t[0], None, str(e)

    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for name, res, err in ex.map(run, tasks):
            if res:
                results[res[0]] = res[1]
            else:
                errors.append(name)
    return results, errors
