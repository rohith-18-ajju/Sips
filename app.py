"""SIPS - Systematic Investment Planner for Students.
Educational guide only. No transactions, no financial advice."""
import json, os, sqlite3
from datetime import datetime
from functools import wraps
from io import BytesIO
from flask import (Flask, render_template, request, redirect, url_for, session, flash, g,
                   send_file, abort, send_from_directory)
from jinja2 import Undefined
from werkzeug.security import generate_password_hash, check_password_hash
import market
import plan_pdf as pdfgen

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-before-submission")
DB = "sips.db"

RISK_RANK = {"Low": 1, "Moderate": 2, "High": 3}
ASSUMED_RETURN = {"Low": 6.0, "Moderate": 10.0, "High": 12.0}  # illustrative, used only for projections
GOAL_TYPES = ["Education", "Gadget or device", "Travel", "Emergency fund", "Starting a business", "Other"]
PREFS = ["Both", "Mutual funds", "Stocks"]
GROUP_ORDER = ["Indian indices", "International indices", "Gold, silver and currency"]
GMAP = {s: g for _, s, g in market.INDICES}

# SAMPLE category data, used only until live data is refreshed
SEED_FUNDS = [
    ("Liquid Fund (sample)", "Liquid", "Low", 0, 0.25, 500, 6.8, 6.2, 5.5),
    ("Short Duration Debt Fund (sample)", "Debt", "Low", 1, 0.55, 500, 7.1, 6.6, 6.9),
    ("Conservative Hybrid Fund (sample)", "Hybrid", "Moderate", 3, 0.90, 500, 9.0, 8.1, 8.4),
    ("Balanced Advantage Fund (sample)", "Hybrid", "Moderate", 3, 0.75, 500, 11.2, 10.4, 10.9),
    ("Nifty 50 Index Fund (sample)", "Index", "Moderate", 5, 0.20, 500, 13.5, 14.1, 13.2),
    ("Flexi Cap Fund (sample)", "Equity", "High", 5, 0.80, 500, 15.0, 15.6, 14.2),
    ("Mid Cap Fund (sample)", "Equity", "High", 7, 0.85, 1000, 19.0, 20.2, 17.5),
    ("Gold ETF Fund of Fund (sample)", "Gold", "Moderate", 3, 0.50, 500, 21.0, 14.3, 12.1),
]

