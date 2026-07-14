"""
report_helper.py
----------------
Generates a premium-quality PDF report for the Ask AI session.
Full session: all Q&A pairs, data tables, SQL queries.
"""

import os, io, re
from datetime import datetime
import pandas as pd
import numpy as np
from typing import Any, Optional, Union
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, Image, ListFlowable, ListItem, PageBreak
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Brand colours ─────────────────────────────────────────────────────────────
NAVY    = colors.HexColor("#1B3B8B")
ORANGE  = colors.HexColor("#FF6B00")
SLATE   = colors.HexColor("#475569")
SILVER  = colors.HexColor("#94A3B8")
ICE     = colors.HexColor("#F0F4FF")
MINT    = colors.HexColor("#F0FDF4")
CREAM   = colors.HexColor("#FFFBF0")
CODEBG  = colors.HexColor("#F1F5F9")
DIVIDER = colors.HexColor("#E2E8F0")
WHITE   = colors.white
BLACK   = colors.HexColor("#0F172A")

LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "tvs logo new.png")
FONT_DIR  = r"C:\Windows\Fonts"

# ── Register premium TTF fonts ────────────────────────────────────────────────
def _register_fonts():
    pairs = [
        ("Calibri",       "calibri.ttf"),
        ("Calibri-Bold",  "calibrib.ttf"),
        ("Calibri-Italic","calibrii.ttf"),
        ("Georgia",       "georgia.ttf"),
        ("Georgia-Bold",  "georgiab.ttf"),
        ("Trebuchet",     "trebuc.ttf"),
        ("Trebuchet-Bold","trebucbd.ttf"),
    ]
    registered = []
    for name, fname in pairs:
        path = os.path.join(FONT_DIR, fname)
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                registered.append(name)
            except Exception:
                pass
    # Pick body/heading pair
    body    = "Calibri"       if "Calibri"      in registered else "Helvetica"
    bodyB   = "Calibri-Bold"  if "Calibri-Bold" in registered else "Helvetica-Bold"
    bodyI   = "Calibri-Italic"if "Calibri-Italic"in registered else "Helvetica-Oblique"
    heading = "Georgia-Bold"  if "Georgia-Bold" in registered else "Helvetica-Bold"
    return body, bodyB, bodyI, heading

BODY, BODY_B, BODY_I, HEAD = _register_fonts()


# ── Markdown → ReportLab XML ──────────────────────────────────────────────────
def _md_to_rl(text: str, body_font: str, body_bold: str, body_italic: str) -> str:
    """Convert basic markdown to ReportLab Paragraph XML."""
    # Escape XML special chars first (except already-safe ones)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # **bold**
    text = re.sub(r'\*\*(.+?)\*\*', lambda m: f'<font name="{body_bold}"><b>{m.group(1)}</b></font>', text)
    # *italic*
    text = re.sub(r'\*(.+?)\*', lambda m: f'<i>{m.group(1)}</i>', text)
    # `code`
    text = re.sub(r'`(.+?)`', r'<font name="Courier" size="8">\1</font>', text)
    return text


def _split_md_paragraphs(text: str, styles: dict) -> list[Any]:
    """Split markdown text into a list of ReportLab flowables (paragraphs + bullets)."""
    flowables: list[Any] = []
    lines = text.split("\n")
    current_para = []
    bullet_items  = []

    def flush_para():
        if current_para:
            joined = " ".join(l for l in current_para if l.strip())
            if joined.strip():
                flowables.append(Paragraph(_md_to_rl(joined, BODY, BODY_B, BODY_I), styles["body"]))
            current_para.clear()

    def flush_bullets():
        if bullet_items:
            items = [
                ListItem(Paragraph(_md_to_rl(b, BODY, BODY_B, BODY_I), styles["bullet_text"]),
                         leftIndent=14, bulletColor=ORANGE)
                for b in bullet_items
            ]
            flowables.append(ListFlowable(items, bulletType="bullet",
                                          bulletFontName=BODY_B, bulletFontSize=9,
                                          leftIndent=16, spaceBefore=2, spaceAfter=2))
            bullet_items.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_para()
            flush_bullets()
            continue
        # Numbered list  "1. text" or bullet "- text" or "* text"
        if re.match(r'^[-*]\s+', stripped) or re.match(r'^\d+\.\s+', stripped):
            flush_para()
            content = re.sub(r'^[-*]\s+', '', stripped)
            content = re.sub(r'^\d+\.\s+', '', content)
            bullet_items.append(content)
        else:
            flush_bullets()
            current_para.append(stripped)

    flush_para()
    flush_bullets()
    return flowables


# ── Indian number post-processing for PDF ────────────────────────────────────
_MILLION_RE = re.compile(
    r'(?:Rs\.?|INR|₹)?\s*(\d+(?:\.\d+)?)\s*(million|billion|lakh|crore)',
    re.IGNORECASE
)

def _convert_indian_units(text: str) -> str:
    """Convert million/billion to lakh/crore in text for PDF display."""
    def replace_unit(m):
        val  = float(m.group(1))
        unit = m.group(2).lower()
        if unit == "million":
            lakh_val = val * 10
            if lakh_val >= 100:
                crore_val = lakh_val / 100
                return f"Rs.{crore_val:,.2f} Crore"
            return f"Rs.{lakh_val:,.2f} Lakh"
        elif unit == "billion":
            crore_val = val * 100
            return f"Rs.{crore_val:,.2f} Crore"
        return m.group(0)
    return _MILLION_RE.sub(replace_unit, text)


def _clean_for_pdf(text: str) -> str:
    """Final text cleanup for PDF — replace ₹ with Rs., remove Unicode issues."""
    text = _convert_indian_units(text)
    text = text.replace("₹", "Rs.")
    return text


def _to_indian_format(val: float) -> str:
    """Format a float into Indian Rupee notation: Rs.X,XX,XX,XXX.XX"""
    try:
        val = float(val)
    except (ValueError, TypeError):
        return str(val)
    if val < 0:
        return f"-{_to_indian_format(-val)}"
    integer_part = str(int(val))
    decimal_part = f"{val:.2f}".split(".")[1]
    if len(integer_part) <= 3:
        return f"Rs.{integer_part}.{decimal_part}"
    last3 = integer_part[-3:]
    rest  = integer_part[:-3]
    groups = []
    while rest:
        groups.append(rest[-2:])
        rest = rest[:-2]
    groups.reverse()
    formatted = ",".join(g for g in groups if g) + "," + last3
    return f"Rs.{formatted}.{decimal_part}"


def _humanize_col(col: str) -> str:
    """Convert snake_case column names to Title Case."""
    return col.replace("_", " ").title()


def _format_cell(val) -> str:
    """Format a cell value — detect numeric and apply Indian formatting."""
    if val is None:
        return "-"
    s = str(val).strip()
    if not s or s == "None":
        return "-"
    # Remove existing commas and Rs. prefix to detect numeric
    cleaned = s.replace(",", "").replace("Rs.", "").replace("INR", "").strip()
    try:
        num = float(cleaned)
        # Only format if looks like a currency/large number (not year or ID)
        if num > 9999 and not (1900 <= num <= 2099):
            return _to_indian_format(num)
    except ValueError:
        pass
    return s


# ── Style factory ─────────────────────────────────────────────────────────────
def _styles():
    s = {}
    s["co_name"] = ParagraphStyle("co_name", fontName=HEAD, fontSize=18,
                                   textColor=NAVY, leading=22, alignment=TA_LEFT)
    s["co_sub"]  = ParagraphStyle("co_sub",  fontName=BODY, fontSize=10,
                                   textColor=SLATE, leading=14, alignment=TA_LEFT)
    s["ts"]      = ParagraphStyle("ts", fontName=BODY, fontSize=8.5,
                                   textColor=SLATE, alignment=TA_RIGHT)
    s["session"] = ParagraphStyle("session", fontName=BODY, fontSize=9.5,
                                   textColor=SLATE, leading=14, spaceAfter=6)
    s["q_label"] = ParagraphStyle("q_label", fontName=BODY_B, fontSize=8,
                                   textColor=ORANGE, spaceAfter=4, spaceBefore=2,
                                   letterSpacing=1.2)
    s["q_text"]  = ParagraphStyle("q_text",  fontName=HEAD, fontSize=11,
                                   textColor=NAVY, leading=16, leftIndent=12)
    s["ai_label"]= ParagraphStyle("ai_label",fontName=BODY_B, fontSize=8,
                                   textColor=NAVY, spaceAfter=3, spaceBefore=8,
                                   letterSpacing=1.2)
    s["body"]    = ParagraphStyle("body", fontName=BODY, fontSize=9.5,
                                   textColor=BLACK, leading=14.5, alignment=TA_JUSTIFY,
                                   spaceAfter=3)
    s["bullet_text"] = ParagraphStyle("bullet_text", fontName=BODY, fontSize=9.5,
                                       textColor=BLACK, leading=14, spaceAfter=1)
    s["sec_label"]= ParagraphStyle("sec_label", fontName=BODY_B, fontSize=7.5,
                                    textColor=ORANGE, spaceBefore=8, spaceAfter=3,
                                    letterSpacing=1.0)
    s["sql"]     = ParagraphStyle("sql", fontName="Courier", fontSize=7.5,
                                   textColor=colors.HexColor("#1e293b"),
                                   leading=11, leftIndent=4, rightIndent=4)
    s["footer"]  = ParagraphStyle("footer", fontName=BODY_I, fontSize=7.5,
                                   textColor=SILVER, alignment=TA_CENTER)
    s["no_data"] = ParagraphStyle("no_data", fontName=BODY_I, fontSize=9,
                                   textColor=SLATE)
    s["kpi_val"] = ParagraphStyle("kpi_val", fontName=BODY_B, fontSize=22,
                                   textColor=NAVY, alignment=TA_CENTER, spaceBefore=4, spaceAfter=4)
    s["kpi_lbl"] = ParagraphStyle("kpi_lbl", fontName=BODY_B, fontSize=9,
                                   textColor=ORANGE, alignment=TA_CENTER, spaceBefore=4, letterSpacing=1.1)
    s["kpi_sub"] = ParagraphStyle("kpi_sub", fontName=BODY_I, fontSize=8,
                                   textColor=SLATE, alignment=TA_CENTER, spaceAfter=4)
    return s


