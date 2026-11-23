import io
from datetime import datetime

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

NAVY, INK, MUTED, TEAL, LINE, AMBER = (HexColor(c) for c in ("#14263d", "#142033", "#5b6676", "#1f6f7f", "#dfe4ea", "#8a5a00"))
W, H = A4
M = 42


def _dt(s):
    if not s:
        return "—"
    return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")


def _php(n):
    return f"PHP {n:,.2f}"


def _label(c, x, y, text):
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(TEAL)
    c.drawString(x, y, text.upper())


def _kv(c, x, y, key, value, width, mono=False):
    c.setFont("Helvetica", 8)
    c.setFillColor(MUTED)
    c.drawString(x, y, key)
    font = "Courier" if mono else "Helvetica-Bold"
    c.setFont(font, 8.5)
    c.setFillColor(INK)
    text, avail = str(value), width - 95
    if mono:
        n = max(10, int(avail / (0.6 * 8.5)))
        lines = [text[i:i + n] for i in range(0, len(text), n)] or [""]
    else:
        lines = simpleSplit(text, font, 8.5, avail)
    for i, ln in enumerate(lines):
        c.drawString(x + 95, y - i * 11, ln)
    return y - max(1, len(lines)) * 11 - 5


def _qr(c, url, x, y, size):
    w = QrCodeWidget(url)
    b = w.getBounds()
    d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
    d.add(w)
    renderPDF.draw(d, c, x, y)


def build_pitch_pdf(ws: dict, kpis: dict, payment: dict, expense: dict | None, duration: int | None, explorer: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("AGOS Pitch Summary")
    st = payment["stellar"]
    v = st.get("verification") or {}

    c.setFillColor(NAVY)
    c.rect(0, H - 118, W, 118, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(M, H - 44, "A G O S")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(HexColor("#9fdbe6"))
    c.drawString(M + 62, H - 43, "Business Finance in Motion  ·  ISLA Ventures Inc.")
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Helvetica-Bold", 19)
    took = f" in {duration // 60}:{duration % 60:02d}" if duration else ""
    c.drawString(M, H - 80, f"From expense to verified settlement{took}")
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#c9d3df"))
    c.drawString(M, H - 98, f"Investor tour summary  ·  {ws['name']}, {ws.get('location', '')}  ·  generated {_dt(v.get('checked_at') or st.get('confirmed_at'))}")

    y = H - 150
    _label(c, M, y, "Business snapshot · synthetic demo data")
    y -= 14
    boxes = [("Recorded expenses", _php(kpis["total_recorded"])), ("This month", _php(kpis["month_spend"])),
             ("Budget utilization", f"{round(kpis['budget_used'] / kpis['budget_total'] * 100) if kpis['budget_total'] else 0}%"),
             ("Pending approvals", str(kpis["pending_approvals"]))]
    bw = (W - 2 * M - 30) / 4
    for i, (k, val) in enumerate(boxes):
        bx = M + i * (bw + 10)
        c.setStrokeColor(LINE)
        c.roundRect(bx, y - 44, bw, 44, 6, stroke=1, fill=0)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUTED)
        c.drawString(bx + 9, y - 14, k)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(INK)
        c.drawString(bx + 9, y - 33, val)
    y -= 72

    _label(c, M, y, "What happened")
    y -= 16
    steps = []
    if expense:
        appr = next((h for h in reversed(expense["history"]) if h["status"] == "approved"), None)
        steps.append(("Expense submitted", f"{expense['merchant']} · {_php(expense['amount_php'])} · {expense['member_name']} ({expense['department']})", _dt(expense["history"][0]["at"])))
        if appr:
            steps.append(("Expense approved", f"by {appr['actor_name']} · counted in {expense['department']} budget", _dt(appr["at"])))
    reqd = payment["history"][0]
    steps.append(("Payment requested", f"{payment['amount']:g} XLM to {payment['recipient_name']}", _dt(reqd["at"])))
    papp = next((h for h in payment["history"] if h["status"] == "approved"), None)
    if papp:
        steps.append(("Payment approved", f"by {papp['actor_name']}", _dt(papp["at"])))
    steps.append(("Signed & submitted", "AGOS-managed key" if st.get("signing") != "wallet" else "Signed in connected Freighter wallet", _dt(st.get("submitted_at"))))
    steps.append(("Confirmed on ledger", f"Stellar Testnet ledger {st.get('ledger')}", _dt(st.get("confirmed_at"))))
    for i, (t, d, when) in enumerate(steps):
        c.setFillColor(TEAL)
        c.circle(M + 5, y + 3, 3.2, stroke=0, fill=1)
        if i < len(steps) - 1:
            c.setStrokeColor(LINE)
            c.line(M + 5, y - 1, M + 5, y - 23)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(M + 18, y, t)
        c.setFont("Helvetica", 8.5)
        c.setFillColor(MUTED)
        c.drawString(M + 140, y, d[:80])
        c.drawRightString(W - M, y, when)
        y -= 26
    y -= 8

    _label(c, M, y, "Verified Stellar Testnet transaction")
    y -= 10
    box_top = y
    c.setFillColor(HexColor("#f1f8fa"))
    c.setStrokeColor(HexColor("#bfe3ea"))
    c.roundRect(M, y - 196, W - 2 * M, 196, 8, stroke=1, fill=1)
    qr = 120
    _qr(c, explorer, W - M - qr - 14, y - qr - 14, qr)
    c.setFont("Helvetica", 7)
    c.setFillColor(MUTED)
    c.drawCentredString(W - M - qr / 2 - 14, y - qr - 26, "Scan to verify on stellar.expert")
    inner = W - 2 * M - qr - 44
    yy = y - 18
    for k, val, mono in [("Transaction hash", st["tx_hash"], True), ("Ledger", st.get("ledger"), False),
                         ("Network", "Stellar Testnet", False), ("Amount", f"{st.get('amount')} XLM (native)", False),
                         ("Source", st.get("source"), True), ("Destination", st.get("destination"), True),
                         ("Confirmed", _dt(st.get("confirmed_at")), False),
                         ("Verified via Horizon", f"{_dt(v.get('checked_at'))} · {'successful, matches the approved request' if v.get('successful') and v.get('matches_request') else 'see explorer'}", False)]:
        yy = _kv(c, M + 14, yy, k, val, inner, mono)
    y = box_top - 208
    c.setFont("Helvetica", 7.5)
    c.setFillColor(TEAL)
    c.drawString(M, y, explorer)
    c.linkURL(explorer, (M, y - 2, W - M, y + 9))

    y -= 26
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(M, y, "IMPORTANT")
    c.setFont("Helvetica", 7.3)
    c.setFillColor(MUTED)
    notes = ("Business figures, employees and cards are synthetic demo data; cards and domestic payments are simulated. "
             "The Stellar transaction is a genuine Testnet record; Testnet XLM has no monetary value, and ledger confirmation does not prove "
             "fiat delivery to a beneficiary. AGOS is an MVP in development under ISLA Ventures Inc. and is not a bank, lender, payment "
             "institution, electronic money issuer or virtual asset service provider. AGOS is not affiliated with or endorsed by the Stellar "
             "Development Foundation. Roadmap timelines are targets, not commitments.")
    for ln in simpleSplit(notes, "Helvetica", 7.3, W - 2 * M):
        y -= 10
        c.drawString(M, y, ln)
    c.showPage()
    c.save()
    return buf.getvalue()
