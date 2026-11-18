"""Builds the SIPS plan PDF (approved design: navy header, progress bar, key figures, tables, disclaimer)."""
from datetime import datetime
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, KeepTogether

NAVY, BLUE = colors.HexColor("#101d35"), colors.HexColor("#3986f6")
BG, LINE, MUTED, TEXT, GOLD = colors.HexColor("#f3f6fc"), colors.HexColor("#dce4f2"), colors.HexColor("#5a6b85"), colors.HexColor("#202b3c"), colors.HexColor("#e8b04a")
HEAD, ICE = colors.HexColor("#eaf0fb"), colors.HexColor("#b9c6e0")
W, H = A4
M = 40
CW = W - 2 * M
KIND = {"mf": "Mutual fund", "stock": "Stock", "sample": "Sample"}


def inr(v):
    return "Rs {:,.0f}".format(v)


def pc(v):
    return "n/a" if v is None else "%.1f%%" % v


def P(t, size=9.5, color=TEXT, bold=False, align=0):
    return Paragraph(t, ParagraphStyle("p", fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                                       textColor=color, leading=size * 1.35, alignment=align))


def indicators(f):
    if f.get("kind") == "stock":
        pe, roe, de = f.get("pe"), f.get("roe"), f.get("debt_equity")
        return "P/E %s, ROE %s, debt to equity %s" % ("n/a" if pe is None else "%.1f" % pe, pc(roe), "n/a" if de is None else "%.1f" % de)
    if f.get("kind") == "mf":
        return "Volatility %s, biggest fall %s" % (pc(f.get("volatility")), pc(f.get("max_drawdown")))
    return "Sample category"


