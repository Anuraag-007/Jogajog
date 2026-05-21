import os
import tempfile

from reportlab.lib.pagesizes import A5
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
from PIL import Image as PILImage

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE  —  deep navy + sharp white + bold black accents
# ─────────────────────────────────────────────────────────────────────────────
NAVY        = colors.HexColor("#0d1b2a")
STEEL       = colors.HexColor("#1b3a5c")
SLATE       = colors.HexColor("#2e4a6b")
MIST        = colors.HexColor("#e8edf2")
WHITE       = colors.white
BLACK       = colors.HexColor("#0a0a0a")
RULE_DARK   = colors.HexColor("#0d1b2a")
RULE_LIGHT  = colors.HexColor("#c8d0da")
LABEL_GREY  = colors.HexColor("#4a5568")
TEXT_BODY   = colors.HexColor("#1a202c")
ACCENT_LINE = colors.HexColor("#0d1b2a")
RED_BOX     = colors.HexColor("#991b1b")
GREEN_BOX   = colors.HexColor("#14532d")
TOTALS_BG   = colors.HexColor("#f0f4f8")

from utils.paths import INVOICE_DIR
os.makedirs(INVOICE_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _wrap_pts(text, font_name, font_size, max_width_pts):
    return simpleSplit(str(text), font_name, font_size, max_width_pts)


def _parse_discount(discount, base, gst_amt):
    total_before = base + gst_amt
    if isinstance(discount, tuple):
        val, is_pct = discount
        val = float(val)
        if is_pct:
            return f"{val:.2f}%", total_before * val / 100
        return f"₹{val:.2f}", val
    s = str(discount).strip()
    if not s or s in ("0", "0.0"):
        return "", 0.0
    if "%" in s:
        val = float(s.replace("%", "").strip())
        return f"{val:.2f}%", total_before * val / 100
    val = float(s.replace("₹", "").replace("Rs.", "").strip() or 0)
    return (f"₹{val:.2f}" if val else ""), val


def _is_nonzero(val):
    if not val:
        return False
    try:
        return float(str(val).replace("₹", "").replace("%", "").strip()) != 0
    except Exception:
        return bool(val)


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN LAYOUTS  — A5 is 148 × 210 mm; usable width ≈ 130 mm (9 mm margins)
# ─────────────────────────────────────────────────────────────────────────────
_COLS_PLAIN = [
    (9,   52, 'L'),
    (61,  12, 'C'),
    (73,  20, 'R'),
    (93,  16, 'C'),
    (109, 30, 'R'),
]
_HDRS_PLAIN = ["Product", "Qty", "Rate", "GST %", "Amount"]

_COLS_HSN = [
    (9,   40, 'L'),
    (49,  14, 'C'),
    (63,  11, 'C'),
    (74,  19, 'R'),
    (93,  16, 'C'),
    (109, 30, 'R'),
]
_HDRS_HSN = ["Product", "HSN", "Qty", "Rate", "GST %", "Amount"]

_COLS_DISC = [
    (9,   42, 'L'),
    (51,  11, 'C'),
    (62,  18, 'R'),
    (80,  14, 'C'),
    (94,  16, 'R'),
    (110, 29, 'R'),
]
_HDRS_DISC = ["Product", "Qty", "Rate", "GST %", "Disc", "Amount"]

_COLS_HSN_DISC = [
    (9,   34, 'L'),
    (43,  13, 'C'),
    (56,  10, 'C'),
    (66,  17, 'R'),
    (83,  13, 'C'),
    (96,  14, 'R'),
    (110, 29, 'R'),
]
_HDRS_HSN_DISC = ["Product", "HSN", "Qty", "Rate", "GST%", "Disc", "Amount"]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def generate_invoice_pdf(
    filename,
    title,
    header_info,
    table_headers,
    table_rows,
    grand_total,
    invoice_discount=0,
):
    """
    table_rows row format (8 items — preferred):
        [name, description, hsn, qty, rate, gst, discount, amount]

    Backward-compatible formats still accepted:
        [name, hsn, qty, rate, gst, discount, amount]  (7 items — no description)
        [name, hsn, qty, rate, gst, amount]            (6 items — no description, no discount)

    description is printed in smaller italic text below the product name.
    """
    c = canvas.Canvas(filename, pagesize=A5)
    W, H = A5
    header_info = dict(header_info or {})

    TABLE_LEFT  = 9 * mm
    TABLE_RIGHT = W - 9 * mm
    TABLE_W     = TABLE_RIGHT - TABLE_LEFT

    # ── QSettings (graceful fallback) ────────────────────────────────────────
    try:
        from PySide6.QtCore import QSettings
        _qs            = QSettings("MayurSoft", "BillingSoftware")
        BUSINESS_STATE = _qs.value("business_state", "West Bengal")
        _show_qr       = _qs.value("show_qr",    False, type=bool)
        _qr_path       = _qs.value("qr_path",    "")
        _upi_id        = _qs.value("upi_id",     "")
        _show_bank     = _qs.value("show_bank",       False, type=bool)
        _bank_name     = _qs.value("bank_name",       "")
        _bank_ac_no    = _qs.value("bank_account_no", "")
        _bank_ifsc     = _qs.value("bank_ifsc",       "")
        _bank_branch   = _qs.value("bank_branch",     "")
        _show_terms    = _qs.value("show_terms", False, type=bool)
        _terms_text    = _qs.value("terms_text", "")
    except Exception:
        BUSINESS_STATE = "West Bengal"
        _show_qr    = False
        _qr_path    = ""
        _upi_id     = ""
        _show_bank  = False
        _bank_name  = ""
        _bank_ac_no = ""
        _bank_ifsc  = ""
        _bank_branch= ""
        _show_terms = False
        _terms_text = ""

    customer_state = header_info.get("customer_state", "")
    same_state = (
        customer_state.strip().lower() == BUSINESS_STATE.strip().lower()
        if customer_state and BUSINESS_STATE else False
    )

    # Detect column visibility — check position 2 (hsn) and 6 (discount) for
    # 8-item rows; fall back to legacy positions 1 and 5.
    def _hsn_val(r):
        return r[2] if len(r) >= 8 else (r[1] if len(r) > 1 else "")

    def _disc_val(r):
        return r[6] if len(r) >= 8 else (r[5] if len(r) > 5 else 0)

    show_hsn      = any(_hsn_val(r) for r in table_rows)
    show_discount = any(_is_nonzero(_disc_val(r)) for r in table_rows)

    if show_hsn and show_discount:
        cols, hdr_labels = _COLS_HSN_DISC, _HDRS_HSN_DISC
    elif show_hsn:
        cols, hdr_labels = _COLS_HSN, _HDRS_HSN
    elif show_discount:
        cols, hdr_labels = _COLS_DISC, _HDRS_DISC
    else:
        cols, hdr_labels = _COLS_PLAIN, _HDRS_PLAIN

    product_col_w_pts = cols[0][1] * mm - 3 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # LOW-LEVEL DRAW HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _filled_rect(x, y, w, h, fill, stroke=None, lw=0.4, radius=0):
        c.saveState()
        c.setFillColor(fill)
        if stroke:
            c.setStrokeColor(stroke)
            c.setLineWidth(lw)
            if radius:
                c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
            else:
                c.rect(x, y, w, h, fill=1, stroke=1)
        else:
            if radius:
                c.roundRect(x, y, w, h, radius, fill=1, stroke=0)
            else:
                c.rect(x, y, w, h, fill=1, stroke=0)
        c.restoreState()

    def _hline(y_pt, x0=None, x1=None, lw=0.5, clr=RULE_LIGHT):
        c.saveState()
        c.setStrokeColor(clr)
        c.setLineWidth(lw)
        c.line(x0 if x0 is not None else TABLE_LEFT,
               y_pt,
               x1 if x1 is not None else TABLE_RIGHT,
               y_pt)
        c.restoreState()

    def _vline(x_pt, y0, y1, lw=0.35, clr=RULE_LIGHT):
        c.saveState()
        c.setStrokeColor(clr)
        c.setLineWidth(lw)
        c.line(x_pt, y0, x_pt, y1)
        c.restoreState()

    def _col_text(cx_mm, cw_mm, align, py, text,
                  font="Helvetica", size=7.5, clr=TEXT_BODY):
        c.saveState()
        c.setFont(font, size)
        c.setFillColor(clr)
        pad = 1.5 * mm
        if align == 'R':
            c.drawRightString((cx_mm + cw_mm) * mm - pad, py, str(text))
        elif align == 'C':
            c.drawCentredString((cx_mm + cw_mm / 2) * mm, py, str(text))
        else:
            c.drawString(cx_mm * mm + pad, py, str(text))
        c.restoreState()

    def _draw_col_dividers(y_top, y_bot, lw=0.35):
        for cx, cw, _ in cols[:-1]:
            _vline((cx + cw) * mm, y_bot, y_top, lw=lw, clr=RULE_LIGHT)

    # ─────────────────────────────────────────────────────────────────────────
    # HEADER BAND
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_header_band():
        HDR_H = 38 * mm
        _filled_rect(0, H - HDR_H, W, HDR_H, NAVY)

        stripe_clr = colors.HexColor("#162840")
        for sx in [W * 0.55, W * 0.68, W * 0.81]:
            stripe_w = 18 * mm
            pts = [
                sx,              H,
                sx + stripe_w,   H,
                sx + stripe_w - 12 * mm, H - HDR_H,
                sx - 12 * mm,    H - HDR_H,
            ]
            c.saveState()
            c.setFillColor(stripe_clr)
            path = c.beginPath()
            path.moveTo(pts[0], pts[1])
            path.lineTo(pts[2], pts[3])
            path.lineTo(pts[4], pts[5])
            path.lineTo(pts[6], pts[7])
            path.close()
            c.clipPath(path, stroke=0, fill=1)
            c.restoreState()

        c.setStrokeColor(WHITE)
        c.setLineWidth(2.5)
        c.line(0, H - HDR_H, W, H - HDR_H)

        badge_cx = 18 * mm
        badge_cy = H - HDR_H / 2
        badge_r  = 10 * mm

        c.setStrokeColor(WHITE)
        c.setLineWidth(1.5)
        c.setFillColor(STEEL)
        c.circle(badge_cx, badge_cy, badge_r, fill=1, stroke=1)

        logo_path = "Automate.ico"
        if os.path.exists(logo_path):
            try:
                img = PILImage.open(logo_path).convert("RGBA")
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                img.save(tmp.name, "PNG")
                sz = badge_r * 1.5
                c.drawImage(tmp.name,
                            badge_cx - sz / 2, badge_cy - sz / 2,
                            width=sz, height=sz,
                            preserveAspectRatio=True, mask='auto')
                os.unlink(tmp.name)
            except Exception as e:
                print("Logo Error:", e)

        from utils.company import COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE
        info_x = 31 * mm

        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(info_x, H - 10 * mm, COMPANY_NAME())

        c.setFont("Helvetica", 7)
        c.setFillColor(colors.HexColor("#a0b4c8"))
        c.drawString(info_x, H - 16 * mm, "Premium Technology & Consulting Services")

        c.setFillColor(colors.HexColor("#7a94a8"))
        c.setFont("Helvetica", 6.5)
        if COMPANY_ADDRESS:
            c.drawString(info_x, H - 22 * mm, COMPANY_ADDRESS())
        if COMPANY_PHONE:
            c.drawString(info_x, H - 27 * mm, f"Ph: {COMPANY_PHONE()}")

        _total_due   = header_info.get("total_due",   None)
        _net_payable = header_info.get("net_payable", None)

        if _total_due is not None:
            box_w = 36 * mm
            box_h = 11 * mm
            box_x = W - box_w - 7 * mm

            if _net_payable is not None:
                net_y = H - 14 * mm
                _filled_rect(box_x, net_y, box_w, box_h, GREEN_BOX)
                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 5.5)
                c.drawString(box_x + 2 * mm, net_y + box_h - 4 * mm, "NET PAYABLE")
                c.setFont("Helvetica-Bold", 9)
                c.drawString(box_x + 2 * mm, net_y + 2 * mm, f"₹ {_net_payable:,.2f}")
                due_y = net_y - box_h - 1.5 * mm
            else:
                due_y = H - 14 * mm

            _filled_rect(box_x, due_y, box_w, box_h, RED_BOX)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 5.5)
            c.drawString(box_x + 2 * mm, due_y + box_h - 4 * mm, "TOTAL DUE")
            c.setFont("Helvetica-Bold", 9)
            c.drawString(box_x + 2 * mm, due_y + 2 * mm, f"₹ {_total_due:,.2f}")

        return H - HDR_H

    # ─────────────────────────────────────────────────────────────────────────
    # META SECTION
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_meta_section(y):
        left_x  = TABLE_LEFT
        right_x = W / 2 + 2 * mm
        sec_h   = 30 * mm

        _filled_rect(0, y - sec_h, W, sec_h, MIST)

        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(left_x, y - 9 * mm, title.upper())

        _hline(y - 10.5 * mm, x0=left_x, x1=left_x + 48 * mm, lw=1.5, clr=NAVY)

        c.setFillColor(LABEL_GREY)
        c.setFont("Helvetica-Oblique", 6.5)
        c.drawString(left_x, y - 14 * mm, "Original for Recipient")

        def _kv(label, value, cy):
            c.setFillColor(LABEL_GREY)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(left_x, cy, label)
            c.setFillColor(TEXT_BODY)
            c.setFont("Helvetica", 6.5)
            c.drawString(left_x + 20 * mm, cy, str(value))
            return cy - 5 * mm

        ky = y - 18 * mm
        ky = _kv("Invoice No :", header_info.get("invoice_no", ""), ky)
        ky = _kv("Date :",       header_info.get("date_time",  ""), ky)

        _vline(W / 2, y - sec_h + 3 * mm, y - 2 * mm, lw=0.6, clr=RULE_LIGHT)

        bx = right_x
        by = y - 5 * mm

        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 6)
        c.drawString(bx, by, "BILL TO")
        by -= 4.5 * mm

        c.setFillColor(TEXT_BODY)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(bx, by, header_info.get("customer_name", ""))
        by -= 5 * mm

        c.setFont("Helvetica", 6.5)
        c.setFillColor(LABEL_GREY)
        phone = header_info.get("customer_phone", "")
        addr  = header_info.get("customer_address", "")
        gst_n = header_info.get("customer_gst", "")
        max_w = (W - right_x - 7 * mm)

        if phone:
            c.drawString(bx, by, phone); by -= 4.5 * mm
        if addr:
            for ln in simpleSplit(addr, "Helvetica", 6.5, max_w):
                c.drawString(bx, by, ln); by -= 4.5 * mm
        if gst_n:
            c.drawString(bx, by, f"GSTIN: {gst_n}"); by -= 4.5 * mm

        _hline(y - sec_h, x0=0, x1=W, lw=2, clr=NAVY)

        return y - sec_h - 1 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # TABLE HEADER
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_table_header(y):
        hdr_h = 7 * mm
        _filled_rect(TABLE_LEFT, y - hdr_h, TABLE_W, hdr_h, STEEL)
        _draw_col_dividers(y, y - hdr_h, lw=0.5)

        for (cx, cw, align), label in zip(cols, hdr_labels):
            _col_text(cx, cw, align, y - 4.8 * mm, label,
                      font="Helvetica-Bold", size=7, clr=WHITE)

        c.setStrokeColor(WHITE)
        c.setLineWidth(0.8)
        c.line(TABLE_LEFT, y - hdr_h, TABLE_RIGHT, y - hdr_h)

        return y - hdr_h

    # ─────────────────────────────────────────────────────────────────────────
    # FIRST PAGE
    # ─────────────────────────────────────────────────────────────────────────
    y = _draw_header_band()
    y = _draw_meta_section(y)
    y = _draw_table_header(y)

    # ─────────────────────────────────────────────────────────────────────────
    # TABLE ROWS
    # ─────────────────────────────────────────────────────────────────────────
    sub_total      = 0.0
    gst_total      = 0.0
    discount_total = 0.0
    cgst_total     = 0.0
    sgst_total     = 0.0
    igst_total     = 0.0
    last_gst_pct   = 0.0

    LINE_H    = 9       # pts per text line (smaller for A5)
    DESC_SIZE = 6.5
    MIN_Y     = 38 * mm

    row_alt = False

    for row_idx, row in enumerate(table_rows):
        # Unpack — supports 8-item rows (with description) and legacy 6/7-item rows.
        if len(row) >= 8:
            name, description, hsn, qty, rate, gst, discount, amount = row[:8]
        elif len(row) == 7:
            name, hsn, qty, rate, gst, discount, amount = row
            description = ""
        elif len(row) == 6:
            name, hsn, qty, rate, gst, amount = row
            discount = 0
            description = ""
        else:
            continue

        discount = discount if discount not in ("", None) else 0
        qty      = float(qty)
        rate     = float(rate)
        gst_pct  = float(str(gst).replace("%", "").strip())
        amount   = float(amount)

        base     = qty * rate
        gst_amt  = base * gst_pct / 100
        net_rate = rate * (1 + gst_pct / 100)

        sub_total    += base
        gst_total    += gst_amt
        last_gst_pct  = gst_pct

        if same_state:
            cgst_total += gst_amt / 2
            sgst_total += gst_amt / 2
        else:
            igst_total += gst_amt

        discount_display, discount_amt = _parse_discount(discount, base, gst_amt)
        discount_total += discount_amt

        qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.2f}"

        if show_hsn and show_discount:
            values = [str(name), str(hsn or ""), qty_str,
                      f"{rate:.2f}", f"{gst_pct:.1f}%",
                      discount_display, f"{amount:.2f}"]
        elif show_hsn:
            values = [str(name), str(hsn or ""), qty_str,
                      f"{rate:.2f}", f"{gst_pct:.1f}%", f"{amount:.2f}"]
        elif show_discount:
            values = [str(name), qty_str,
                      f"{rate:.2f}", f"{gst_pct:.1f}%",
                      discount_display, f"{amount:.2f}"]
        else:
            values = [str(name), qty_str,
                      f"{rate:.2f}", f"{gst_pct:.1f}%", f"{amount:.2f}"]

        # Wrap product name and description separately.
        wrapped      = _wrap_pts(values[0], "Helvetica", 7.5, product_col_w_pts)
        desc_wrapped = (
            _wrap_pts(str(description), "Helvetica-Oblique", DESC_SIZE, product_col_w_pts)
            if description else []
        )
        n_lines = max(1, len(wrapped)) + len(desc_wrapped)
        row_h   = n_lines * LINE_H + 5

        if y - row_h < MIN_Y:
            c.showPage()
            y = H - 10 * mm
            y = _draw_table_header(y)
            row_alt = False

        if row_alt:
            _filled_rect(TABLE_LEFT, y - row_h, TABLE_W, row_h, MIST)
        row_alt = not row_alt

        c.setStrokeColor(RULE_LIGHT)
        c.setLineWidth(0.25)
        c.rect(TABLE_LEFT, y - row_h, TABLE_W, row_h, fill=0, stroke=1)

        _draw_col_dividers(y, y - row_h)

        # Product name (wrapped).
        for li, wline in enumerate(wrapped):
            c.setFont("Helvetica", 7.5)
            c.setFillColor(TEXT_BODY)
            py = y - LINE_H - li * LINE_H + 1
            c.drawString(cols[0][0] * mm + 1.5 * mm, py, wline)

        # Description (italic, muted, smaller) — printed below the name.
        if desc_wrapped:
            desc_base_y = y - LINE_H - len(wrapped) * LINE_H + 1
            for li, dline in enumerate(desc_wrapped):
                c.setFont("Helvetica-Oblique", DESC_SIZE)
                c.setFillColor(LABEL_GREY)
                c.drawString(cols[0][0] * mm + 1.5 * mm, desc_base_y - li * LINE_H, dline)

        # Remaining column values aligned to the first line.
        text_y = y - LINE_H + 1
        for (cx, cw, align), val in zip(cols[1:], values[1:]):
            _col_text(cx, cw, align, text_y, val, size=7.5)

        y -= row_h

        if y < MIN_Y:
            c.showPage()
            y = H - 10 * mm
            y = _draw_table_header(y)
            row_alt = False

    c.setStrokeColor(NAVY)
    c.setLineWidth(1.2)
    c.line(TABLE_LEFT, y, TABLE_RIGHT, y)

    # ─────────────────────────────────────────────────────────────────────────
    # TOTALS SECTION
    # ─────────────────────────────────────────────────────────────────────────
    y -= 4 * mm

    product_discount = max(0.0, discount_total - invoice_discount)

    n_tot_rows  = 2
    n_tot_rows += 2 if same_state else 1
    if show_discount and product_discount > 0:
        n_tot_rows += 1
    if invoice_discount > 0:
        n_tot_rows += 1
    n_tot_rows += 1

    tot_row_h    = 5.5 * mm
    totals_box_x = W / 2 + 2 * mm
    totals_box_w = TABLE_RIGHT - totals_box_x
    totals_box_h = n_tot_rows * tot_row_h + 6 * mm

    if y - totals_box_h < MIN_Y:
        c.showPage()
        y = H - 10 * mm

    _filled_rect(totals_box_x, y - totals_box_h, totals_box_w, totals_box_h,
                 TOTALS_BG, stroke=RULE_LIGHT, lw=0.4)

    LABEL_X = totals_box_x + 2 * mm
    VALUE_X = totals_box_x + totals_box_w - 2 * mm
    ty      = y - 3 * mm

    def _tot_line(label, value, bold=False, highlight=False):
        nonlocal ty
        if highlight:
            _filled_rect(totals_box_x, ty - 4 * mm, totals_box_w, 6 * mm, NAVY)
            c.setFillColor(WHITE)
        else:
            c.setFillColor(TEXT_BODY)
        fnt = "Helvetica-Bold" if (bold or highlight) else "Helvetica"
        sz  = 8.5 if highlight else 7
        c.setFont(fnt, sz)
        c.drawString(LABEL_X, ty, label)
        c.drawRightString(VALUE_X, ty, value)
        ty -= tot_row_h

    _tot_line("Subtotal (Before Tax):", f"₹ {sub_total:,.2f}")

    if same_state:
        _tot_line(f"CGST @ {last_gst_pct/2:.1f}%:", f"₹ {cgst_total:,.2f}")
        _tot_line(f"SGST @ {last_gst_pct/2:.1f}%:", f"₹ {sgst_total:,.2f}")
    else:
        _tot_line("IGST Total:", f"₹ {igst_total:,.2f}")

    if show_discount and product_discount > 0:
        _tot_line("Product Discount:", f"(-) ₹ {product_discount:,.2f}")
    if invoice_discount > 0:
        _tot_line("Invoice Discount:", f"(-) ₹ {invoice_discount:,.2f}")

    _tot_line("Round Off:", "(-) 0.00")
    _tot_line("GRAND TOTAL:", f"₹ {grand_total:,.2f}", bold=True, highlight=True)

    if header_info.get("amount_paid"):
        paid    = float(header_info["amount_paid"])
        balance = grand_total - paid
        _tot_line("Amount Paid:", f"(-) ₹ {paid:,.2f}")
        _filled_rect(totals_box_x, ty - 4 * mm, totals_box_w, 6 * mm, RED_BOX)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(LABEL_X, ty, "BALANCE DUE:")
        c.drawRightString(VALUE_X, ty, f"₹ {balance:,.2f}")
        ty -= tot_row_h

    words_x = TABLE_LEFT
    words_y = y - totals_box_h + totals_box_h / 2
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColor(NAVY)
    c.drawString(words_x, words_y + 4 * mm, "Amount in Words:")
    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColor(LABEL_GREY)
    amt_words = header_info.get("amount_in_words", "")
    for ln in simpleSplit(amt_words, "Helvetica-Oblique", 6.5, (W / 2 - TABLE_LEFT - 4 * mm)):
        c.drawString(words_x, words_y, ln)
        words_y -= 4.5 * mm

    y = y - totals_box_h - 5 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # FOOTER  —  2-column: Bank+Terms left | Signature right
    # ─────────────────────────────────────────────────────────────────────────
    footer_h = 30 * mm

    if y - footer_h < 10 * mm:
        c.showPage()
        y = H - 10 * mm

    _filled_rect(TABLE_LEFT, y - footer_h, TABLE_W, footer_h,
                 MIST, stroke=RULE_LIGHT, lw=0.5)

    split_x = TABLE_LEFT + TABLE_W * 0.60
    _vline(split_x, y - footer_h, y, lw=0.5, clr=RULE_LIGHT)

    from utils.company import COMPANY_NAME

    def _ft(x, cy, text):
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(x + 2 * mm, cy, text)

    def _fkv(x, cy, label, value, max_w):
        c.setFont("Helvetica-Bold", 6)
        c.setFillColor(LABEL_GREY)
        c.drawString(x + 2 * mm, cy, label)
        c.setFont("Helvetica", 6)
        c.setFillColor(TEXT_BODY)
        for ln in simpleSplit(str(value), "Helvetica", 6, max_w - 18 * mm):
            c.drawString(x + 2 * mm + 16 * mm, cy, ln)
            cy -= 4 * mm
        return cy

    left_max_w = split_x - TABLE_LEFT
    fy = y - 4 * mm

    if _show_bank:
        _ft(TABLE_LEFT, fy, "BANK DETAILS")
        fy -= 5 * mm
        bank_rows = [
            ("Bank :",    _bank_name),
            ("Branch :",  _bank_branch),
            ("A/C No. :", _bank_ac_no),
            ("IFSC :",    _bank_ifsc),
        ]
        for lbl, val in bank_rows:
            if val:
                fy = _fkv(TABLE_LEFT, fy, lbl, val, left_max_w)
    else:
        _ft(TABLE_LEFT, fy, "TERMS & CONDITIONS")
        fy -= 5 * mm

        if _show_terms and _terms_text.strip():
            terms = [ln.strip() for ln in _terms_text.splitlines() if ln.strip()]
        else:
            terms = [
                "1. Payment due within 15 days.",
                "2. Late payment: 18% p.a. interest.",
                "3. Goods once sold not returnable.",
                "4. Subject to local jurisdiction.",
                "5. E. & O.E.",
            ]

        c.setFont("Helvetica", 6)
        c.setFillColor(LABEL_GREY)
        for line in terms:
            if fy < y - footer_h + 3 * mm:
                break
            c.drawString(TABLE_LEFT + 2 * mm, fy, str(line))
            fy -= 4 * mm

    if _show_bank and fy > y - footer_h + 8 * mm:
        _ft(TABLE_LEFT, fy, "TERMS & CONDITIONS")
        fy -= 5 * mm
        if _show_terms and _terms_text.strip():
            terms = [ln.strip() for ln in _terms_text.splitlines() if ln.strip()]
        else:
            terms = ["1. Goods once sold not returnable.",
                     "2. Subject to local jurisdiction."]
        c.setFont("Helvetica", 6)
        c.setFillColor(LABEL_GREY)
        for line in terms:
            if fy < y - footer_h + 3 * mm:
                break
            c.drawString(TABLE_LEFT + 2 * mm, fy, str(line))
            fy -= 4 * mm

    sig_col_x = split_x
    sy = y - 4 * mm
    _ft(sig_col_x, sy, f"FOR {COMPANY_NAME()}")

    sig_line_y = y - footer_h + 10 * mm
    sig_start  = sig_col_x + 4 * mm
    sig_end    = TABLE_RIGHT - 3 * mm

    c.setStrokeColor(NAVY)
    c.setLineWidth(0.6)
    c.line(sig_start, sig_line_y, sig_end, sig_line_y)

    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(NAVY)
    c.drawCentredString((sig_start + sig_end) / 2,
                        sig_line_y - 4 * mm, "Authorised Signatory")
    c.setFont("Helvetica-Oblique", 5.5)
    c.setFillColor(LABEL_GREY)
    c.drawCentredString((sig_start + sig_end) / 2,
                        sig_line_y - 7.5 * mm, "(Stamp & Signature)")

    y -= footer_h + 4 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # QR CODE
    # ─────────────────────────────────────────────────────────────────────────
    if _show_qr and _qr_path and os.path.exists(_qr_path):
        try:
            qr_size = 20 * mm
            qr_x    = TABLE_LEFT
            qr_y    = y - qr_size - 3 * mm

            if qr_y > 10 * mm:
                _filled_rect(qr_x, qr_y + qr_size, 28 * mm, 5 * mm, NAVY)
                c.setFillColor(WHITE)
                c.setFont("Helvetica-Bold", 5.5)
                c.drawString(qr_x + 1.5 * mm,
                             qr_y + qr_size + 1.5 * mm, "SCAN & PAY via UPI")

                c.drawImage(_qr_path, qr_x, qr_y,
                            width=qr_size, height=qr_size,
                            preserveAspectRatio=True, mask='auto')

                c.setFont("Helvetica", 5.5)
                c.setFillColor(LABEL_GREY)
                c.drawString(qr_x, qr_y - 4 * mm, f"UPI: {_upi_id}")

        except Exception as e:
            print("QR Error:", e)

    # ─────────────────────────────────────────────────────────────────────────
    # DARK FOOTER BAR
    # ─────────────────────────────────────────────────────────────────────────
    _filled_rect(0, 0, W, 8 * mm, NAVY)

    c.setFillColor(colors.HexColor("#8899aa"))
    c.setFont("Helvetica", 5.5)

    from utils.company import COMPANY_NAME as _CN
    footer_text = f"{_CN()}  ·  info@company.in  ·  +91-000-000-0000"
    c.drawCentredString(W / 2, 2.5 * mm, footer_text)

    c.save()
