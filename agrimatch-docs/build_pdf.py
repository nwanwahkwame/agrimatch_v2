"""Convert DATA_SCIENCE_TECHNICAL_BRIEF.md to a styled PDF using ReportLab."""

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
MD   = BASE / "DATA_SCIENCE_TECHNICAL_BRIEF.md"
OUT  = BASE / "AgriMatch_DataScience_Technical_Brief.pdf"

# ── Colour palette ────────────────────────────────────────────────────────────
GREEN_DARK   = colors.HexColor("#1a5c38")
GREEN_MID    = colors.HexColor("#2e7d52")
GREEN_LIGHT  = colors.HexColor("#e8f5ee")
GREY_LINE    = colors.HexColor("#cccccc")
GREY_TEXT    = colors.HexColor("#444444")
CODE_BG      = colors.HexColor("#f4f4f4")
WHITE        = colors.white
TABLE_HEADER = colors.HexColor("#2e7d52")
TABLE_ALT    = colors.HexColor("#f0f8f4")

# ── Styles ────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

S = {
    "title": ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=28,
        textColor=WHITE,
        alignment=TA_CENTER,
        spaceAfter=6,
    ),
    "subtitle": ParagraphStyle(
        "DocSubtitle",
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#c8e6d4"),
        alignment=TA_CENTER,
        spaceAfter=0,
    ),
    "h1": ParagraphStyle(
        "H1",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=20,
        textColor=GREEN_DARK,
        spaceBefore=18,
        spaceAfter=6,
        borderPad=4,
    ),
    "h2": ParagraphStyle(
        "H2",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=GREEN_MID,
        spaceBefore=14,
        spaceAfter=4,
    ),
    "h3": ParagraphStyle(
        "H3",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=GREY_TEXT,
        spaceBefore=10,
        spaceAfter=2,
    ),
    "body": ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=GREY_TEXT,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    ),
    "bullet": ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=GREY_TEXT,
        leftIndent=14,
        spaceAfter=3,
    ),
    "sub_bullet": ParagraphStyle(
        "SubBullet",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=GREY_TEXT,
        leftIndent=28,
        spaceAfter=2,
    ),
    "code": ParagraphStyle(
        "Code",
        fontName="Courier",
        fontSize=8,
        leading=12,
        textColor=colors.HexColor("#1a1a2e"),
        backColor=CODE_BG,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=4,
        spaceAfter=4,
        borderPad=5,
    ),
    "table_header": ParagraphStyle(
        "TH",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=WHITE,
        alignment=TA_CENTER,
    ),
    "table_cell": ParagraphStyle(
        "TC",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=GREY_TEXT,
    ),
    "note": ParagraphStyle(
        "Note",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#666666"),
        spaceAfter=4,
    ),
}


# ── Page template ─────────────────────────────────────────────────────────────
def _header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4

    # Header bar
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(0, h - 1.1 * cm, w, 1.1 * cm, fill=True, stroke=False)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(1.5 * cm, h - 0.72 * cm, "AgriMatch — Data Science Technical Brief")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 1.5 * cm, h - 0.72 * cm, "Confidential · Presentation Reference")

    # Footer bar
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(0, 0, w, 0.9 * cm, fill=True, stroke=False)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.5 * cm, 0.3 * cm, "AgriMatch Agricultural Market Platform · Ghana")
    canvas.drawRightString(w - 1.5 * cm, 0.3 * cm, f"Page {doc.page}")

    canvas.restoreState()


# ── Cover page ────────────────────────────────────────────────────────────────
def _cover():
    w, h = A4
    elems = []

    # Green hero block
    cover_table = Table(
        [[Paragraph("AgriMatch", S["title"]),
          Paragraph("Data Science Technical Brief", S["subtitle"]),
          Paragraph("For Presentation Panel — Complete Model &amp; Algorithm Reference", S["subtitle"])]],
        colWidths=[w - 4 * cm],
    )
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), GREEN_DARK),
        ("TOPPADDING",  (0, 0), (-1, -1), 30),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 30),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elems.append(Spacer(1, 3 * cm))
    elems.append(cover_table)
    elems.append(Spacer(1, 1 * cm))

    meta = [
        ["Document Type", "Technical Reference Brief"],
        ["Audience",      "Data Science Presentation Panel"],
        ["Project",       "AgriMatch — Ghana Agricultural Market Platform"],
        ["Components",    "12 Data Science Models & Pipelines"],
        ["Coverage",      "Algorithms · Formulas · Connections · Panel Q&A"],
    ]
    mt = Table(meta, colWidths=[5 * cm, 11 * cm])
    mt.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",     (0, 0), (0, -1), GREEN_DARK),
        ("TEXTCOLOR",     (1, 0), (1, -1), GREY_TEXT),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.5, GREY_LINE),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]))
    elems.append(mt)
    elems.append(PageBreak())
    return elems


# ── Markdown parser → ReportLab flowables ────────────────────────────────────
def _escape(text):
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _inline(text):
    """Convert inline markdown (bold, code, italic) to ReportLab markup."""
    # Bold: **text**
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Italic: *text*
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # Inline code: `text`
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" color="#1a1a2e">\1</font>', text)
    return text


