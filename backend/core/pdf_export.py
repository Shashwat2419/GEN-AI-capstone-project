"""Offline PDF travel guide (ReportLab).

Currency *codes* (INR, USD, EUR...) are used instead of symbols because the
built-in PDF fonts do not contain glyphs such as the rupee sign.
"""
import io
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

from core.config import APP_NAME
from core.planner import budget_summary, day_cost_local, day_transit_km, fmt_num, to_usd_inr

TEAL = colors.HexColor("#0F766E")
SUNSET = colors.HexColor("#F97316")
SAND = colors.HexColor("#FFF7ED")
MIST = colors.HexColor("#F0FDFA")
INK = colors.HexColor("#1F2937")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], textColor=colors.white, fontSize=26, leading=30),
        "sub": ParagraphStyle("s", parent=base["Normal"], textColor=colors.white, fontSize=11, leading=15),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], textColor=TEAL, fontSize=16, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=SUNSET, fontSize=12, spaceAfter=2),
        "body": ParagraphStyle("b", parent=base["Normal"], textColor=INK, fontSize=9.5, leading=13),
        "small": ParagraphStyle("sm", parent=base["Normal"], textColor=colors.HexColor("#6B7280"),
                                fontSize=8, leading=10),
        "cell": ParagraphStyle("c", parent=base["Normal"], textColor=INK, fontSize=9, leading=11.5),
        "center": ParagraphStyle("ce", parent=base["Normal"], alignment=TA_CENTER, fontSize=8,
                                 textColor=colors.HexColor("#6B7280")),
    }


def _p(text, style):
    return Paragraph(escape(str(text)), style)


def _cost(amount_local, fx):
    if amount_local <= 0:
        return "Free"
    m = to_usd_inr(amount_local, fx)
    return "%s %s<br/><font size=7 color='#6B7280'>USD %s | INR %s</font>" % (
        fx["local"], fmt_num(m["local"]), fmt_num(m["usd"]), fmt_num(m["inr"]))


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(18 * mm, 10 * mm, "%s  -  offline travel guide" % APP_NAME)
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, "Page %d" % doc.page)
    canvas.restoreState()