GLOSSARY = [  # category, term, meaning, example
    ("Basics", "SIP (Systematic Investment Plan)", "Investing a fixed amount at regular intervals, usually monthly, instead of all at once.", "Putting Rs 1,000 into a fund on the 5th of every month."),
    ("Basics", "Compounding", "Earning returns on your earlier returns. The longer you stay invested, the bigger this effect becomes.", "Rs 1,000 growing 10% a year becomes about Rs 2,594 in 10 years, not Rs 2,000."),
    ("Basics", "Inflation", "The yearly rise in prices. Investments need to grow faster than inflation to gain real buying power.", "A Rs 100 snack costing Rs 106 next year means 6% inflation."),
    ("Basics", "Liquidity", "How quickly you can turn an investment into cash without losing value.", "Money in a savings account is more liquid than a fixed deposit."),
    ("Basics", "Lump sum", "Investing one large amount at once, as opposed to a SIP.", "Investing Rs 12,000 in one go instead of Rs 1,000 a month."),
    ("Basics", "Portfolio", "The full collection of your investments.", "Two mutual funds, one stock and some gold make one portfolio."),
    ("Mutual funds", "Mutual fund", "A pool of money from many investors, managed by professionals who invest it in stocks, bonds or other assets.", "Hundreds of students each add Rs 500 and a manager buys shares with the total."),
    ("Mutual funds", "NAV (Net Asset Value)", "The price of one unit of a mutual fund. It is updated at the end of each trading day.", "If the NAV is Rs 50, Rs 1,000 buys 20 units."),
    ("Mutual funds", "Expense ratio", "The yearly fee a fund charges, as a percentage of your money. Lower fees leave more returns for you.", "A 1% expense ratio costs Rs 100 a year on Rs 10,000."),
    ("Mutual funds", "Exit load", "A fee some funds charge if you withdraw before a set period.", "A 1% exit load if you sell within one year."),
    ("Mutual funds", "Equity fund", "A fund that invests mainly in company shares. It can grow faster but its value swings more.", "A flexi cap fund holding shares of many companies."),
    ("Mutual funds", "Debt fund", "A fund that invests in loans and bonds. It is usually steadier than equity with lower returns.", "A liquid fund lending money to companies for a few days."),
    ("Mutual funds", "Hybrid fund", "A fund that mixes equity and debt to balance growth and stability.", "A balanced advantage fund shifting between shares and bonds."),
    ("Mutual funds", "Index fund", "A fund that copies a market index instead of picking stocks. It usually has low fees.", "A Nifty 50 index fund holds the same 50 companies as the index."),
    ("Mutual funds", "ETF (Exchange Traded Fund)", "A fund that trades on the stock exchange like a share.", "Gold ETFs such as GOLDBEES track the price of gold."),
    ("Mutual funds", "Rupee cost averaging", "Because a SIP invests every month, you buy more units when prices are low and fewer when prices are high.", "At NAV 50 you get 20 units for Rs 1,000. At NAV 40 you get 25."),
    ("Stocks", "P/E ratio", "The share price divided by yearly profit per share. A high P/E means investors pay more for each rupee of profit.", "A Rs 500 share earning Rs 20 a year has a P/E of 25."),
    ("Stocks", "EPS (Earnings per share)", "The profit a company earns for each share.", "Rs 10,000 crore profit over 1,000 crore shares is Rs 10 EPS."),
    ("Stocks", "P/B ratio", "Compares the share price to the company's net worth per share.", "A P/B of 3 means the market values the company at three times its book value."),
    ("Stocks", "Market capitalisation", "The total value of a company's shares: share price times number of shares.", "Large caps are the biggest companies, such as those in the Nifty 50."),
    ("Stocks", "Dividend", "A share of profit paid out to investors by a company or a fund.", "A Rs 5 dividend on 100 shares pays you Rs 500."),
    ("Stocks", "ROE (Return on equity)", "How well a company turns shareholders' money into profit.", "An ROE of 18% means Rs 18 profit for every Rs 100 of shareholder money."),
    ("Stocks", "Debt to equity", "How much a company borrows compared with its own money. It is not very meaningful for banks.", "A ratio of 0.5 means Rs 50 of debt for every Rs 100 of equity."),
    ("Stocks", "Beta", "How much a stock tends to move compared with the market. Above 1 means bigger swings.", "A beta of 1.3 means a 10% market fall often brings a 13% fall."),
    ("Risk and returns", "CAGR", "Compound annual growth rate: the steady yearly rate that turns your starting amount into the final amount.", "Rs 10,000 becoming Rs 14,641 in 4 years is a 10% CAGR."),
    ("Risk and returns", "Risk", "How much the value of an investment can rise and fall, including the chance of losing money.", "A mid cap fund usually has more risk than a liquid fund."),
    ("Risk and returns", "Volatility", "How much the price moves up and down over a year.", "A volatility of 20% means typical yearly swings of around 20%."),
    ("Risk and returns", "Maximum drawdown", "The largest fall from a peak to a low point over a period.", "A fall from Rs 100 to Rs 70 is a 30% drawdown."),
    ("Risk and returns", "Diversification", "Spreading money across different investments so one bad performer does not hurt you too much.", "Holding a fund, a stock and gold instead of only one stock."),
    ("Risk and returns", "Asset allocation", "How you split your money between equity, debt, gold and cash.", "60% equity, 30% debt and 10% gold."),
    ("Markets", "Index", "A basket of shares that shows how a market is doing.", "Nifty 50 tracks 50 large Indian companies. Sensex tracks 30."),
    ("Markets", "Bull and bear market", "A bull market is a period of rising prices. A bear market is a period of falling prices.", "Prices rising for many months is a bull run."),
    ("Markets", "USD/INR", "How many rupees one US dollar costs.", "At 85, one dollar costs Rs 85. A rising rate means a weaker rupee."),
]