# ── Header ────────────────────────────────────────────────────────────────────
def _header(S, generated_at: str) -> list:
    logo_cell = ""
    if os.path.exists(LOGO_PATH):
        try:
            logo_cell = Image(LOGO_PATH, width=3.0 * cm, height=1.3 * cm)
            logo_cell.hAlign = "LEFT"
        except Exception:
            logo_cell = Paragraph("TVS Insurance Broking Private Limited", S["co_name"])
    else:
        logo_cell = Paragraph("TVS Insurance Broking Private Limited", S["co_name"])

    title_col = [
        Paragraph("TVS Insurance Broking Private Limited", S["co_name"]),
        Paragraph("Analytics Intelligence Report", S["co_sub"]),
    ]
    ts_col = Paragraph(f"Generated:<br/><b>{generated_at}</b>", S["ts"])

    hdr = Table([[logo_cell, title_col, ts_col]],
                colWidths=[3.2 * cm, 11.0 * cm, 4.8 * cm])
    hdr.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    return [
        hdr,
        Spacer(1, 0.2 * cm),
        HRFlowable(width="100%", thickness=2.5, color=NAVY, spaceAfter=4),
        HRFlowable(width="100%", thickness=1.0, color=ORANGE, spaceAfter=10),
    ]


# ── Data table ────────────────────────────────────────────────────────────────
def _data_table(data: list, S: dict) -> list:
    if not data:
        return [Paragraph("No data returned for this query.", S["no_data"])]

    columns   = list(data[0].keys())
    n_cols    = len(columns)
    usable_w  = A4[0] - 3.6 * cm
    col_w     = usable_w / n_cols

    th = ParagraphStyle("th", fontName=BODY_B, fontSize=8.5,
                         textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("td", fontName=BODY,   fontSize=8.5,
                         textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("td_num", fontName=BODY, fontSize=8.5,
                             textColor=BLACK, alignment=TA_RIGHT)

    rows = [[Paragraph(_humanize_col(c), th) for c in columns]]
    for i, row in enumerate(data[:60]):
        cells = []
        for col in columns:
            raw = row.get(col, "")  
            fmt = _format_cell(raw)
            # Right-align if numeric
            try:
                float(str(raw).replace(",", "").replace("Rs.", ""))
                cells.append(Paragraph(fmt, td_num))
            except (ValueError, TypeError):
                cells.append(Paragraph(fmt, td))
        rows.append(cells)

    tbl = Table(rows, colWidths=[col_w] * n_cols, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), WHITE]),
        ("LINEBELOW",     (0, 0), (-1, 0),  1.5, ORANGE),
        ("GRID",          (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    result: list[Any] = [tbl]
    if len(data) > 60:
        result.append(Paragraph(
            f"Showing first 60 of {len(data)} rows.",
            S["no_data"]
        ))
    return result


def _draw_kpi_card(val_str: str, col_name: str, S: dict) -> Table:
    p_lbl = Paragraph(col_name.upper(), S["kpi_lbl"])
    p_val = Paragraph(val_str, S["kpi_val"])
    p_sub = Paragraph("Single Metric Query Result", S["kpi_sub"])
    
    t = Table([[p_lbl], [p_val], [p_sub]], colWidths=[9.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
    ]))
    t.hAlign = "CENTER"
    return t


def _create_progress_bar(width: float, pct: float, color: Any) -> Drawing:
    d = Drawing(width, 16)
    # Background track
    d.add(Rect(0, 3, width, 10, fillColor=colors.HexColor("#F1F5F9"), strokeColor=None, rx=4, ry=4)) # type: ignore
    # Filled bar
    if pct > 0:
        fill_w = max(2, width * min(pct, 1.0))
        d.add(Rect(0, 3, fill_w, 10, fillColor=color, strokeColor=None, rx=4, ry=4)) # type: ignore
    return d


def _draw_bar_chart_table(data: list, cat_col: str, val_col: str, S: dict, is_currency: bool = True) -> Optional[list[Any]]:
    rows = []
    for r in data:
        c_val = r.get(cat_col)
        v_val = r.get(val_col)
        if c_val is not None and v_val is not None:
            try:
                rows.append((str(c_val), float(str(v_val).replace(",", "").replace("Rs.", "").replace("₹", "").strip())))
            except (ValueError, TypeError):
                pass
                
    if not rows:
        return None
        
    rows = rows[:12]
    
    vals = [r[1] for r in rows]
    max_val = max(vals) if vals else 1.0
    if max_val <= 0:
        max_val = 1.0
        
    lbl_style = ParagraphStyle("bar_lbl", fontName=BODY_B, fontSize=8.5, textColor=BLACK, leading=12)
    val_style = ParagraphStyle("bar_val", fontName=BODY, fontSize=8.5, textColor=SLATE, alignment=TA_RIGHT)
    
    table_rows = []
    for cat_name, val_num in rows:
        p_lbl = Paragraph(cat_name, lbl_style)
        bar_flowable = _create_progress_bar(9.0 * cm, val_num / max_val, NAVY)
        if is_currency:
            fmt_val = _format_cell(val_num)
        else:
            fmt_val = f"{int(val_num):,}"
        p_val = Paragraph(fmt_val, val_style)
        table_rows.append([p_lbl, bar_flowable, p_val])
        
    t = Table(table_rows, colWidths=[5.0 * cm, 9.4 * cm, 3.0 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
    ]))
    t.hAlign = "LEFT"
    return [t]


def _draw_line_chart(data: list, date_col: str, val_col: str, S: dict) -> Optional[Drawing]:
    points = []
    for row in data:
        d_val = row.get(date_col)
        v_val = row.get(val_col)
        if d_val is not None and v_val is not None:
            try:
                points.append((str(d_val), float(str(v_val).replace(",", "").replace("Rs.", "").replace("₹", "").strip())))
            except (ValueError, TypeError):
                pass
                
    if not points:
        return None
        
    try:
        points.sort(key=lambda x: x[0])
    except Exception:
        pass
        
    N = len(points)
    if N < 2:
        return None
        
    vals = [p[1] for p in points]
    min_val = min(vals)
    max_val = max(vals)
    val_range = max_val - min_val
    if val_range == 0:
        val_range = 1.0
        
    w = 17.4 * cm
    h = 5.0 * cm
    pad_left = 1.8 * cm
    pad_right = 0.5 * cm
    pad_bottom = 0.8 * cm
    pad_top = 0.5 * cm
    
    plot_w = w - pad_left - pad_right
    plot_h = h - pad_bottom - pad_top
    
    d = Drawing(w, h)
    
    d.add(Rect(pad_left, pad_bottom, plot_w, plot_h, fillColor=colors.HexColor("#F8FAFC"), strokeColor=DIVIDER, strokeWidth=1)) # type: ignore
    
    grid_steps = 4
    for step in range(grid_steps + 1):
        f = step / grid_steps
        y_val = min_val + f * (max_val - min_val)
        y_pos = pad_bottom + f * plot_h
        
        if step > 0 and step < grid_steps:
            d.add(Line(pad_left, y_pos, pad_left + plot_w, y_pos, strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.5))
            
        lbl_str = _format_cell(y_val)
        d.add(String(pad_left - 6, y_pos - 3, lbl_str, fontName=BODY, fontSize=7, fillColor=SLATE, textAnchor="end"))
        
    x_indices = [0, N // 2, N - 1] if N > 2 else [0, 1]
    x_indices = sorted(list(set(x_indices)))
    for idx in x_indices:
        date_str, _ = points[idx]
        x_pos = pad_left + (idx / (N - 1)) * plot_w
        short_date = date_str
        if len(date_str) > 10:
            short_date = date_str[:10]
        d.add(String(x_pos, pad_bottom - 12, short_date, fontName=BODY, fontSize=7, fillColor=SLATE, textAnchor="middle"))
        
    line_coords = []
    for idx, (d_str, v_val) in enumerate(points):
        x_pos = pad_left + (idx / (N - 1)) * plot_w
        y_pos = pad_bottom + ((v_val - min_val) / val_range) * plot_h
        line_coords.append((x_pos, y_pos))
        
        if N <= 20:
            d.add(Circle(x_pos, y_pos, 2.5, fillColor=ORANGE, strokeColor=WHITE, strokeWidth=0.5))
            
    for idx in range(len(line_coords) - 1):
        x1, y1 = line_coords[idx]
        x2, y2 = line_coords[idx+1]
        d.add(Line(x1, y1, x2, y2, strokeColor=NAVY, strokeWidth=2))
        
    return d


def _to_indian_abbreviated(val: float) -> str:
    """Format a float into abbreviated Indian Rupee notation: Rs.X.XX Cr/L"""
    if val < 0:
        return f"-{_to_indian_abbreviated(-val)}"
    abs_val = abs(val)
    if abs_val >= 10_000_000:
        return f"Rs.{abs_val/10_000_000:.2f} Cr"
    elif abs_val >= 100_000:
        return f"Rs.{abs_val/100_000:.2f} L"
    elif abs_val >= 1_000:
        return f"Rs.{abs_val/1_000:.1f}k"
    return f"Rs.{abs_val:,.0f}"


def _draw_general_kpi_table(df: pd.DataFrame, S: dict) -> Table:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None

    total_prem  = df[premium_col].sum() if premium_col else 0.0
    total_claim = df[claim_col].sum()   if claim_col   else 0.0
    total_comm  = df[comm_col].sum()    if comm_col    else 0.0
    loss_ratio  = (total_claim / total_prem * 100) if total_prem > 0 else 0.0
    comm_rate   = (total_comm / total_prem * 100) if total_prem > 0 else 0.0
    
    today = pd.Timestamp.now().normalize()
    if 'policy_status' in df.columns:
        status_counts = df['policy_status'].value_counts()
        renewed    = status_counts.get('Renewed', 0)
        expired    = status_counts.get('Expired', 0)
        cancelled  = status_counts.get('Cancelled', 0)
        
        # Audit expired policies: exclude those that expired within the last 30 days (grace period/renewal-eligible)
        eligible_expired = 0
        if 'expiry_date' in df.columns:
            expired_df = df[df['policy_status'] == 'Expired']
            if not expired_df.empty:
                exp_dates = pd.to_datetime(expired_df['expiry_date'], errors='coerce')
                eligible_expired = int(np.sum((exp_dates >= (today - pd.Timedelta(days=30))) & (exp_dates <= today)))
                
        true_expired_churn = max(0, expired - eligible_expired)
        denom      = renewed + expired + cancelled
        # Note: Retention Rate and Churn Rate do not sum to 100% because expired policies
        # within the 30-day grace period (eligible_expired) are excluded from the churn numerator
        # (true_expired_churn) but kept in the denominator since they are not yet fully churned.
        ret_rate   = (renewed / denom * 100) if denom > 0 else 0.0
        churn_rate = ((cancelled + true_expired_churn) / denom * 100) if denom > 0 else 0.0
    else:
        ret_rate = 0.0
        churn_rate = 0.0
        
    val_premium = _to_indian_abbreviated(total_prem)
    val_claims  = _to_indian_abbreviated(total_claim)
    val_comm    = f"{_to_indian_abbreviated(total_comm)} ({comm_rate:.1f}%)"
    
    val_loss = f"{loss_ratio:.1f}%"
    val_ret = f"{ret_rate:.1f}%"
    val_churn = f"{churn_rate:.1f}%"
    
    th_style = ParagraphStyle("kpi_th", fontName=BODY_B, fontSize=7, textColor=ORANGE, alignment=TA_CENTER)
    td_style = ParagraphStyle("kpi_td", fontName=HEAD, fontSize=9.5, textColor=NAVY, alignment=TA_CENTER)
    
    row_lbls = [
        Paragraph("TOTAL PREMIUM", th_style),
        Paragraph("GROSS COMMISSION", th_style),
        Paragraph("TOTAL CLAIMS", th_style),
        Paragraph("LOSS RATIO", th_style),
        Paragraph("RETENTION RATE", th_style),
        Paragraph("CHURN RATE", th_style)
    ]
    row_vals = [
        Paragraph(val_premium, td_style),
        Paragraph(val_comm, td_style),
        Paragraph(val_claims, td_style),
        Paragraph(val_loss, td_style),
        Paragraph(val_ret, td_style),
        Paragraph(val_churn, td_style)
    ]
    
    t = Table([row_lbls, row_vals], colWidths=[2.9 * cm] * 6)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, DIVIDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 1.0, ORANGE),
    ]))
    t.hAlign = "CENTER"
    return t