def build_pdf(itin: dict) -> bytes:
    """Return the itinerary as a PDF (bytes)."""
    st = _styles()
    fx, prefs = itin["fx"], itin["prefs"]
    party = prefs["party_size"]
    summary = budget_summary(itin)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm,
                            title="%s - Travel Itinerary" % itin["destination"], author=APP_NAME)
    width = A4[0] - 36 * mm
    story = []

    # ---- cover banner
    banner = Table([[Paragraph(escape(itin["destination"]), st["title"])],
                    [Paragraph(escape("%s  |  %d days  |  %s  |  %s pace" % (
                        itin["country"], len(itin["days"]), prefs["party"], prefs["pace"])), st["sub"])],
                    [Paragraph(escape(itin["summary"]), st["sub"])]], colWidths=[width])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TEAL),
                                ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                                ("TOPPADDING", (0, 0), (0, 0), 16), ("BOTTOMPADDING", (0, -1), (-1, -1), 16),
                                ("LINEBELOW", (0, -1), (-1, -1), 4, SUNSET)]))
    story += [banner, Spacer(1, 10)]

    facts = [["Dates", "%s to %s" % (itin["days"][0]["date"], itin["days"][-1]["date"])],
             ["Travellers", "%s (%d)" % (prefs["party"], party)],
             ["Budget level", prefs["budget"]],
             ["Interests", ", ".join(prefs["interests"]) or "General"],
             ["Dietary needs", prefs["diet"]],
             ["Estimated activity + food cost", "%s %s  (USD %s | INR %s)" % (
                 fx["local"], fmt_num(summary["total_local"]), fmt_num(summary["total_usd"]),
                 fmt_num(summary["total_inr"]))],
             ["Total transit between stops", "%.1f km (clustered by area)" % summary["transit_km"]]]
    t = Table([[_p(a, st["cell"]), _p(b, st["cell"])] for a, b in facts], colWidths=[55 * mm, width - 55 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), MIST), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [t, Spacer(1, 8)]
    if itin.get("tips"):
        story.append(Paragraph("Local tips", st["h2"]))
        for tip in itin["tips"]:
            story.append(Paragraph("- " + escape(tip), st["body"]))

    # ---- days
    for day in itin["days"]:
        story.append(PageBreak())
        story.append(Paragraph("Day %d - %s" % (day["day"], escape(day["theme"])), st["h1"]))
        story.append(Paragraph("%s  |  about %.1f km between stops" % (day["date"], day_transit_km(day)), st["small"]))
        story.append(Spacer(1, 4))
        hdr = [Paragraph("<font color='white'><b>%s</b></font>" % h, st["cell"])
               for h in ("Time slot", "Plan", "Est. cost (all travellers)")]
        rows = [hdr]
        for slot in day["slots"]:
            for idx, it in enumerate(slot["items"]):
                detail = "<b>%s</b><br/>%s<br/><font size=7 color='#6B7280'>%s | ~%s h</font>" % (
                    escape(it["name"]), escape(it["description"]), escape(it["area"]), fmt_num(it["duration_hrs"]))
                rows.append([_p(slot["slot"], st["cell"]) if idx == 0 else "",
                             Paragraph(detail, st["cell"]),
                             Paragraph(_cost(it["cost_local"] * party, fx), st["cell"])])
        day_total = day_cost_local(day, party)
        rows.append(["", _p("Day total", st["cell"]), Paragraph("<b>%s</b>" % _cost(day_total, fx), st["cell"])])
        tbl = Table(rows, colWidths=[36 * mm, width - 36 * mm - 42 * mm, 42 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), TEAL),
            ("BACKGROUND", (0, -1), (-1, -1), SAND), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, MIST]),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story.append(tbl)

    # ---- budget tracker
    story += [PageBreak(), Paragraph("Running budget tracker", st["h1"])]
    head = ["Day", "Day cost (%s)" % fx["local"], "Cumulative (%s)" % fx["local"], "Cumulative USD", "Cumulative INR"]
    data = [[_p(h, st["cell"]) for h in head]]
    for r in summary["rows"]:
        data.append([_p(v, st["cell"]) for v in (r["Day"], fmt_num(r["Day cost (%s)" % fx["local"]]),
                                                  fmt_num(r["Cumulative (%s)" % fx["local"]]),
                                                  fmt_num(r["Cumulative (USD)"]), fmt_num(r["Cumulative (INR)"]))])
    bt = Table(data, repeatRows=1)
    bt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), MIST), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB"))]))
    story += [bt, Spacer(1, 4),
              Paragraph("Target for a %s budget: about USD %s (INR %s) for food and activities. "
                        "Lodging and transport to the destination are not included. Exchange rates are "
                        "approximate (1 USD = %s %s = INR %s)." % (
                            prefs["budget"].lower(), fmt_num(summary["target_usd"]), fmt_num(summary["target_inr"]),
                            fmt_num(fx["per_usd"]), fx["local"], fmt_num(fx["inr_per_usd"])), st["small"])]

    # ---- emergency + checklists
    em = itin.get("emergency") or {}
    labels = [("Police", "police"), ("Ambulance", "ambulance"), ("Fire", "fire"), ("Tourist helpline", "tourist_helpline")]
    em_rows = [[_p(l, st["cell"]), _p(em.get(k) or "Verify locally", st["cell"])] for l, k in labels]
    em_rows += [[_p("Embassy / consulate", st["cell"]), _p(em.get("embassy_note") or "Save your embassy contact before you travel.", st["cell"])],
                [_p("Hotel name & phone", st["cell"]), _p("______________________________", st["cell"])],
                [_p("Local emergency contact", st["cell"]), _p("______________________________", st["cell"])],
                [_p("Travel insurance policy #", st["cell"]), _p("______________________________", st["cell"])]]
    et = Table(em_rows, colWidths=[55 * mm, width - 55 * mm])
    et.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), SAND), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB"))]))
    story += [Spacer(1, 12), KeepTogether([Paragraph("Emergency contacts", st["h1"]), et,
              Paragraph("Numbers are provided as a convenience - please verify them before you travel.", st["small"])])]

    checklist = ["Passport / ID valid for 6+ months, plus photocopies", "Visa or e-visa approved and printed",
                 "Travel insurance purchased; policy number saved offline", "Flights, hotels and transfers confirmed",
                 "Medication, prescriptions and a basic first-aid kit", "Local SIM / eSIM or roaming plan; offline maps downloaded",
                 "Cards and some local cash; bank notified of travel", "Power adapter, chargers and power bank",
                 "Emergency numbers saved on phone and in this guide", "Share this itinerary with a trusted contact"]
    story += [Spacer(1, 12), KeepTogether([Paragraph("Pre-departure checklist", st["h1"])] +
              [Paragraph("[   ]  " + escape(c), st["body"]) for c in checklist])]
    story += [Spacer(1, 10), Paragraph("Generated on %s by %s. Opening hours, prices and availability may change; "
                                       "confirm details before visiting." % (date.today().isoformat(), APP_NAME), st["small"])]

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