TREND_LABELS = ["12M ago", "11M", "10M", "9M", "8M", "7M", "6M", "5M", "4M", "3M", "2M", "1M ago", "Now"]
TRENDS = {  # illustrative sample series, used only until live data is refreshed
    "Equity index (sample)": [100, 102, 99, 104, 107, 105, 109, 112, 108, 114, 117, 119, 121],
    "Gold (sample)": [100, 103, 105, 104, 108, 111, 114, 113, 117, 121, 124, 126, 129],
    "Debt fund (sample)": [100, 100.6, 101.2, 101.8, 102.3, 102.9, 103.5, 104.0, 104.6, 105.2, 105.8, 106.4, 107.0],
}


# ---------------- database ----------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS funds(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT, risk TEXT, min_horizon INTEGER,
        expense_ratio REAL, min_sip INTEGER, ret_1y REAL, ret_3y REAL, ret_5y REAL);
    CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, data TEXT, updated TEXT);
    CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, goal_name TEXT, goal_amount REAL,
        years REAL, monthly REAL, risk TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS plan_items(id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, asset_key TEXT, name TEXT,
        kind TEXT, alloc REAL DEFAULT 0);
    """)
    cols = {r[1] for r in db.execute("PRAGMA table_info(plans)")}
    for col, ddl in (("goal_type", "TEXT DEFAULT 'Other'"), ("preference", "TEXT DEFAULT 'Both'")):
        if col not in cols:
            db.execute("ALTER TABLE plans ADD COLUMN %s %s" % (col, ddl))
    if db.execute("SELECT COUNT(*) FROM funds").fetchone()[0] == 0:
        db.executemany("INSERT INTO funds(name,category,risk,min_horizon,expense_ratio,min_sip,ret_1y,ret_3y,ret_5y) VALUES(?,?,?,?,?,?,?,?,?)", SEED_FUNDS)
    db.commit()
    db.close()


def load_cache():
    rows = get_db().execute("SELECT key,data,updated FROM cache").fetchall()
    return {r["key"]: (json.loads(r["data"]), r["updated"]) for r in rows}


def live_assets(cache=None):
    cache = cache if cache is not None else load_cache()
    out = []
    for key, (d, _) in cache.items():
        if d.get("kind") in ("mf", "stock"):
            out.append(dict(d, key=key, live=True, r1=d.get("ret_1y"), r3=d.get("ret_3y"), r5=d.get("ret_5y"),
                            link=url_for("asset", kind=d["kind"], code=key.split(":", 1)[1])))
    return out


# ---------------- SIP maths and rule-based recommendation ----------------
def sip_future_value(monthly, annual_rate, years):
    i, n = annual_rate / 100 / 12, int(round(years * 12))
    return monthly * n if i == 0 else monthly * (((1 + i) ** n - 1) / i) * (1 + i)


def sip_needed(goal, annual_rate, years):
    return goal / sip_future_value(1, annual_rate, years)


def recommend(years, monthly, risk, preference="Both"):
    """Live funds/stocks that fit horizon, budget, risk and preference, ranked by 3-year return."""
    allowed = {"Both": ("mf", "stock"), "Mutual funds": ("mf",), "Stocks": ("stock",)}.get(preference, ("mf", "stock"))
    ok = lambda a: (a["kind"] in allowed and a["min_horizon"] <= years and a["min_sip"] <= monthly and a["r3"] is not None
                    and RISK_RANK[a["risk"]] <= RISK_RANK[risk])
    live = sorted([a for a in live_assets() if ok(a)], key=lambda a: a["r3"], reverse=True)
    mfs = [a for a in live if a["kind"] == "mf"]
    stocks = [a for a in live if a["kind"] == "stock"]
    if preference == "Both":
        picks = mfs[:2] + stocks[:1]
        for a in mfs[2:]:
            if len(picks) < 3:
                picks.append(a)
    else:
        picks = (mfs or stocks)[:3]
    if picks or preference == "Stocks":
        return picks
    rows = get_db().execute("SELECT * FROM funds").fetchall()
    fit = sorted([f for f in rows if f["min_horizon"] <= years and f["min_sip"] <= monthly and RISK_RANK[f["risk"]] <= RISK_RANK[risk]],
                 key=lambda f: f["ret_3y"], reverse=True)
    return [dict(name=f["name"], category=f["category"], risk=f["risk"], r1=f["ret_1y"], r3=f["ret_3y"], kind="sample",
                 live=False, link=url_for("fund", fid=f["id"])) for f in fit[:3]]


def build_result(d):
    rate = ASSUMED_RETURN[d["risk"]]
    scen = [(r, sip_future_value(d["monthly"], r, d["years"])) for r in (rate - 2, rate, rate + 2)]
    proj = scen[1][1]
    return {"goal_name": d["name"], "goal": d["goal"], "years": d["years"], "monthly": d["monthly"], "risk": d["risk"],
            "goal_type": d["goal_type"], "preference": d["preference"], "rate": rate,
            "needed": sip_needed(d["goal"], rate, d["years"]), "invested": d["monthly"] * d["years"] * 12,
            "scenarios": scen, "projected": proj, "on_track": proj >= d["goal"], "pct": min(100, proj / d["goal"] * 100),
            "funds": recommend(d["years"], d["monthly"], d["risk"], d["preference"])}


def parse_plan(form):
    try:
        d = {"name": form.get("goal_name", "").strip() or "My goal", "goal": float(form["goal_amount"]),
             "years": float(form["years"]), "monthly": float(form["monthly"]), "risk": form["risk"],
             "goal_type": form.get("goal_type", "Other"), "preference": form.get("preference", "Both")}
        assert d["goal"] > 0 and d["years"] > 0 and d["monthly"] > 0 and d["risk"] in RISK_RANK
        assert d["goal_type"] in GOAL_TYPES and d["preference"] in PREFS
        return d
    except (ValueError, KeyError, AssertionError):
        return None


def plan_dict(p):
    return {"name": p["goal_name"], "goal": p["goal_amount"], "years": p["years"], "monthly": p["monthly"], "risk": p["risk"],
            "goal_type": p["goal_type"] or "Other", "preference": p["preference"] or "Both"}


def login_required(view):
    @wraps(view)
    def wrapped(*a, **k):
        if "uid" not in session:
            return redirect(url_for("login"))
        return view(*a, **k)
    return wrapped


# ---------------- template helpers ----------------
def _na(v):
    return v is None or isinstance(v, Undefined)


@app.template_filter("pct")
def _pct(v):
    return "n/a" if _na(v) else "%.1f%%" % v


@app.template_filter("inr")
def _inr(v):
    return "n/a" if _na(v) else "Rs {:,.2f}".format(v)


@app.template_filter("crore")
def _crore(v):
    return "n/a" if _na(v) or not v else "Rs {:,.0f} crore".format(v / 1e7)


@app.template_filter("num")
def _num(v, d=2):
    return "n/a" if _na(v) else ("{:,.%df}" % d).format(v)


@app.context_processor
def inject_ticker():
    if "uid" not in session:
        return {}
    try:
        cache = load_cache()
    except Exception:
        return {}
    return {"ticker": [{"name": d["name"], "chg": d["day_change"]} for d, _ in cache.values()
                       if d.get("kind") == "index" and d.get("day_change") is not None]}


# ---------------- account routes ----------------
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico")


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest", mimetype="application/manifest+json")


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "uid" in session else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u, p = request.form["username"].strip(), request.form["password"]
        if len(u) < 3 or len(p) < 6:
            flash("Username needs 3+ characters and password 6+ characters.")
        else:
            try:
                get_db().execute("INSERT INTO users(username,password_hash) VALUES(?,?)", (u, generate_password_hash(p)))
                get_db().commit()
                flash("Account created. Log in to continue.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username is taken. Try another.")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = get_db().execute("SELECT * FROM users WHERE username=?", (request.form["username"].strip(),)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form["password"]):
            session["uid"], session["user"] = row["id"], row["username"]
            return redirect(url_for("dashboard"))
        flash("Username or password is incorrect.")
    return render_template("auth.html", mode="login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    n = db.execute("SELECT COUNT(*) FROM plans WHERE user_id=?", (session["uid"],)).fetchone()[0]
    last = db.execute("SELECT * FROM plans WHERE user_id=? ORDER BY id DESC LIMIT 1", (session["uid"],)).fetchone()
    cache = load_cache()
    snap = [d for d, _ in cache.values() if d.get("kind") == "index" and GMAP.get(d.get("symbol")) == "Indian indices"]
    updated = max([u for _, u in cache.values()], default=None)
    return render_template("dashboard.html", n=n, last=last, snap=snap, updated=updated)


# ---------------- planner and plan management ----------------
@app.route("/planner", methods=["GET", "POST"])
@login_required
def planner():
    result = None
    if request.method == "POST":
        d = parse_plan(request.form)
        if d:
            result = build_result(d)
        else:
            flash("Enter positive numbers for amount, years and monthly budget.")
    return render_template("planner.html", result=result, goal_types=GOAL_TYPES, prefs=PREFS)


@app.route("/plans/save", methods=["POST"])
@login_required
def save_plan():
    d = parse_plan(request.form)
    if not d:
        flash("That plan could not be saved. Check the numbers and try again.")
        return redirect(url_for("planner"))
    db = get_db()
    cur = db.execute("INSERT INTO plans(user_id,goal_name,goal_amount,years,monthly,risk,goal_type,preference) VALUES(?,?,?,?,?,?,?,?)",
                     (session["uid"], d["name"], d["goal"], d["years"], d["monthly"], d["risk"], d["goal_type"], d["preference"]))
    pid = cur.lastrowid
    picks = [f for f in recommend(d["years"], d["monthly"], d["risk"], d["preference"]) if f.get("key")]
    for i, f in enumerate(picks):
        alloc = 100 // len(picks) + (1 if i < 100 % len(picks) else 0)
        db.execute("INSERT INTO plan_items(plan_id,asset_key,name,kind,alloc) VALUES(?,?,?,?,?)", (pid, f["key"], f["name"], f["kind"], alloc))
    db.commit()
    flash("Draft saved. You can edit it here.")
    return redirect(url_for("plan_edit", pid=pid))


@app.route("/plans")
@login_required
def plans():
    rows = get_db().execute("""SELECT p.*, (SELECT COUNT(*) FROM plan_items i WHERE i.plan_id = p.id) AS n_items
                               FROM plans p WHERE user_id=? ORDER BY id DESC""", (session["uid"],)).fetchall()
    return render_template("plans.html", plans=rows)


def own_plan(pid):
    row = get_db().execute("SELECT * FROM plans WHERE id=? AND user_id=?", (pid, session["uid"])).fetchone()
    if not row:
        abort(404)
    return row


def plan_items_list(pid):
    cache, out = load_cache(), []
    for r in get_db().execute("SELECT * FROM plan_items WHERE plan_id=? ORDER BY id", (pid,)).fetchall():
        d = cache.get(r["asset_key"], ({},))[0]
        out.append(dict(d, id=r["id"], key=r["asset_key"], name=r["name"], kind=r["kind"], alloc=r["alloc"],
                        r1=d.get("ret_1y"), r3=d.get("ret_3y"),
                        link=url_for("asset", kind=r["kind"], code=r["asset_key"].split(":", 1)[1])))
    return out


@app.route("/plans/<int:pid>")
@login_required
def plan_edit(pid):
    p = own_plan(pid)
    items = plan_items_list(pid)
    have = {i["key"] for i in items}
    return render_template("plan_edit.html", p=p, items=items, result=build_result(plan_dict(p)),
                           total=sum(i["alloc"] for i in items), addable=[a for a in live_assets() if a["key"] not in have],
                           goal_types=GOAL_TYPES, prefs=PREFS)


@app.route("/plans/<int:pid>/update", methods=["POST"])
@login_required
def plan_update(pid):
    own_plan(pid)
    d = parse_plan(request.form)
    db = get_db()
    ids = [r["id"] for r in db.execute("SELECT id FROM plan_items WHERE plan_id=?", (pid,)).fetchall()]
    try:
        allocs = {i: float(request.form.get("alloc_%d" % i) or 0) for i in ids}
        assert d and all(0 <= v <= 100 for v in allocs.values())
    except (ValueError, AssertionError):
        flash("Check the numbers. Allocations must be between 0 and 100, and the plan fields must be positive.")
        return redirect(url_for("plan_edit", pid=pid))
    total = sum(allocs.values())
    if total > 100.0001:
        flash("Allocations total %g%%, which is more than 100%%. Reduce them and save again." % total)
        return redirect(url_for("plan_edit", pid=pid))
    db.execute("UPDATE plans SET goal_name=?,goal_amount=?,years=?,monthly=?,risk=?,goal_type=?,preference=? WHERE id=?",
               (d["name"], d["goal"], d["years"], d["monthly"], d["risk"], d["goal_type"], d["preference"], pid))
    for i, v in allocs.items():
        db.execute("UPDATE plan_items SET alloc=? WHERE id=?", (v, i))
    db.commit()
    flash("Draft updated. Allocations total %g%%." % total + ("" if abs(total - 100) < 0.001 else " A complete plan allocates 100%."))
    return redirect(url_for("plan_edit", pid=pid))


@app.route("/plans/<int:pid>/items/add", methods=["POST"])
@login_required
def plan_item_add(pid):
    own_plan(pid)
    key = request.form.get("asset_key", "")
    a = next((x for x in live_assets() if x["key"] == key), None)
    db = get_db()
    if not a:
        flash("Choose a fund or stock from the list.")
    elif db.execute("SELECT 1 FROM plan_items WHERE plan_id=? AND asset_key=?", (pid, key)).fetchone():
        flash("That one is already in this plan.")
    else:
        db.execute("INSERT INTO plan_items(plan_id,asset_key,name,kind,alloc) VALUES(?,?,?,?,0)", (pid, key, a["name"], a["kind"]))
        db.commit()
        flash("Added. Set its allocation and save.")
    return redirect(url_for("plan_edit", pid=pid))


@app.route("/plans/<int:pid>/items/<int:iid>/delete", methods=["POST"])
@login_required
def plan_item_remove(pid, iid):
    own_plan(pid)
    get_db().execute("DELETE FROM plan_items WHERE id=? AND plan_id=?", (iid, pid))
    get_db().commit()
    flash("Removed from this plan.")
    return redirect(url_for("plan_edit", pid=pid))


@app.route("/plans/<int:pid>/delete", methods=["POST"])
@login_required
def delete_plan(pid):
    own_plan(pid)
    get_db().execute("DELETE FROM plan_items WHERE plan_id=?", (pid,))
    get_db().execute("DELETE FROM plans WHERE id=?", (pid,))
    get_db().commit()
    flash("Draft deleted.")
    return redirect(url_for("plans"))


@app.route("/plans/<int:pid>/pdf")
@login_required
def plan_pdf(pid):
    p = own_plan(pid)
    buf = BytesIO()
    pdfgen.render(buf, session["user"], build_result(plan_dict(p)), os.path.join(app.static_folder, "icon-512.png"), plan_items_list(pid))
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name="sips_plan_%d.pdf" % pid)


# ---------------- market, funds, stocks, comparison ----------------
@app.route("/funds")
@login_required
def funds():
    sample = get_db().execute("SELECT * FROM funds ORDER BY category, name").fetchall()
    return render_template("funds.html", live=live_assets(), funds=sample)


@app.route("/fund/<int:fid>")
@login_required
def fund(fid):
    f = get_db().execute("SELECT * FROM funds WHERE id=?", (fid,)).fetchone()
    if not f:
        abort(404)
    return render_template("fund.html", f=f, growth=10000 * (1 + f["ret_5y"] / 100) ** 5)


@app.route("/asset/<kind>/<code>")
@login_required
def asset(kind, code):
    row = get_db().execute("SELECT data, updated FROM cache WHERE key=?", (kind + ":" + code,)).fetchone()
    if kind not in ("mf", "stock") or not row:
        abort(404)
    return render_template("asset.html", a=json.loads(row["data"]), updated=row["updated"], compare_key=kind + ":" + code)


@app.route("/compare")
@login_required
def compare():
    assets = live_assets()
    by_key = {a["key"]: a for a in assets}
    sel = [request.args.get(k, "") for k in ("a", "b", "c")]
    chosen = [by_key[k] for k in sel if k in by_key]
    series = {}
    for a in chosen:
        m = a.get("m13")
        if m and None not in m:
            series[a["name"]] = [round(v / m[0] * 100, 1) for v in m]
    return render_template("compare.html", assets=assets, chosen=chosen, series=series, labels=TREND_LABELS, sel=sel)


@app.route("/market")
@login_required
def market_page():
    cache = load_cache()
    order = {s: i for i, (_, s, _) in enumerate(market.INDICES)}
    items = sorted([d for d, _ in cache.values() if d.get("kind") == "index"], key=lambda d: order.get(d.get("symbol"), 99))
    for i, d in enumerate(items):
        d["idx"] = i
        d["group"] = d.get("group") or GMAP.get(d.get("symbol"), "Indian indices")
    groups = [(g_, [d for d in items if d["group"] == g_]) for g_ in GROUP_ORDER]
    updated = max([u for _, u in cache.values()], default=None)
    news = cache.get("news:market", ({"items": []},))[0].get("items", [])
    return render_template("market.html", indices=items, groups=[x for x in groups if x[1]], updated=updated,
                           assets=live_assets(cache), news=news)


@app.route("/trends")
@login_required
def trends():
    cache = load_cache()
    m13 = lambda k: cache.get(k, ({},))[0].get("m13")
    eq, gold, debt = m13("index:^NSEI"), m13("index:GOLDBEES.NS"), m13("mf:hdfc-liquid")
    live = all(x and None not in x for x in (eq, gold, debt))
    if live:
        series = {n: [round(v / x[0] * 100, 1) for v in x]
                  for n, x in (("Nifty 50 (equity)", eq), ("Gold ETF", gold), ("Liquid fund (debt)", debt))}
        note = "Live data. Each line starts at 100 twelve months ago, so you can compare how different asset types behaved."
    else:
        series = TRENDS
        note = "Illustrative sample data, each line starts at 100 twelve months ago. Open the Market page and press Refresh to load live data."
    rows = [(n, (v[-1] / v[-2] - 1) * 100, (v[-1] / v[-7] - 1) * 100, (v[-1] / v[0] - 1) * 100) for n, v in series.items()]
    return render_template("trends.html", labels=TREND_LABELS, series=series, rows=rows, note=note)


@app.route("/metals")
@login_required
def metals():
    cache = load_cache()
    return render_template("metals.html", gold=cache.get("index:GOLDBEES.NS", (None,))[0], silver=cache.get("index:SILVERBEES.NS", (None,))[0])


@app.route("/glossary")
@login_required
def glossary():
    groups = {}
    for cat, term, meaning, ex in GLOSSARY:
        groups.setdefault(cat, []).append((term, meaning, ex))
    return render_template("glossary.html", groups=groups)


@app.route("/refresh", methods=["POST"])
@login_required
def refresh():
    results, errors = market.refresh_all()
    db, now = get_db(), datetime.now().strftime("%Y-%m-%d %H:%M")
    for k, d in results.items():
        db.execute("INSERT OR REPLACE INTO cache(key,data,updated) VALUES(?,?,?)", (k, json.dumps(d), now))
    db.commit()
    msg = "Updated %d items." % len(results)
    if errors:
        msg += " Could not fetch: " + ", ".join(errors[:4]) + (" and more." if len(errors) > 4 else ".")
    flash(msg)
    return redirect(url_for("market_page"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