def _draw_channel_mix_table(df: pd.DataFrame, S: dict) -> Optional[Table]:
    if 'distribution_channel' not in df.columns:
        return None
        
    agg_kwargs = {}
    if 'policy_number' in df.columns:
        agg_kwargs['policies'] = pd.NamedAgg(column='policy_number', aggfunc='count')
    else:
        agg_kwargs['policies'] = pd.NamedAgg(column='distribution_channel', aggfunc='count')
        
    if 'premium_amount' in df.columns:
        agg_kwargs['premium'] = pd.NamedAgg(column='premium_amount', aggfunc='sum')
    else:
        agg_kwargs['premium'] = pd.NamedAgg(column='distribution_channel', aggfunc=lambda x: 0.0)
        
    if 'claim_amount' in df.columns:
        agg_kwargs['claims'] = pd.NamedAgg(column='claim_amount', aggfunc='sum')
    else:
        agg_kwargs['claims'] = pd.NamedAgg(column='distribution_channel', aggfunc=lambda x: 0.0)
        
    gp = df.groupby('distribution_channel').agg(**agg_kwargs).reset_index()
    gp = gp.sort_values(by='premium', ascending=False)
    
    th = ParagraphStyle("ch_th", fontName=BODY_B, fontSize=8, textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("ch_td", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("ch_td_num", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_RIGHT)
    
    rows = [[
        Paragraph("Distribution Channel", th),
        Paragraph("Policies", th),
        Paragraph("Written Premium", th),
        Paragraph("Claims Paid", th),
        Paragraph("Loss Ratio", th)
    ]]
    
    for _, r in gp.iterrows():
        channel = str(r['distribution_channel'])
        cnt = int(r['policies'])
        prem = float(r['premium'])
        clm = float(r['claims'])
        lr = (clm / prem * 100) if prem > 0 else 0.0
        
        rows.append([
            Paragraph(channel, td),
            Paragraph(f"{cnt:,}", td_num),
            Paragraph(_to_indian_format(prem), td_num),
            Paragraph(_to_indian_format(clm), td_num),
            Paragraph(f"{lr:.1f}%", td_num)
        ])
        
    t = Table(rows, colWidths=[4.8 * cm, 2.0 * cm, 3.8 * cm, 3.8 * cm, 3.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), WHITE]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t


def _draw_regional_table(df: pd.DataFrame, S: dict, colWidths=None) -> Optional[Table]:
    if 'region' not in df.columns:
        return None
        
    df = df.copy()
    df['region'] = df['region'].astype(str).str.strip().str.upper()
    
    agg_kwargs = {}
    if 'policy_number' in df.columns:
        agg_kwargs['policies'] = pd.NamedAgg(column='policy_number', aggfunc='count')
    else:
        agg_kwargs['policies'] = pd.NamedAgg(column='region', aggfunc='count')
        
    if 'premium_amount' in df.columns:
        agg_kwargs['premium'] = pd.NamedAgg(column='premium_amount', aggfunc='sum')
    else:
        agg_kwargs['premium'] = pd.NamedAgg(column='region', aggfunc=lambda x: 0.0)
        
    if 'claim_amount' in df.columns:
        agg_kwargs['claims'] = pd.NamedAgg(column='claim_amount', aggfunc='sum')
    else:
        agg_kwargs['claims'] = pd.NamedAgg(column='region', aggfunc=lambda x: 0.0)
        
    gp = df.groupby('region').agg(**agg_kwargs).reset_index()
    gp = gp.sort_values(by='premium', ascending=False)
    
    th = ParagraphStyle("rg_th", fontName=BODY_B, fontSize=8, textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("rg_td", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("rg_td_num", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_RIGHT)
    
    rows = [[
        Paragraph("Region", th),
        Paragraph("Policies", th),
        Paragraph("Written Premium", th),
        Paragraph("Claims Paid", th),
        Paragraph("Loss Ratio", th)
    ]]
    
    for _, r in gp.iterrows():
        reg = str(r['region'])
        cnt = int(r['policies'])
        prem = float(r['premium'])
        clm = float(r['claims'])
        lr = (clm / prem * 100) if prem > 0 else 0.0
        
        rows.append([
            Paragraph(reg, td),
            Paragraph(f"{cnt:,}", td_num),
            Paragraph(_to_indian_format(prem), td_num),
            Paragraph(_to_indian_format(clm), td_num),
            Paragraph(f"{lr:.1f}%", td_num)
        ])
        
    if colWidths is None:
        colWidths = [4.8 * cm, 2.0 * cm, 3.8 * cm, 3.8 * cm, 3.0 * cm]
    t = Table(rows, colWidths=colWidths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), WHITE]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t


def _draw_top_clients_table(df: pd.DataFrame, S: dict) -> Optional[Table]:
    if 'client_name' not in df.columns:
        return None
        
    agg_kwargs = {}
    if 'policy_number' in df.columns:
        agg_kwargs['policies'] = pd.NamedAgg(column='policy_number', aggfunc='count')
    else:
        agg_kwargs['policies'] = pd.NamedAgg(column='client_name', aggfunc='count')
        
    if 'premium_amount' in df.columns:
        agg_kwargs['premium'] = pd.NamedAgg(column='premium_amount', aggfunc='sum')
    else:
        agg_kwargs['premium'] = pd.NamedAgg(column='client_name', aggfunc=lambda x: 0.0)
        
    if 'claim_amount' in df.columns:
        agg_kwargs['claims'] = pd.NamedAgg(column='claim_amount', aggfunc='sum')
    else:
        agg_kwargs['claims'] = pd.NamedAgg(column='client_name', aggfunc=lambda x: 0.0)
        
    gp = df.groupby('client_name').agg(**agg_kwargs).reset_index()
    gp = gp.sort_values(by='premium', ascending=False).head(5)
    
    th = ParagraphStyle("cli_th", fontName=BODY_B, fontSize=8, textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("cli_td", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("cli_td_num", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_RIGHT)
    
    rows = [[
        Paragraph("Client Name", th),
        Paragraph("Policies", th),
        Paragraph("Written Premium", th),
        Paragraph("Claims Paid", th),
        Paragraph("Loss Ratio", th)
    ]]
    
    for _, r in gp.iterrows():
        name = str(r['client_name'])
        cnt = int(r['policies'])
        prem = float(r['premium'])
        clm = float(r['claims'])
        lr = (clm / prem * 100) if prem > 0 else 0.0
        
        rows.append([
            Paragraph(name, td),
            Paragraph(f"{cnt:,}", td_num),
            Paragraph(_to_indian_format(prem), td_num),
            Paragraph(_to_indian_format(clm), td_num),
            Paragraph(f"{lr:.1f}%", td_num)
        ])
        
    t = Table(rows, colWidths=[4.8 * cm, 2.0 * cm, 3.8 * cm, 3.8 * cm, 3.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), WHITE]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t


def _draw_high_risk_table(df: pd.DataFrame, S: dict) -> Optional[Union[Table, Paragraph]]:
    claim_col = 'claim_amount' if 'claim_amount' in df.columns else None
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    if not claim_col or not premium_col or 'client_name' not in df.columns:
        return None
        
    risk_df = df.groupby('client_name').agg(
        policies=('policy_number', 'count') if 'policy_number' in df.columns else ('client_name', 'count'),
        premium=(premium_col, 'sum'),
        claims=(claim_col, 'sum')
    ).reset_index()
    
    risk_df['loss_ratio'] = (risk_df['claims'] / risk_df['premium'] * 100)
    hr = risk_df[risk_df['loss_ratio'] > 100].sort_values(by='loss_ratio', ascending=False).head(5)
    
    if hr.empty:
        return Paragraph("No high-risk clients (Loss Ratio > 100%) identified in the current portfolio.", S["body"])
        
    th = ParagraphStyle("hr_th", fontName=BODY_B, fontSize=8, textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("hr_td", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("hr_td_num", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_RIGHT)
    
    rows = [[
        Paragraph("Client Name", th),
        Paragraph("Policies", th),
        Paragraph("Total Premium", th),
        Paragraph("Total Claims", th),
        Paragraph("Loss Ratio", th)
    ]]
    
    for _, r in hr.iterrows():
        name = str(r['client_name'])
        cnt = int(r['policies'])
        prem = float(r['premium'])
        clm = float(r['claims'])
        lr = float(r['loss_ratio'])
        
        rows.append([
            Paragraph(name, td),
            Paragraph(f"{cnt:,}", td_num),
            Paragraph(_to_indian_format(prem), td_num),
            Paragraph(_to_indian_format(clm), td_num),
            Paragraph(f"{lr:.1f}%", td_num)
        ])
        
    t = Table(rows, colWidths=[4.8 * cm, 2.0 * cm, 3.8 * cm, 3.8 * cm, 3.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FEF2F2"), WHITE]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t


def _draw_product_mix_table(df: pd.DataFrame, S: dict) -> Table:
    agg_kwargs = {}
    if 'policy_number' in df.columns:
        agg_kwargs['policies'] = pd.NamedAgg(column='policy_number', aggfunc='count')
    else:
        agg_kwargs['policies'] = pd.NamedAgg(column='category', aggfunc='count')
        
    if 'premium_amount' in df.columns:
        agg_kwargs['premium'] = pd.NamedAgg(column='premium_amount', aggfunc='sum')
    else:
        agg_kwargs['premium'] = pd.NamedAgg(column='category', aggfunc=lambda x: 0.0)
        
    if 'claim_amount' in df.columns:
        agg_kwargs['claims'] = pd.NamedAgg(column='claim_amount', aggfunc='sum')
    else:
        agg_kwargs['claims'] = pd.NamedAgg(column='category', aggfunc=lambda x: 0.0)
        
    if 'commission_earned' in df.columns:
        agg_kwargs['commission'] = pd.NamedAgg(column='commission_earned', aggfunc='sum')
    else:
        agg_kwargs['commission'] = pd.NamedAgg(column='category', aggfunc=lambda x: 0.0)
        
    gp = df.groupby('category').agg(**agg_kwargs).reset_index()
    gp = gp.sort_values(by='premium', ascending=False)
    
    th = ParagraphStyle("pm_th", fontName=BODY_B, fontSize=8, textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("pm_td", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("pm_td_num", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_RIGHT)
    
    rows = [[
        Paragraph("Product Category", th),
        Paragraph("Policies", th),
        Paragraph("Total Premium", th),
        Paragraph("Claims Incurred", th),
        Paragraph("Loss Ratio", th),
        Paragraph("Commission", th)
    ]]
    
    for _, r in gp.iterrows():
        cat = str(r['category'])
        cnt = int(r['policies'])
        prem = float(r['premium'])
        clm = float(r['claims'])
        comm = float(r['commission'])
        lr = (clm / prem * 100) if prem > 0 else 0.0
        
        rows.append([
            Paragraph(cat, td),
            Paragraph(f"{cnt:,}", td_num),
            Paragraph(_to_indian_format(prem), td_num),
            Paragraph(_to_indian_format(clm), td_num),
            Paragraph(f"{lr:.1f}%", td_num),
            Paragraph(_to_indian_format(comm), td_num)
        ])
        
    t = Table(rows, colWidths=[3.2 * cm, 1.8 * cm, 3.4 * cm, 3.4 * cm, 2.2 * cm, 3.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), WHITE]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t


def _draw_carrier_table(df: pd.DataFrame, S: dict) -> Optional[Table]:
    if 'carrier_name' not in df.columns:
        return None
        
    agg_kwargs = {}
    if 'policy_number' in df.columns:
        agg_kwargs['policies'] = pd.NamedAgg(column='policy_number', aggfunc='count')
    else:
        agg_kwargs['policies'] = pd.NamedAgg(column='carrier_name', aggfunc='count')
        
    if 'premium_amount' in df.columns:
        agg_kwargs['premium'] = pd.NamedAgg(column='premium_amount', aggfunc='sum')
    else:
        agg_kwargs['premium'] = pd.NamedAgg(column='carrier_name', aggfunc=lambda x: 0.0)
        
    if 'claim_amount' in df.columns:
        agg_kwargs['claims'] = pd.NamedAgg(column='claim_amount', aggfunc='sum')
    else:
        agg_kwargs['claims'] = pd.NamedAgg(column='carrier_name', aggfunc=lambda x: 0.0)
        
    gp = df.groupby('carrier_name').agg(**agg_kwargs).reset_index()
    gp = gp.sort_values(by='premium', ascending=False).head(8)
    
    th = ParagraphStyle("cr_th", fontName=BODY_B, fontSize=8, textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("cr_td", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("cr_td_num", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_RIGHT)
    
    rows = [[
        Paragraph("Carrier Name", th),
        Paragraph("Policies", th),
        Paragraph("Written Premium", th),
        Paragraph("Claims Paid", th),
        Paragraph("Loss Ratio", th)
    ]]
    
    for _, r in gp.iterrows():
        name = str(r['carrier_name'])
        cnt = int(r['policies'])
        prem = float(r['premium'])
        clm = float(r['claims'])
        lr = (clm / prem * 100) if prem > 0 else 0.0
        
        rows.append([
            Paragraph(name, td),
            Paragraph(f"{cnt:,}", td_num),
            Paragraph(_to_indian_format(prem), td_num),
            Paragraph(_to_indian_format(clm), td_num),
            Paragraph(f"{lr:.1f}%", td_num)
        ])
        
    t = Table(rows, colWidths=[4.8 * cm, 2.0 * cm, 3.8 * cm, 3.8 * cm, 3.0 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), WHITE]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t


def _draw_claims_breakdown_table(df: pd.DataFrame, S: dict, colWidths=None) -> Optional[Table]:
    if 'claim_status' not in df.columns:
        return None
        
    agg_kwargs = {}
    agg_kwargs['count'] = pd.NamedAgg(column='claim_amount', aggfunc='count')
    if 'claim_amount' in df.columns:
        agg_kwargs['amount'] = pd.NamedAgg(column='claim_amount', aggfunc='sum')
    else:
        agg_kwargs['amount'] = pd.NamedAgg(column='claim_status', aggfunc=lambda x: 0.0)
        
    gp = df.groupby('claim_status').agg(**agg_kwargs).reset_index()
    gp = gp.sort_values(by='amount', ascending=False)
    
    th = ParagraphStyle("cl_th", fontName=BODY_B, fontSize=8, textColor=WHITE, alignment=TA_LEFT)
    td = ParagraphStyle("cl_td", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_LEFT)
    td_num = ParagraphStyle("cl_td_num", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_RIGHT)
    
    rows = [[
        Paragraph("Claim Status", th),
        Paragraph("Claims Count", th),
        Paragraph("Total Claims Amount", th)
    ]]
    
    for _, r in gp.iterrows():
        status = str(r['claim_status'])
        cnt = int(r['count'])
        amt = float(r['amount'])
        
        rows.append([
            Paragraph(status, td),
            Paragraph(f"{cnt:,}", td_num),
            Paragraph(_to_indian_format(amt), td_num)
        ])
        
    if colWidths is None:
        colWidths = [6.4 * cm, 3.6 * cm, 7.4 * cm]
    t = Table(rows, colWidths=colWidths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), WHITE]),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, ORANGE),
        ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t



def _draw_growth_trend_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    if 'issue_date' not in df.columns or not premium_col:
        return None
    try:
        df3 = df.copy()
        df3['issue_month'] = pd.to_datetime(df3['issue_date']).dt.to_period('M').astype(str) # type: ignore
        growth_df = df3.groupby('issue_month')[premium_col].sum().reset_index().sort_values('issue_month')
        growth_df['cumulative'] = growth_df[premium_col].cumsum()
        
        import plotly.express as px
        fig = px.line(growth_df, x='issue_month', y='cumulative', markers=True)
        fig.update_traces(line_color='#1B3B8B', line_width=3, fill='tozeroy', fillcolor='rgba(27,59,139,0.09)')
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=10, b=25, l=45, r=10),
            xaxis_title=None, yaxis_title=None,
            width=800, height=220
        )
        fig.update_xaxes(showgrid=True, gridcolor='#E2E8F0')
        fig.update_yaxes(showgrid=True, gridcolor='#E2E8F0')
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error growth chart: {e}")
        return None

def _draw_vintage_cohort_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    if 'issue_date' not in df.columns or 'policy_status' not in df.columns:
        return None
    try:
        df2 = df.copy()
        df2['issue_date'] = pd.to_datetime(df2['issue_date'], errors='coerce')
        df2['issue_quarter'] = df2['issue_date'].dt.to_period('Q').astype(str) # type: ignore
        cohort = df2.groupby(['issue_quarter', 'policy_status']).size().reset_index(name='count')
        
        import plotly.express as px
        fig = px.bar(cohort, x='issue_quarter', y='count', color='policy_status', barmode='stack',
                     color_discrete_map={'Active': '#10B981', 'Renewed': '#1B3B8B',
                                         'Cancelled': '#EF4444', 'Expired': '#F59E0B'})
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=10, b=25, l=45, r=10),
            xaxis_title=None, yaxis_title=None,
            legend_title=None,
            width=800, height=220,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_xaxes(showgrid=True, gridcolor='#E2E8F0')
        fig.update_yaxes(showgrid=True, gridcolor='#E2E8F0')
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error vintage chart: {e}")
        return None

def _draw_profitability_carrier_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None
    if 'carrier_name' not in df.columns or not premium_col or not claim_col or not comm_col:
        return None
    try:
        nr = df.groupby('carrier_name').agg(
            Premium=(premium_col, 'sum'),
            Commission=(comm_col, 'sum'),
            Claims=(claim_col, 'sum'),
        ).reset_index()
        nr['Underwriting_Profit'] = nr['Premium'] - nr['Claims'] - nr['Commission']
        nr = nr.sort_values('Underwriting_Profit', ascending=True).head(8)
        colors_nr = ['#10B981' if v >= 0 else '#EF4444' for v in nr['Underwriting_Profit']]
        nr['Profit_Label'] = nr['Underwriting_Profit'].apply(lambda x: _to_indian_abbreviated(x))
        
        max_val = nr['Underwriting_Profit'].max()
        min_val = nr['Underwriting_Profit'].min()
        x_min = min_val * 1.25 if min_val < 0 else min_val * 0.75
        x_max = max_val * 1.25 if max_val > 0 else max_val * 0.75
        if x_max == 0: x_max = 1000.0
        if x_min == 0: x_min = -1000.0
        
        import plotly.express as px
        fig = px.bar(nr, y='carrier_name', x='Underwriting_Profit', orientation='h', text='Profit_Label')
        fig.update_traces(marker_color=colors_nr, textposition='outside')
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=15, b=25, l=100, r=70),
            xaxis_title=None, yaxis_title=None,
            width=800, height=220
        )
        fig.update_xaxes(showgrid=True, gridcolor='#E2E8F0', range=[x_min, x_max])
        fig.update_yaxes(showgrid=False)
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error profitability chart: {e}")
        return None

def _draw_margin_category_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None
    if 'category' not in df.columns or not premium_col or not comm_col:
        return None
    try:
        mg = df.groupby('category')[[premium_col, comm_col]].sum().reset_index()
        mg['margin_pct'] = np.where(
            mg[premium_col] > 0,
            (mg[comm_col] / mg[premium_col] * 100).round(1),
            0
        )
        
        max_pct = mg['margin_pct'].max()
        y_max = max_pct * 1.25 if max_pct > 0 else 100.0
        
        import plotly.express as px
        fig = px.bar(mg, x='category', y='margin_pct', text='margin_pct')
        fig.update_traces(marker_color='#FF6B00', texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=35, b=25, l=45, r=10),
            xaxis_title=None, yaxis_title=None,
            width=800, height=220
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor='#E2E8F0', range=[0, y_max])
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error margin chart: {e}")
        return None

def _draw_renewal_calendar_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    if 'expiry_date' not in df.columns or not premium_col:
        return None
    try:
        df2 = df.copy()
        df2['expiry_date'] = pd.to_datetime(df2['expiry_date'], errors='coerce')
        now = pd.Timestamp.today().normalize()
        future = df2[df2['expiry_date'] >= now].copy()
        future['exp_month_period'] = future['expiry_date'].dt.to_period('M') # type: ignore
        exp_monthly = future.groupby('exp_month_period').size().reset_index(name='Policies')
        exp_monthly = exp_monthly.sort_values('exp_month_period').head(12)
        exp_monthly['exp_month'] = exp_monthly['exp_month_period'].astype(str)
        
        import plotly.express as px
        fig = px.bar(exp_monthly, x='exp_month', y='Policies')
        fig.update_traces(marker_color='#1B3B8B')
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=10, b=25, l=45, r=10),
            xaxis_title=None, yaxis_title=None,
            width=800, height=220
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor='#E2E8F0')
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error renewal calendar: {e}")
        return None


def _draw_b2b_b2c_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col   = 'claim_amount' if 'claim_amount' in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None
    if 'client_type' not in df.columns or not premium_col or not claim_col or not comm_col:
        return None
    try:
        seg = df.groupby('client_type').agg(
            Premium=(premium_col, 'sum'), Claims=(claim_col, 'sum'), Commission=(comm_col, 'sum')
        ).reset_index()
        seg_melted = seg.melt(id_vars='client_type', value_vars=['Premium', 'Claims', 'Commission'], var_name='Metric', value_name='Value')
        
        import plotly.express as px
        fig = px.bar(seg_melted, x='Metric', y='Value', color='client_type', barmode='group',
                     color_discrete_map={'Individual/B2C': '#1B3B8B', 'Corporate/B2B': '#FF6B00'})
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=10, b=25, l=45, r=10),
            xaxis_title=None, yaxis_title=None,
            legend_title=None,
            width=800, height=220,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor='#E2E8F0')
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error segment chart: {e}")
        return None