def _table_from_md(lines):
    """Parse a markdown pipe-table into a ReportLab Table."""
    rows = []
    for line in lines:
        line = line.strip().strip("|")
        if re.match(r'^[\s\-|:]+$', line):
            continue  # separator row
        cells = [c.strip() for c in line.split("|")]
        rows.append(cells)
    if not rows:
        return None

    col_count = max(len(r) for r in rows)
    page_w = A4[0] - 4 * cm
    col_w = page_w / col_count

    table_data = []
    for i, row in enumerate(rows):
        while len(row) < col_count:
            row.append("")
        style = S["table_header"] if i == 0 else S["table_cell"]
        table_data.append([Paragraph(_inline(_escape(c)), style) for c in row])

    t = Table(table_data, colWidths=[col_w] * col_count, repeatRows=1)
    row_count = len(table_data)
    ts = TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),        TABLE_HEADER),
        ("TEXTCOLOR",     (0, 0), (-1, 0),        WHITE),
        ("FONTNAME",      (0, 0), (-1, 0),        "Helvetica-Bold"),
        ("ALIGN",         (0, 0), (-1, -1),       "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1),       "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1),       5),
        ("BOTTOMPADDING", (0, 0), (-1, -1),       5),
        ("LEFTPADDING",   (0, 0), (-1, -1),       6),
        ("RIGHTPADDING",  (0, 0), (-1, -1),       6),
        ("GRID",          (0, 0), (-1, -1),       0.4, GREY_LINE),
    ])
    for r in range(1, row_count):
        if r % 2 == 0:
            ts.add("BACKGROUND", (0, r), (-1, r), TABLE_ALT)
    t.setStyle(ts)
    return t


def _parse_md(md_text):
    elems = []
    lines = md_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # --- Blank line ---
        if not line.strip():
            i += 1
            continue

        # --- Horizontal rule ---
        if re.match(r'^---+$', line.strip()):
            elems.append(HRFlowable(width="100%", thickness=1, color=GREEN_MID, spaceAfter=6))
            i += 1
            continue

        # --- Headings ---
        m = re.match(r'^(#{1,4})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            text  = _inline(_escape(m.group(2)))
            if level == 1:
                elems.append(Spacer(1, 0.3 * cm))
                elems.append(HRFlowable(width="100%", thickness=2, color=GREEN_DARK, spaceAfter=2))
                elems.append(Paragraph(text, S["h1"]))
                elems.append(HRFlowable(width="100%", thickness=0.5, color=GREEN_MID, spaceAfter=4))
            elif level == 2:
                elems.append(Paragraph(text, S["h2"]))
            elif level == 3:
                elems.append(Paragraph(text, S["h3"]))
            else:
                elems.append(Paragraph(text, S["h3"]))
            i += 1
            continue

        # --- Fenced code block ---
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(_escape(lines[i]))
                i += 1
            i += 1  # skip closing ```
            code_text = "<br/>".join(code_lines) if code_lines else " "
            elems.append(Paragraph(code_text, S["code"]))
            continue

        # --- Pipe table ---
        if "|" in line and line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            t = _table_from_md(table_lines)
            if t:
                elems.append(Spacer(1, 0.2 * cm))
                elems.append(t)
                elems.append(Spacer(1, 0.2 * cm))
            continue

        # --- Bullet (- or *)  ---
        m_b = re.match(r'^(\s*)([-*])\s+(.*)', line)
        if m_b:
            indent = len(m_b.group(1))
            text   = _inline(_escape(m_b.group(3)))
            style  = S["sub_bullet"] if indent >= 4 else S["bullet"]
            prefix = "&#8226; " if indent < 4 else "&#8250; "
            elems.append(Paragraph(prefix + text, style))
            i += 1
            continue

        # --- Numbered list ---
        m_n = re.match(r'^\s*\d+\.\s+(.*)', line)
        if m_n:
            text = _inline(_escape(m_n.group(1)))
            elems.append(Paragraph("&#8226; " + text, S["bullet"]))
            i += 1
            continue

        # --- Italic-only line (notes) ---
        if line.strip().startswith("*") and line.strip().endswith("*") and not line.strip().startswith("**"):
            text = _inline(_escape(line.strip()))
            elems.append(Paragraph(text, S["note"]))
            i += 1
            continue

        # --- Regular paragraph ---
        text = _inline(_escape(line.strip()))
        if text:
            elems.append(Paragraph(text, S["body"]))
        i += 1

    return elems


# ── Build PDF ─────────────────────────────────────────────────────────────────
def build():
    md_text = MD.read_text(encoding="utf-8")

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=1.5 * cm,
        title="AgriMatch Data Science Technical Brief",
        author="AgriMatch Engineering",
        subject="Data Science Models & Algorithms",
    )

    story = []
    story.extend(_cover())
    story.extend(_parse_md(md_text))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    print(f"PDF written: {OUT}")


if __name__ == "__main__":
    build()