def grid(rows, widths, head=True, extra=None):
    t = Table(rows, colWidths=widths)
    st = [("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 8)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), HEAD))
    t.setStyle(TableStyle(st + (extra or [])))
    return t


def heading(t):
    return [Spacer(1, 12), P(t, 12, NAVY, True), Spacer(1, 5)]


def render(buf, user, r, icon_path, items=None):
    def page(c, doc):
        c.saveState()
        c.setFillColor(NAVY); c.rect(0, H - 78, W, 78, stroke=0, fill=1)
        c.setFillColor(BLUE); c.rect(0, H - 81, W, 3, stroke=0, fill=1)
        try:
            c.drawImage(icon_path, M, H - 66, 44, 44, mask="auto")
        except Exception:
            pass
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 19); c.drawString(M + 54, H - 42, "SIPS")
        c.setFillColor(ICE); c.setFont("Helvetica", 8.5); c.drawString(M + 54, H - 57, "Systematic Investment Planner for Students")
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12); c.drawRightString(W - M, H - 40, "Investment plan")
        c.setFillColor(ICE); c.setFont("Helvetica", 8.5); c.drawRightString(W - M, H - 55, datetime.now().strftime("%d %B %Y").lstrip("0"))
        c.setStrokeColor(LINE); c.setLineWidth(0.8); c.line(M, 42, W - M, 42)
        c.setFillColor(MUTED); c.setFont("Helvetica", 7.5)
        c.drawString(M, 30, "SIPS - Systematic Investment Planner for Students. Educational guide only, not financial advice.")
        c.drawRightString(W - M, 30, "Page %d" % doc.page)
        c.restoreState()

    doc = BaseDocTemplate(buf, pagesize=A4, title="SIPS investment plan", author="SIPS")
    doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(M, 52, CW, H - 52 - 96, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=page)])
    pct = r["pct"]
    S = [P(escape(r["goal_name"]), 24, NAVY, True), Spacer(1, 2), P("Prepared for %s" % escape(user), 9.5, MUTED), Spacer(1, 12)]
    bar = Table([[P("%d%% of your goal is reached at this budget" % round(pct), 10, NAVY, True), P("Target %s" % inr(r["goal"]), 9, MUTED, align=2)]], colWidths=[CW * .7, CW * .3])
    bar.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    widths = [CW * pct / 100, CW * (100 - pct) / 100] if pct < 100 else [CW, 0.01]
    track = Table([["", ""]], colWidths=widths, rowHeights=[11])
    track.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), BLUE), ("BACKGROUND", (1, 0), (1, 0), LINE), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    S += [bar, track, Spacer(1, 12)]
    tile = lambda a, b: [P(a, 8.5, MUTED), Spacer(1, 2), P(b, 16, NAVY, True)]
    tiles = Table([[tile("SIP needed for goal", inr(r["needed"]) + " a month"), tile("You invest", inr(r["invested"])), tile("Projected value", inr(r["projected"]))]], colWidths=[CW / 3] * 3)
    tiles.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BG), ("BOX", (0, 0), (-1, -1), 0.5, LINE), ("LINEAFTER", (0, 0), (1, 0), 0.5, LINE),
                               ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("LEFTPADDING", (0, 0), (-1, -1), 12)]))
    S += [tiles] + heading("Plan details")
    d = [["Goal", escape(r["goal_name"]), "Goal type", escape(r.get("goal_type", "Other"))],
         ["Target amount", inr(r["goal"]), "Monthly budget", inr(r["monthly"])],
         ["Time to goal", "%g years" % r["years"], "Risk comfort", r["risk"]],
         ["Assumed return", "%g%% a year" % r["rate"], "Preference", escape(r.get("preference", "Both"))]]
    S += [grid([[P(a, 9, MUTED), P(b, 9, NAVY, True), P(c_, 9, MUTED), P(e, 9, NAVY, True)] for a, b, c_, e in d],
               [CW * .22, CW * .28, CW * .25, CW * .25], head=False, extra=[("BACKGROUND", (0, 0), (0, -1), BG), ("BACKGROUND", (2, 0), (2, -1), BG)])]
    S += heading("What if returns are different?")
    rows = [[P("Assumed return a year", 9, NAVY, True), P("Projected value", 9, NAVY, True), P("Share of goal", 9, NAVY, True)]]
    for rt, v in r["scenarios"]:
        base = rt == r["rate"]
        rows.append([P("%g%%%s" % (rt, " (used in this plan)" if base else ""), 9), P(inr(v), 9, NAVY, base), P("%d%%" % round(v / r["goal"] * 100), 9, NAVY, base)])
    S += [grid(rows, [CW * .4, CW * .3, CW * .3], extra=[("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#e8f1ff"))])]
    h = lambda t: P(t, 8.5, NAVY, True)
    if items:
        S += heading("Your funds and stocks")
        fr = [[h("Name"), h("Type"), h("Allocation"), h("Monthly"), h("1Y"), h("3Y a year"), h("Key indicators")]]
        total = 0
        for f in items:
            total += f["alloc"]
            fr.append([P(escape(f["name"]), 9, NAVY, True), P(KIND.get(f["kind"], ""), 9), P("%g%%" % f["alloc"], 9, NAVY, True),
                       P(inr(r["monthly"] * f["alloc"] / 100), 9), P(pc(f.get("r1")), 9), P(pc(f.get("r3")), 9), P(escape(indicators(f)), 8)])
        fr.append([P("Total", 9, NAVY, True), "", P("%g%%" % total, 9, NAVY, True), P(inr(r["monthly"] * total / 100), 9, NAVY, True), "", "", ""])
        S += [grid(fr, [CW * .23, CW * .11, CW * .13, CW * .11, CW * .08, CW * .09, CW * .25],
                   extra=[("BACKGROUND", (0, len(fr) - 1), (-1, len(fr) - 1), BG)]), Spacer(1, 3)]
        note = "Proposed allocations of your monthly budget." if abs(total - 100) < 0.001 else "Allocations total %g%%. A complete plan allocates 100%%." % total
        S += [P(note, 8, MUTED), Spacer(1, 14)]
    else:
        S += heading("Funds and stocks that fit this plan")
        fr = [[h("Name"), h("Type"), h("Risk"), h("1Y"), h("3Y a year"), h("Key indicators")]]
        for f in r["funds"]:
            fr.append([P(escape(f["name"]), 9, NAVY, True), P(KIND.get(f["kind"], ""), 9), P(f["risk"], 9), P(pc(f["r1"]), 9), P(pc(f["r3"]), 9), P(escape(indicators(f)), 8.5, MUTED)])
        if len(fr) == 1:
            fr.append([P("No fund or stock fits this budget and time frame.", 9, MUTED), "", "", "", "", ""])
        S += [grid(fr, [CW * .26, CW * .12, CW * .13, CW * .09, CW * .11, CW * .29]), Spacer(1, 3),
              P("Ranked by 3-year return. Figures come from AMFI and Yahoo Finance when live data is loaded.", 8, MUTED), Spacer(1, 14)]
    disc = Table([[P("<b>Please note:</b> SIPS is an educational guide. It does not buy or sell anything and is not financial advice. Projections use assumed returns and are not guaranteed. Past returns do not guarantee future returns.", 8.8, colors.HexColor("#5b3a05"))]], colWidths=[CW])
    disc.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff6e0")), ("LINEBEFORE", (0, 0), (0, 0), 3, GOLD),
                              ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 12)]))
    S += [KeepTogether([disc])]
    doc.build(S)