def _draw_carrier_portfolio_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    req_cols = ['carrier_name', 'category', 'sub_category']
    if not all(c in df.columns for c in req_cols) or not premium_col:
        return None
    try:
        sun_df = df.groupby(req_cols)[premium_col].sum().reset_index()
        sun_df = sun_df[sun_df[premium_col] > 0]
        order = sun_df.groupby('carrier_name')[premium_col].sum().sort_values().index
        
        import plotly.express as px
        fig = px.bar(sun_df, y='carrier_name', x=premium_col, color='category', orientation='h')
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=10, b=25, l=100, r=10),
            xaxis_title=None, yaxis_title=None,
            legend_title=None,
            width=800, height=220,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            barmode='stack'
        )
        fig.update_yaxes(categoryorder='array', categoryarray=order)
        fig.update_xaxes(showgrid=True, gridcolor='#E2E8F0')
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error carrier breakdown chart: {e}")
        return None

def _draw_channel_stacked_chart(df: pd.DataFrame, S: dict) -> Optional[Image]:
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    if 'distribution_channel' not in df.columns or 'category' not in df.columns or not premium_col:
        return None
    try:
        stack_df = df[df[premium_col] > 0].groupby(
            ['distribution_channel', 'category']
        )[premium_col].sum().reset_index()
        categories = sorted(stack_df['category'].unique())
        channels_sorted = stack_df.groupby('distribution_channel')[premium_col].sum().sort_values(ascending=True).index.tolist()
        
        import plotly.graph_objects as go
        fig = go.Figure()
        channel_palette = ["#1B3B8B", "#FF6B00", "#10B981", "#8B5CF6", "#F59E0B"]
        for i, cat in enumerate(categories):
            cat_data = stack_df[stack_df['category'] == cat]
            x_vals = [cat_data[cat_data['distribution_channel'] == ch][premium_col].sum() if not cat_data[cat_data['distribution_channel'] == ch].empty else 0 for ch in channels_sorted]
            fig.add_trace(go.Bar(
                name=cat, x=x_vals, y=channels_sorted, orientation='h',
                marker_color=channel_palette[i % len(channel_palette)],
            ))
        fig.update_layout(
            barmode="stack",
            plot_bgcolor='white', paper_bgcolor='white',
            margin=dict(t=10, b=25, l=80, r=10),
            xaxis=dict(showgrid=True, gridcolor='#E2E8F0'),
            yaxis=dict(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            width=800, height=220
        )
        png_bytes = fig.to_image(format='png', scale=2.0)
        return Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
    except Exception as e:
        print(f"[report_helper] Error channel stacked chart: {e}")
        return None


def _generate_key_insight(df: pd.DataFrame) -> str:
    """Generate a data-driven Key Insight sentence for the dashboard reporting period."""
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    
    if df.empty or not premium_col:
        return "Key Insight: Premium portfolio is stable with balanced category distribution."
        
    parts = []
    tot_prem = df[premium_col].sum()
    
    if 'category' in df.columns:
        cat_df = df.groupby('category').agg(
            premium=(premium_col, 'sum'),
            claims=(claim_col, 'sum') if claim_col else (premium_col, lambda x: 0)
        )
        if not cat_df.empty:
            top_cat = cat_df['premium'].idxmax()
            top_cat_pct = (cat_df.loc[top_cat, 'premium'] / tot_prem) * 100
            parts.append(f"{top_cat} is the leading product category (contributing {top_cat_pct:.1f}% of premium)")
            
            if claim_col:
                cat_df['loss_ratio'] = (cat_df['claims'] / cat_df['premium'] * 100)
                high_lr_cat = cat_df['loss_ratio'].idxmax()
                high_lr_val = cat_df['loss_ratio'].max()
                if high_lr_val > 50:
                    parts.append(f"the highest loss-ratio is in {high_lr_cat} at {high_lr_val:.1f}%")
                    
    if 'distribution_channel' in df.columns:
        chan_df = df.groupby('distribution_channel')[premium_col].sum()
        if not chan_df.empty:
            top_chan = chan_df.idxmax()
            top_chan_pct = (chan_df.max() / tot_prem) * 100
            parts.append(f"{top_chan} is the dominant channel with {top_chan_pct:.1f}% volume")
            
    if len(parts) >= 2:
        insight = f"Key Insight: {parts[0]}, while {parts[1]}."
    elif parts:
        insight = f"Key Insight: {parts[0]}."
    else:
        insight = "Key Insight: Premium portfolio is stable with balanced category distribution."
        
    return insight


def generate_session_pdf(history: list, df: Optional[pd.DataFrame] = None, exec_notes: Optional[str] = None) -> bytes:
    """
    Generate a premium-quality, multi-page corporate PDF analytics report.
    """
    buf       = io.BytesIO()
    generated = datetime.now().strftime("%d %b %Y   %I:%M %p")
    S         = _styles()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.5 * cm,  bottomMargin=2.2 * cm,
        title="TVS Insurance Broking Private Limited Analytics Report",
        author="TVS Insurance Broking Private Limited",
    )

    elems: list[Any] = []

    # ── COVER PAGE ─────────────────────────────────────────────────────────────
    elems.append(Spacer(1, 4 * cm))
    if os.path.exists(LOGO_PATH):
        try:
            logo_img = Image(LOGO_PATH, width=5.0 * cm, height=2.1 * cm)
            logo_img.hAlign = "CENTER"
            elems.append(logo_img)
        except Exception:
            pass
    elems.append(Spacer(1, 1.5 * cm))
    
    t_style = ParagraphStyle("cover_title", fontName=HEAD, fontSize=28, leading=34, textColor=NAVY, alignment=TA_CENTER)
    elems.append(Paragraph("TVS Insurance Broking Private Limited", t_style))
    elems.append(Spacer(1, 0.4 * cm))
    
    sub_style = ParagraphStyle("cover_subtitle", fontName=BODY_B, fontSize=14, leading=18, textColor=ORANGE, alignment=TA_CENTER)
    elems.append(Paragraph("Analytics Intelligence Report", sub_style))
    elems.append(Spacer(1, 2 * cm))
    
    meta_style = ParagraphStyle("cover_meta", fontName=BODY, fontSize=10, leading=14, textColor=SLATE, alignment=TA_CENTER)
    elems.append(Paragraph(f"<b>Reporting Period:</b> Active Database History<br/><b>Generated:</b> {generated}", meta_style))
    
    elems.append(Spacer(1, 8.5 * cm))
    
    disclaimer_style = ParagraphStyle("cover_disclaimer", fontName=BODY_I, fontSize=9, textColor=SLATE, alignment=TA_CENTER)
    elems.append(Paragraph("Confidential — Internal Use Only", disclaimer_style))
    elems.append(PageBreak())

    # ── PAGE 1: EXECUTIVE BRIEF & PORTFOLIO KPIs ──────────────────────────────
    elems += _header(S, generated)
    
    if df is not None and not df.empty:
        premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
        claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
        comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None

        elems.append(Paragraph("PORTFOLIO EXECUTIVE SUMMARY", S["sec_label"]))
        
        if exec_notes and exec_notes.strip():
            narrative = exec_notes.strip()
        else:
            narrative = (
                "This corporate report compiles key operational indices, premium trajectories, product "
                "segmentations, and claims lifecycles from the active policy database of TVS Insurance Broking Private Limited. "
                "The metrics represent aggregated policy actions, risk profiles, and carrier performance."
            )
        elems.append(Paragraph(narrative, S["body"]))
        elems.append(Spacer(1, 0.3 * cm))
        
        elems.append(_draw_general_kpi_table(df, S))
        elems.append(Spacer(1, 0.15 * cm))
        
        tot_prem = df[premium_col].sum() if premium_col else 0.0
        tot_claims = df[claim_col].sum() if claim_col else 0.0
        tot_comm = df[comm_col].sum() if comm_col else 0.0
        footnote_text = f"<b>Footnote:</b> Full Precise Totals — Written Premium: {_to_indian_format(tot_prem)} | Gross Commission: {_to_indian_format(tot_comm)} | Claims Paid: {_to_indian_format(tot_claims)}"
        elems.append(Paragraph(footnote_text, ParagraphStyle("fn_style", fontName=BODY, fontSize=7, textColor=SLATE, leading=9)))
        elems.append(Spacer(1, 0.25 * cm))

        insight_text = _generate_key_insight(df)
        insight_style = ParagraphStyle("insight_callout", fontName=BODY_I, fontSize=8.5, textColor=NAVY, leading=11)
        insight_table = Table([[Paragraph(insight_text, insight_style)]], colWidths=[17.4 * cm])
        insight_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CREAM),
            ("BOX", (0, 0), (-1, -1), 1.0, ORANGE),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elems.append(insight_table)
        elems.append(Spacer(1, 0.35 * cm))
        
        if 'issue_date' in df.columns and premium_col:
            try:
                df2 = df.copy()
                df2['issue_month'] = pd.to_datetime(df2['issue_date']).dt.to_period('M').astype(str) # type: ignore
                df2['biz_type'] = df2['policy_status'].apply(
                    lambda s: 'Renewal' if s == 'Renewed' else 'New Business'
                ) if 'policy_status' in df2.columns else 'New Business'
                monthly = df2.groupby(['issue_month', 'biz_type'])[premium_col].sum().reset_index()
                monthly = monthly.sort_values('issue_month').tail(12)
                
                import plotly.express as px
                fig_monthly = px.bar(monthly, x='issue_month', y=premium_col, color='biz_type',
                                     barmode='stack',
                                     color_discrete_map={'New Business': '#1B3B8B', 'Renewal': '#FF6B00'})
                fig_monthly.update_layout(
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    margin=dict(t=10, b=25, l=45, r=10),
                    xaxis_title=None,
                    yaxis_title=None,
                    legend_title="Business Type",
                    font=dict(family="Calibri, sans-serif", size=10),
                    width=800,
                    height=280,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                fig_monthly.update_xaxes(showgrid=True, gridcolor='#E2E8F0', tickangle=0)
                fig_monthly.update_yaxes(showgrid=True, gridcolor='#E2E8F0')
                
                png_bytes = fig_monthly.to_image(format='png', scale=2.0)
                img_monthly = Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.8*cm)
                
                elems.append(Paragraph("MONTHLY WRITTEN PREMIUM TREND (NEW BUSINESS VS RENEWALS)", S["sec_label"]))
                elems.append(img_monthly)
            except Exception as e:
                print(f"[report_helper] Error general trend page 1: {e}")
            elems.append(Spacer(1, 0.4 * cm))

        # ── PAGE 2: PORTFOLIO GROWTH & VINTAGE ──────────────────────────────────
        growth_chart = _draw_growth_trend_chart(df, S)
        if growth_chart:
            elems.append(KeepTogether([
                Paragraph("CUMULATIVE PREMIUM WRITTEN (ALL-TIME)", S["sec_label"]),
                growth_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))
            
        vintage_chart = _draw_vintage_cohort_chart(df, S)
        if vintage_chart:
            elems.append(KeepTogether([
                Paragraph("POLICY VINTAGE COHORT — OUTCOME BY ISSUE QUARTER", S["sec_label"]),
                vintage_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))

        # ── PAGE 3: PORTFOLIO SEGMENTATION, PRODUCTS & CHANNELS ───────────────────
        elems.append(KeepTogether([
            Paragraph("PRODUCT CATEGORY SUMMARY", S["sec_label"]),
            _draw_product_mix_table(df, S)
        ]))
        elems.append(Spacer(1, 0.15 * cm))
        
        channel_tbl = _draw_channel_mix_table(df, S)
        if channel_tbl:
            elems.append(KeepTogether([
                Paragraph("DISTRIBUTION CHANNEL PERFORMANCE", S["sec_label"]),
                channel_tbl
            ]))
            elems.append(Spacer(1, 0.15 * cm))
            
        seg_chart = _draw_b2b_b2c_chart(df, S)
        if seg_chart:
            elems.append(KeepTogether([
                Paragraph("B2B VS B2C REVENUE BREAKDOWN", S["sec_label"]),
                seg_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))

        chan_chart = _draw_channel_stacked_chart(df, S)
        if chan_chart:
            elems.append(KeepTogether([
                Paragraph("PREMIUM MIX BY CHANNEL & CATEGORY", S["sec_label"]),
                chan_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))

        if 'category' in df.columns and 'premium_amount' in df.columns:
            try:
                cat_df = df.groupby('category')['premium_amount'].sum().reset_index()
                cat_df = cat_df.sort_values(by='premium_amount', ascending=False).head(5)
                cat_data = cat_df.to_dict('records')
                cat_bars = _draw_bar_chart_table(cat_data, 'category', 'premium_amount', S)
                if cat_bars:
                    elems.append(KeepTogether([
                        Paragraph("PREMIUM CONTRIBUTION BY PRODUCT CATEGORY", S["sec_label"])
                    ] + cat_bars))
                    elems.append(Spacer(1, 0.15 * cm))
            except Exception as e:
                print(f"[report_helper] Error product bars page 3: {e}")

        # ── PAGE 4: MARGIN & PROFITABILITY ANALYSIS ─────────────────────────────
        prof_chart = _draw_profitability_carrier_chart(df, S)
        if prof_chart:
            elems.append(KeepTogether([
                Paragraph("CARRIER UNDERWRITING PROFIT (PREMIUM − CLAIMS − COMMISSION)", S["sec_label"]),
                prof_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))
            
        marg_chart = _draw_margin_category_chart(df, S)
        if marg_chart:
            elems.append(KeepTogether([
                Paragraph("AVERAGE COMMISSION MARGIN % BY PRODUCT CATEGORY", S["sec_label"]),
                marg_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))

        # ── PAGE 5: CARRIER SCORECARD & CLAIMS ANALYSIS ──────────────────────────
        elems.append(KeepTogether([
            Paragraph("TOP INSURANCE CARRIER SCORECARD", S["sec_label"]),
            _draw_carrier_table(df, S)
        ]))
        elems.append(Spacer(1, 0.15 * cm))

        carr_chart = _draw_carrier_portfolio_chart(df, S)
        if carr_chart:
            elems.append(KeepTogether([
                Paragraph("CARRIER PORTFOLIO BREAKDOWN", S["sec_label"]),
                carr_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))
        
        if 'claim_status' in df.columns and claim_col:
            try:
                total_claim = df[claim_col].sum() if claim_col else 0
                total_prem  = df[premium_col].sum() if premium_col else 0
                loss_ratio  = (total_claim / total_prem * 100) if total_prem > 0 else 0
                
                import plotly.graph_objects as go
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = loss_ratio, domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "Global Incurred Claims Ratio", 'font': {'size': 12, 'color': "#475569"}},
                    number = {'suffix': "%", 'font': {'size': 28, 'color': "#1B3B8B", 'weight': 'bold'}},
                    gauge = {
                        'axis': {'range': [0, 150], 'tickvals': [0, 75, 85, 150], 'tickwidth': 1, 'tickcolor': "#D1D5DB"},
                        'bar': {'color': "#1B3B8B", 'thickness': 0.15}, 'bgcolor': "white", 'borderwidth': 0,
                        'steps': [{'range': [0, 75], 'color': "rgba(16, 185, 129, 0.2)"},
                                  {'range': [75, 85], 'color': "rgba(245, 158, 11, 0.2)"},
                                  {'range': [85, 150], 'color': "rgba(239, 68, 68, 0.2)"}],
                        'threshold': {'line': {'color': "black", 'width': 2}, 'thickness': 0.75, 'value': loss_ratio}
                    }
                ))
                fig_gauge.update_layout(margin=dict(t=35, b=5, l=15, r=15), width=400, height=250, paper_bgcolor='white')
                png_bytes = fig_gauge.to_image(format='png', scale=2.0)
                img_gauge = Image(io.BytesIO(png_bytes), width=7.0*cm, height=4.4*cm)
                
                claims_tbl = _draw_claims_breakdown_table(df, S, colWidths=[3.8 * cm, 2.0 * cm, 3.8 * cm])
                if claims_tbl:
                    side_table = Table([[claims_tbl, img_gauge]], colWidths=[9.8*cm, 7.0*cm])
                    side_table.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('LEFTPADDING', (0,0), (-1,-1), 0),
                        ('RIGHTPADDING', (0,0), (-1,-1), 0),
                        ('TOPPADDING', (0,0), (-1,-1), 0),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                    ]))
                    elems.append(KeepTogether([
                        Paragraph("CLAIMS LIFECYCLE & GLOBAL INCURRED CLAIMS RATIO (ICR) GAUGE", S["sec_label"]),
                        side_table
                    ]))
                    elems.append(Spacer(1, 0.15 * cm))
            except Exception as e:
                print(f"[report_helper] Error gauge page 5: {e}")
                
        if 'policy_status' in df.columns:
            try:
                status_df = df['policy_status'].value_counts().reset_index()
                status_df.columns = ['policy_status', 'count']
                status_data = status_df.to_dict('records')
                status_bars = _draw_bar_chart_table(status_data, 'policy_status', 'count', S, is_currency=False)
                if status_bars:
                    elems.append(KeepTogether([
                        Paragraph("PORTFOLIO POLICY STATUS DISTRIBUTION", S["sec_label"])
                    ] + status_bars))
                    elems.append(Spacer(1, 0.1 * cm))
            except Exception as e:
                print(f"[report_helper] Error policy status bars page 5: {e}")

        # ── PAGE 6: REGIONAL PERFORMANCE & KEY POLICYHOLDERS ──────────────────────
        reg_tbl = _draw_regional_table(df, S)
        if reg_tbl and 'region' in df.columns and premium_col and claim_col:
            try:
                df_reg_copy = df.copy()
                df_reg_copy['region'] = df_reg_copy['region'].astype(str).str.strip().str.upper()
                reg_df = df_reg_copy.groupby('region')[[premium_col, claim_col]].sum().reset_index()
                import plotly.express as px
                fig_reg = px.bar(reg_df, x='region', y=[premium_col, claim_col], barmode='group',
                                 color_discrete_map={premium_col: '#1B3B8B', claim_col: '#FF6B00'})
                fig_reg.update_layout(
                    plot_bgcolor='white', paper_bgcolor='white',
                    margin=dict(t=10, b=25, l=45, r=10),
                    xaxis_title=None, yaxis_title=None,
                    legend_title=None,
                    font=dict(family="Calibri, sans-serif", size=10),
                    width=800, height=280,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                fig_reg.update_xaxes(showgrid=True, gridcolor='#E2E8F0', tickangle=0)
                fig_reg.update_yaxes(showgrid=True, gridcolor='#E2E8F0')
                
                png_bytes = fig_reg.to_image(format='png', scale=2.0)
                img_reg = Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.8*cm)
                
                elems.append(KeepTogether([
                    Paragraph("REGIONAL PERFORMANCE ANALYSIS", S["sec_label"]),
                    reg_tbl
                ]))
                elems.append(Spacer(1, 0.15 * cm))
                elems.append(KeepTogether([
                    Paragraph("REGIONAL WRITTEN PREMIUM VS CLAIMS INCURRED", S["sec_label"]),
                    img_reg
                ]))
                elems.append(Spacer(1, 0.15 * cm))
            except Exception as e:
                print(f"[report_helper] Error regional bar page 6: {e}")
            
        top_cli_tbl = _draw_top_clients_table(df, S)
        if top_cli_tbl:
            elems.append(KeepTogether([
                Paragraph("TOP 5 KEY POLICYHOLDERS BY PREMIUM", S["sec_label"]),
                top_cli_tbl
            ]))
            elems.append(Spacer(1, 0.15 * cm))

        # ── PAGE 7: CLAIMS PIPELINE FUNNEL & RISK REGISTER ───────────────────────
        if 'claim_status' in df.columns and claim_col:
            try:
                stage_order = ['Registered', 'Under Review', 'Approved', 'Settled']
                # Filter stage_order to only include statuses actually present in df['claim_status']
                unique_statuses = set(df['claim_status'].dropna().unique())
                stage_order = [s for s in stage_order if s in unique_statuses]
                
                raw_vals = {s: df[df['claim_status'] == s][claim_col].sum() for s in stage_order}
                cumulative_vals = {}
                running_sum = 0
                for s in reversed(stage_order):
                    running_sum += raw_vals[s]
                    cumulative_vals[s] = running_sum
                
                funnel_data = [{'Stage': s, 'Value': cumulative_vals[s]} for s in stage_order]
                funnel_df = pd.DataFrame(funnel_data)
                
                import plotly.express as px
                fig_funnel = px.bar(funnel_df, x='Value', y='Stage', orientation='h',
                                    color='Stage', text=funnel_df['Value'].apply(lambda val: f" ₹{val:,.0f} "),
                                    color_discrete_sequence=['#EF4444', '#F59E0B', '#8B5CF6', '#10B981'])
                fig_funnel.update_layout(
                    plot_bgcolor='white', paper_bgcolor='white',
                    margin=dict(t=10, b=25, l=90, r=30),
                    xaxis_title=None, yaxis_title=None,
                    font=dict(family="Calibri, sans-serif", size=10),
                    width=800, height=240, showlegend=False
                )
                fig_funnel.update_xaxes(showgrid=True, gridcolor='#E2E8F0')
                
                png_bytes = fig_funnel.to_image(format='png', scale=2.0)
                img_funnel = Image(io.BytesIO(png_bytes), width=17.4*cm, height=4.2*cm)
                
                elems.append(KeepTogether([
                    Paragraph("CLAIM SETTLEMENT PIPELINE (MUTUALLY EXCLUSIVE PIPELINE VALUE)", S["sec_label"]),
                    img_funnel
                ]))
                elems.append(Spacer(1, 0.15 * cm))
            except Exception as e:
                print(f"[report_helper] Error claims funnel page 7: {e}")
                
        hr_tbl = _draw_high_risk_table(df, S)
        if hr_tbl:
            elems.append(KeepTogether([
                Paragraph("EXECUTIVE HIGH-RISK CLIENT REGISTER (LOSS RATIO > 100%)", S["sec_label"]),
                hr_tbl
            ]))
            elems.append(Spacer(1, 0.15 * cm))

        # ── PAGE 8: UPCOMING RENEWALS CALENDAR ──────────────────────────────────
        elems.append(Paragraph("UPCOMING POLICY EXPIRATIONS & RENEWAL CALENDAR", S["ai_label"]))
        
        ren_chart = _draw_renewal_calendar_chart(df, S)
        if ren_chart:
            elems.append(KeepTogether([
                Paragraph("RENEWAL CALENDAR — POLICIES EXPIRING BY MONTH (NEXT 12 MONTHS)", S["sec_label"]),
                ren_chart
            ]))
            elems.append(Spacer(1, 0.15 * cm))
            
        # At-risk expiration lists
        if 'expiry_date' in df.columns and premium_col:
            try:
                now = pd.Timestamp.today().normalize()
                df2 = df.copy()
                df2['expiry_date'] = pd.to_datetime(df2['expiry_date'], errors='coerce')
                df2['days_to_expiry'] = (df2['expiry_date'] - now).dt.days # type: ignore
                
                b0_30   = df2[(df2['days_to_expiry'] >= 0) & (df2['days_to_expiry'] <= 30)]
                b31_60  = df2[(df2['days_to_expiry'] > 30) & (df2['days_to_expiry'] <= 60)]
                b61_90  = df2[(df2['days_to_expiry'] > 60) & (df2['days_to_expiry'] <= 90)]
                
                th_sub = ParagraphStyle("th_sub", fontName=BODY_B, fontSize=7.5, textColor=WHITE, alignment=TA_CENTER)
                td_sub = ParagraphStyle("td_sub", fontName=BODY, fontSize=8, textColor=BLACK, alignment=TA_CENTER)
                
                rows_exp = [
                    [Paragraph("Window (Days)", th_sub), Paragraph("Policy Count", th_sub), Paragraph("Total Premium at Risk", th_sub)],
                    [Paragraph("0–30 Days", td_sub), Paragraph(f"{len(b0_30):,}", td_sub), Paragraph(_to_indian_format(b0_30[premium_col].sum()), td_sub)],
                    [Paragraph("31–60 Days", td_sub), Paragraph(f"{len(b31_60):,}", td_sub), Paragraph(_to_indian_format(b31_60[premium_col].sum()), td_sub)],
                    [Paragraph("61–90 Days", td_sub), Paragraph(f"{len(b61_90):,}", td_sub), Paragraph(_to_indian_format(b61_90[premium_col].sum()), td_sub)]
                ]
                t_exp = Table(rows_exp, colWidths=[5.8 * cm, 5.8 * cm, 5.8 * cm])
                t_exp.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFBF0"), WHITE]),
                    ("GRID", (0, 0), (-1, -1), 0.25, DIVIDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]))
                elems.append(KeepTogether([
                    Paragraph("UPCOMING RENEWAL EXPOSURE BREAKDOWN", S["sec_label"]),
                    t_exp
                ]))
            except Exception as e:
                print(f"[report_helper] Error renewals table page 8: {e}")

    # ── NATURAL LANGUAGE QUERY SESSION (IF HISTORY EXISTS) ──────────────────
    if history:
        
        u_cnt = sum(1 for m in history if m.get("sender") == "user")
        a_cnt = sum(1 for m in history if m.get("sender") == "ai")
        
        elems.append(Paragraph("NATURAL LANGUAGE QUERY & AI INSIGHTS LOG", S["ai_label"]))
        
        pill  = Table([[Paragraph(
            f"<b>AI Chat Assistant Session</b>  —  This section covers <b>{u_cnt} question(s)</b> with <b>{a_cnt} AI response(s)</b>",
            S["session"]
        )]], colWidths=["100%"])
        pill.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,-1), ICE),
            ("LEFTPADDING",  (0,0),(-1,-1), 12),
            ("RIGHTPADDING", (0,0),(-1,-1), 12),
            ("TOPPADDING",   (0,0),(-1,-1), 7),
            ("BOTTOMPADDING",(0,0),(-1,-1), 7),
            ("LINEBELOW",    (0,0),(-1,-1), 1.5, ORANGE),
        ]))
        elems.append(pill)
        elems.append(Spacer(1, 0.3 * cm))

        q_num = 0
        for msg in history:
            if msg.get("sender") == "user":
                q_num += 1
                block: list[Any] = [
                    Spacer(1, 0.25 * cm),
                    Paragraph(f"QUESTION  {q_num}", S["q_label"]),
                ]
                q_tbl = Table(
                    [[
                        Table([[""]],
                              colWidths=[0.25 * cm],
                              rowHeights=[None]),
                        Paragraph(msg.get("text", ""), S["q_text"])
                    ]],
                    colWidths=[0.35 * cm, None]
                )
                q_tbl.setStyle(TableStyle([
                    ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
                    ("BACKGROUND",   (0,0),(0,-1),  NAVY),
                    ("BACKGROUND",   (1,0),(1,-1),  ICE),
                    ("LEFTPADDING",  (1,0),(1,-1),  12),
                    ("RIGHTPADDING", (1,0),(1,-1),  12),
                    ("TOPPADDING",   (0,0),(-1,-1), 10),
                    ("BOTTOMPADDING",(0,0),(-1,-1), 10),
                    ("LEFTPADDING",  (0,0),(0,-1),  0),
                    ("RIGHTPADDING", (0,0),(0,-1),  0),
                ]))
                block.append(q_tbl)
                elems.append(KeepTogether(block))

            elif msg.get("sender") == "ai":
                # Data & Visualization
                data = msg.get("data")
                if data and isinstance(data, list) and len(data) > 0:
                    try:
                        df_temp = pd.DataFrame(data)
                        for col in df_temp.columns:
                            if pd.api.types.is_numeric_dtype(df_temp[col]):
                                continue
                            try:
                                cleaned = df_temp[col].astype(str).str.replace(r'[₹$,]', '', regex=True).str.strip()
                                df_temp[col] = pd.to_numeric(cleaned, errors='coerce')
                            except Exception:
                                pass
                                
                        num_cols = []
                        cat_cols = []
                        date_cols = []
                        
                        for col in df_temp.columns:
                            col_lower = col.lower()
                            if 'date' in col_lower or 'time' in col_lower or pd.api.types.is_datetime64_any_dtype(df_temp[col]):
                                date_cols.append(col)
                            elif pd.api.types.is_numeric_dtype(df_temp[col]):
                                if 'id' in col_lower or 'code' in col_lower:
                                    cat_cols.append(col)
                                else:
                                    num_cols.append(col)
                            else:
                                cat_cols.append(col)
                                
                        if len(df_temp) == 1 and len(num_cols) == 1:
                            val = df_temp[num_cols[0]].iloc[0]
                            col_name = num_cols[0].replace('_', ' ').title()
                            fmt_val = _format_cell(val)
                            if any(x in col_name.lower() for x in ['premium', 'claim', 'commission', 'brokerage', 'amount', 'earned', 'paid', 'revenue']):
                                if not fmt_val.startswith("Rs."):
                                    fmt_val = _to_indian_format(val)
                            
                            elems.append(Paragraph("KPI METRIC", S["sec_label"]))
                            elems.append(_draw_kpi_card(fmt_val, col_name, S))
                            elems.append(Spacer(1, 0.3 * cm))
                            
                        elif date_cols and num_cols and len(df_temp) > 1:
                            line_chart = _draw_line_chart(data, date_cols[0], num_cols[0], S)
                            if line_chart:
                                elems.append(Paragraph("TREND OVER TIME", S["sec_label"]))
                                elems.append(line_chart)
                                elems.append(Spacer(1, 0.4 * cm))
                                
                        elif num_cols and len(df_temp) > 1:
                            cat_col = str(cat_cols[0]) if cat_cols else str(df_temp.columns[0])
                            val_col = num_cols[0]
                            bar_flowables = _draw_bar_chart_table(data, cat_col, val_col, S)
                            if bar_flowables:
                                elems.append(Paragraph("COMPARATIVE ANALYSIS", S["sec_label"]))
                                elems += bar_flowables
                                elems.append(Spacer(1, 0.4 * cm))
                    except Exception as e:
                        print(f"[report_helper] Error building visualization for PDF: {e}")

                # AI Insights
                elems.append(Paragraph("AI INSIGHTS", S["ai_label"]))

                raw_text = _clean_for_pdf(msg.get("text") or "")
                para_elems = _split_md_paragraphs(raw_text, S)
                elems += para_elems

                # Data table
                data = msg.get("data")
                if data:
                    elems.append(Paragraph("DATA TABLE", S["sec_label"]))
                    elems += _data_table(data, S)

                # SQL
                sql = msg.get("sql")
                if sql:
                    elems.append(Paragraph("SQL QUERY", S["sec_label"]))
                    sql_safe = sql.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    sql_lines = sql_safe.strip().split("\n")
                    sql_content = "<br/>".join(
                        (l if l.strip() else "&nbsp;") for l in sql_lines
                    )
                    sql_box = Table(
                        [[Paragraph(sql_content, S["sql"])]],
                        colWidths=["100%"]
                    )
                    sql_box.setStyle(TableStyle([
                        ("BACKGROUND",    (0,0),(-1,-1), CODEBG),
                        ("LEFTPADDING",   (0,0),(-1,-1), 10),
                        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
                        ("TOPPADDING",    (0,0),(-1,-1), 8),
                        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
                        ("LINEBEFORE",    (0,0),(0,-1),  2.5, NAVY),
                    ]))
                    elems.append(sql_box)

                elems.append(Spacer(1, 0.3 * cm))

    # ── Footer ────────────────────────────────────────────────────────────────
    def _footer_cb(canvas, doc):
        if doc.page == 1:
            return  # Suppress headers/footers on the cover page!
        canvas.saveState()
        canvas.setFont(BODY_I if BODY_I != "Helvetica-Oblique" else "Helvetica-Oblique", 7.5)
        canvas.setFillColor(SILVER)
        canvas.drawString(1.8 * cm, 1.1 * cm,
                          "TVS Insurance Broking Private Limited  |  Confidential Analytics Report")
        canvas.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm,
                               f"Page {doc.page}")
        # Bottom rule
        canvas.setStrokeColor(DIVIDER)
        canvas.setLineWidth(0.5)
        canvas.line(1.8 * cm, 1.5 * cm, A4[0] - 1.8 * cm, 1.5 * cm)
        canvas.restoreState()

    doc.build(elems, onFirstPage=_footer_cb, onLaterPages=_footer_cb)
    buf.seek(0)
    return buf.read()
