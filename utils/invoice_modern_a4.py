import os
import tempfile

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
from PIL import Image as PILImage

# ─────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE
# ─────────────────────────────────────────────────────────────────────────────
DARK_BG      = colors.HexColor("#1a1f2e")
GOLD         = colors.HexColor("#c9a84c")
RED_BOX      = colors.HexColor("#c0392b")
GREEN_BOX    = colors.HexColor("#1e7e52")
TABLE_HDR_BG = colors.HexColor("#2c3347")
TABLE_HDR_FG = colors.white
ROW_ALT      = colors.HexColor("#f7f8fc")
LABEL_GREY   = colors.HexColor("#555555")
BORDER_LIGHT = colors.HexColor("#dddddd")
TEXT_DARK    = colors.HexColor("#1a1a2e")
TOTALS_BG    = colors.HexColor("#f5f7fa")

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
# COLUMN LAYOUTS  — perfectly contiguous (start_x + width == next start_x)
# All x values in mm.  Table spans 10 mm → 200 mm (190 mm wide).
# ─────────────────────────────────────────────────────────────────────────────
_COLS_PLAIN = [
    (10,  72, 'L'),
    (82,  14, 'C'),
    (96,  20, 'R'),
    (116, 22, 'R'),
    (138, 15, 'C'),
    (153, 47, 'R'),
]
_HDRS_PLAIN = ["Product", "Qty", "Rate", "Net Rate", "GST %", "Amount"]

_COLS_HSN = [
    (10,  55, 'L'),
    (65,  15, 'C'),
    (80,  14, 'C'),
    (94,  20, 'R'),
    (114, 22, 'R'),
    (136, 15, 'C'),
    (151, 49, 'R'),
]
_HDRS_HSN = ["Product", "HSN", "Qty", "Rate", "Net Rate", "GST %", "Amount"]

_COLS_DISC = [
    (10,  58, 'L'),
    (68,  14, 'C'),
    (82,  20, 'R'),
    (102, 22, 'R'),
    (124, 15, 'C'),
    (139, 20, 'R'),
    (159, 41, 'R'),
]
_HDRS_DISC = ["Product", "Qty", "Rate", "Net Rate", "GST %", "Discount", "Amount"]

_COLS_HSN_DISC = [
    (10,  48, 'L'),
    (58,  15, 'C'),
    (73,  13, 'C'),
    (86,  19, 'R'),
    (105, 19, 'R'),
    (124, 14, 'C'),
    (138, 20, 'R'),
    (158, 42, 'R'),
]
_HDRS_HSN_DISC = ["Product", "HSN", "Qty", "Rate", "Net Rate", "GST %", "Discount", "Amount"]


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
    c = canvas.Canvas(filename, pagesize=A4)
    W, H = A4
    header_info = dict(header_info or {})

    TABLE_LEFT  = 10 * mm
    TABLE_RIGHT = W - 10 * mm
    TABLE_W     = TABLE_RIGHT - TABLE_LEFT

    # ── QSettings (graceful fallback) ────────────────────────────────────────
    try:
        from PySide6.QtCore import QSettings
        _qs            = QSettings("MayurSoft", "BillingSoftware")
        BUSINESS_STATE = _qs.value("business_state", "West Bengal")
        _show_qr       = _qs.value("show_qr", False, type=bool)
        _qr_path       = _qs.value("qr_path", "")
        _upi_id        = _qs.value("upi_id", "")
        _show_bank     = _qs.value("show_bank",      False, type=bool)
        _bank_name     = _qs.value("bank_name",      "")
        _bank_ac_no    = _qs.value("bank_account_no","")
        _bank_ifsc     = _qs.value("bank_ifsc",      "")
        _bank_branch   = _qs.value("bank_branch",    "")
        _show_terms    = _qs.value("show_terms", False, type=bool)
        _terms_text    = _qs.value("terms_text", "")
    except Exception:
        BUSINESS_STATE = "West Bengal"
        _show_qr       = False
        _qr_path       = ""
        _upi_id        = ""
        _show_bank     = False
        _bank_name     = ""
        _bank_ac_no    = ""
        _bank_ifsc     = ""
        _bank_branch   = ""
        _show_terms    = False
        _terms_text    = ""

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

    product_col_w_pts = cols[0][1] * mm - 4 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # LOW-LEVEL DRAW HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _filled_rect(x, y, w, h, fill, stroke=None, lw=0.5, radius=0):
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

    def _hline(y_pt, x0=None, x1=None, lw=0.5, color=BORDER_LIGHT):
        c.saveState()
        c.setStrokeColor(color)
        c.setLineWidth(lw)
        c.line(x0 if x0 is not None else TABLE_LEFT,
               y_pt,
               x1 if x1 is not None else TABLE_RIGHT,
               y_pt)
        c.restoreState()

    def _vline(x_pt, y0, y1, lw=0.4, color=BORDER_LIGHT):
        c.saveState()
        c.setStrokeColor(color)
        c.setLineWidth(lw)
        c.line(x_pt, y0, x_pt, y1)
        c.restoreState()

    def _col_text(cx_mm, cw_mm, align, py, text,
                  font="Helvetica", size=9, color=TEXT_DARK):
        c.saveState()
        c.setFont(font, size)
        c.setFillColor(color)
        pad = 2 * mm
        if align == 'R':
            c.drawRightString((cx_mm + cw_mm) * mm - pad, py, str(text))
        elif align == 'C':
            c.drawCentredString((cx_mm + cw_mm / 2) * mm, py, str(text))
        else:
            c.drawString(cx_mm * mm + pad, py, str(text))
        c.restoreState()

    def _draw_col_dividers(y_top, y_bot, line_width=0.4):
        for cx, cw, _ in cols[:-1]:
            _vline((cx + cw) * mm, y_bot, y_top, lw=line_width, color=BORDER_LIGHT)

    # ─────────────────────────────────────────────────────────────────────────
    # DARK HEADER BAND
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_header_band():
        header_h = 48 * mm
        _filled_rect(0, H - header_h, W, header_h, DARK_BG)

        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.line(0, H - header_h, W, H - header_h)

        badge_cx = 22 * mm
        badge_cy = H - header_h / 2
        badge_r  = 13 * mm

        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.setFillColor(DARK_BG)
        c.circle(badge_cx, badge_cy, badge_r, fill=1, stroke=1)

        logo_path = "Automate.ico"
        if os.path.exists(logo_path):
            try:
                img = PILImage.open(logo_path).convert("RGBA")
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                img.save(tmp.name, "PNG")
                sz = badge_r * 1.4
                c.drawImage(tmp.name,
                            badge_cx - sz / 2, badge_cy - sz / 2,
                            width=sz, height=sz,
                            preserveAspectRatio=True, mask='auto')
                os.unlink(tmp.name)
            except Exception as e:
                print("Logo Error:", e)

        from utils.company import COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE
        name_x = 38 * mm

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(name_x, H - 14 * mm, COMPANY_NAME())

        c.setFillColor(GOLD)
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(name_x, H - 20 * mm, "Premium Technology & Consulting Services")

        c.setFillColor(colors.HexColor("#bbbbbb"))
        c.setFont("Helvetica", 8)
        if COMPANY_ADDRESS:
            c.drawString(name_x, H - 27 * mm, COMPANY_ADDRESS())
        if COMPANY_PHONE:
            c.drawString(name_x, H - 33 * mm, f"Ph: {COMPANY_PHONE()}")

        _total_due   = header_info.get("total_due",   None)
        _net_payable = header_info.get("net_payable", None)

        if _total_due is not None:
            box_w, box_h = 50 * mm, 17 * mm
            box_x = W - box_w - 10 * mm

            if _net_payable is not None:
                net_y = H - 22 * mm
                _filled_rect(box_x, net_y, box_w, box_h, GREEN_BOX)
                c.setFillColor(colors.white)
                c.setFont("Helvetica-Bold", 7)
                c.drawString(box_x + 2 * mm, net_y + box_h - 5 * mm, "NET PAYABLE")
                c.setFont("Helvetica-Bold", 14)
                c.drawString(box_x + 2 * mm, net_y + 2 * mm, f"₹ {_net_payable:,.2f}")
                total_due_y = net_y - box_h - 2 * mm
            else:
                total_due_y = H - 22 * mm

            _filled_rect(box_x, total_due_y, box_w, box_h, RED_BOX)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(box_x + 2 * mm, total_due_y + box_h - 5 * mm, "TOTAL DUE")
            c.setFont("Helvetica-Bold", 14)
            c.drawString(box_x + 2 * mm, total_due_y + 2 * mm, f"₹ {_total_due:,.2f}")

        return H - header_h

    # ─────────────────────────────────────────────────────────────────────────
    # INVOICE TITLE + META  (left)  &  BILL TO  (right)
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_meta_section(y):
        left_x  = 12 * mm
        mid_x   = W / 2 - 5 * mm

        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 28)
        c.drawString(left_x, y - 10 * mm, title.upper())

        c.setFillColor(LABEL_GREY)
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(left_x, y - 16 * mm, "Original for Recipient")

        meta_y = y - 26 * mm

        def _meta_row(label, value, cy):
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(left_x, cy, label)
            c.setFont("Helvetica", 9)
            c.drawString(left_x + 28 * mm, cy, str(value))
            return cy - 6 * mm

        meta_y = _meta_row("Invoice No. :",  header_info.get("invoice_no", ""),    meta_y)
        meta_y = _meta_row("Invoice Date :", header_info.get("date_time", ""),     meta_y)
        meta_y = _meta_row("Due Date :",     header_info.get("due_date", ""),      meta_y)
        meta_y = _meta_row("P.O. Number :",  header_info.get("po_number", ""),     meta_y)
        _meta_row("Payment Terms :", header_info.get("payment_terms", "Net 15 Days"), meta_y)

        bill_top = y - 8 * mm

        def _address_block(cx, cy, section_label):
            c.setFillColor(GOLD)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(cx, cy, section_label + ":")
            cy -= 6 * mm
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(cx, cy, header_info.get("customer_name", ""))
            cy -= 5 * mm
            c.setFont("Helvetica", 8)
            c.setFillColor(LABEL_GREY)
            phone = header_info.get("customer_phone", "")
            addr  = header_info.get("customer_address", "")
            gst   = header_info.get("customer_gst", "")
            if phone:
                c.drawString(cx, cy, phone);  cy -= 5 * mm
            if addr:
                for line in simpleSplit(addr, "Helvetica", 8, 52 * mm):
                    c.drawString(cx, cy, line); cy -= 5 * mm
            if gst:
                c.drawString(cx, cy, f"GST: {gst}"); cy -= 5 * mm
            return cy

        _address_block(mid_x, bill_top, "BILL TO")

        sep_y = y - 52 * mm
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        c.line(10 * mm, sep_y, W - 10 * mm, sep_y)
        return sep_y - 10 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # TABLE HEADER ROW
    # ─────────────────────────────────────────────────────────────────────────

    def _draw_table_header(y):
        hdr_h = 10 * mm
        _filled_rect(TABLE_LEFT, y - hdr_h, TABLE_W, hdr_h, TABLE_HDR_BG)
        _draw_col_dividers(y, y - hdr_h, line_width=0.5)
        for (cx, cw, align), label in zip(cols, hdr_labels):
            _col_text(cx, cw, align, y - 6.5 * mm, label,
                      font="Helvetica-Bold", size=8.5, color=TABLE_HDR_FG)
        c.setStrokeColor(GOLD)
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

    LINE_H    = 11     # pts per text line
    DESC_SIZE = 7.5
    MIN_Y     = 50 * mm

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
                      f"{rate:.2f}", f"{net_rate:.2f}",
                      f"{gst_pct:.1f}%", discount_display, f"{amount:.2f}"]
        elif show_hsn:
            values = [str(name), str(hsn or ""), qty_str,
                      f"{rate:.2f}", f"{net_rate:.2f}",
                      f"{gst_pct:.1f}%", f"{amount:.2f}"]
        elif show_discount:
            values = [str(name), qty_str,
                      f"{rate:.2f}", f"{net_rate:.2f}",
                      f"{gst_pct:.1f}%", discount_display, f"{amount:.2f}"]
        else:
            values = [str(name), qty_str,
                      f"{rate:.2f}", f"{net_rate:.2f}",
                      f"{gst_pct:.1f}%", f"{amount:.2f}"]

        # Wrap product name and description separately.
        wrapped      = _wrap_pts(values[0], "Helvetica", 9, product_col_w_pts)
        desc_wrapped = (
            _wrap_pts(str(description), "Helvetica-Oblique", DESC_SIZE, product_col_w_pts)
            if description else []
        )
        n_lines = max(1, len(wrapped)) + len(desc_wrapped)
        row_h   = n_lines * LINE_H + 7

        if y - row_h < MIN_Y:
            c.showPage()
            y = H - 15 * mm
            y = _draw_table_header(y)
            row_alt = False

        if row_alt:
            _filled_rect(TABLE_LEFT, y - row_h, TABLE_W, row_h, ROW_ALT)
        row_alt = not row_alt

        c.setStrokeColor(BORDER_LIGHT)
        c.setLineWidth(0.3)
        c.rect(TABLE_LEFT, y - row_h, TABLE_W, row_h, fill=0, stroke=1)

        _draw_col_dividers(y, y - row_h)

        # Product name (wrapped).
        for li, wline in enumerate(wrapped):
            c.setFont("Helvetica", 9)
            c.setFillColor(TEXT_DARK)
            py = y - LINE_H - li * LINE_H + 2
            c.drawString(cols[0][0] * mm + 2 * mm, py, wline)

        # Description (italic, muted, smaller) — printed below the name.
        if desc_wrapped:
            desc_base_y = y - LINE_H - len(wrapped) * LINE_H + 2
            for li, dline in enumerate(desc_wrapped):
                c.setFont("Helvetica-Oblique", DESC_SIZE)
                c.setFillColor(LABEL_GREY)
                c.drawString(cols[0][0] * mm + 2 * mm, desc_base_y - li * LINE_H, dline)

        # Remaining column values aligned to the first line.
        text_y = y - LINE_H + 2
        for (cx, cw, align), val in zip(cols[1:], values[1:]):
            _col_text(cx, cw, align, text_y, val, size=9)

        y -= row_h

        if y < MIN_Y:
            c.showPage()
            y = H - 15 * mm
            y = _draw_table_header(y)
            row_alt = False

    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.line(TABLE_LEFT, y, TABLE_RIGHT, y)

    # ─────────────────────────────────────────────────────────────────────────
    # TOTALS SECTION
    # ─────────────────────────────────────────────────────────────────────────
    y -= 6 * mm

    product_discount = max(0.0, discount_total - invoice_discount)

    n_tot_rows = 2
    n_tot_rows += 2 if same_state else 1
    if show_discount and product_discount > 0:
        n_tot_rows += 1
    if invoice_discount > 0:
        n_tot_rows += 1
    n_tot_rows += 1

    tot_row_h    = 7 * mm
    totals_box_x = 105 * mm
    totals_box_w = W - totals_box_x - 10 * mm
    totals_box_h = n_tot_rows * tot_row_h + 8 * mm

    if y - totals_box_h < MIN_Y:
        c.showPage()
        y = H - 15 * mm

    _filled_rect(totals_box_x, y - totals_box_h, totals_box_w, totals_box_h,
                 TOTALS_BG, stroke=BORDER_LIGHT, lw=0.5)

    LABEL_X = totals_box_x + 3 * mm
    VALUE_X = totals_box_x + totals_box_w - 3 * mm
    ty      = y - 4 * mm

    def _tot_line(label, value, bold=False, highlight=False):
        nonlocal ty
        if highlight:
            _filled_rect(totals_box_x, ty - 5 * mm, totals_box_w, 8 * mm, DARK_BG)
            c.setFillColor(colors.white)
        else:
            c.setFillColor(TEXT_DARK)
        fnt = "Helvetica-Bold" if (bold or highlight) else "Helvetica"
        sz  = 11 if highlight else 9
        c.setFont(fnt, sz)
        c.drawString(LABEL_X, ty, label)
        c.drawRightString(VALUE_X, ty, value)
        ty -= tot_row_h

    _tot_line("Subtotal (Before Tax) :", f"₹ {sub_total:,.2f}")

    if same_state:
        _tot_line(f"CGST @ {last_gst_pct/2:.1f}% :", f"₹ {cgst_total:,.2f}")
        _tot_line(f"SGST @ {last_gst_pct/2:.1f}% :", f"₹ {sgst_total:,.2f}")
    else:
        _tot_line("IGST Total :", f"₹ {igst_total:,.2f}")

    if show_discount and product_discount > 0:
        _tot_line("Product Discount :", f"(-) ₹ {product_discount:,.2f}")
    if invoice_discount > 0:
        _tot_line("Invoice Discount :", f"(-) ₹ {invoice_discount:,.2f}")

    _tot_line("Round Off :", "(-) 0.00")
    _tot_line("GRAND TOTAL :", f"₹ {grand_total:,.2f}", bold=True, highlight=True)

    if header_info.get("amount_paid"):
        paid    = float(header_info["amount_paid"])
        balance = grand_total - paid
        _tot_line("Amount Paid :", f"(-) ₹ {paid:,.2f}")
        _filled_rect(totals_box_x, ty - 5 * mm, totals_box_w, 8 * mm, RED_BOX)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(LABEL_X, ty, "BALANCE DUE :")
        c.drawRightString(VALUE_X, ty, f"₹ {balance:,.2f}")
        ty -= tot_row_h

    y = min(y - totals_box_h, ty) - 8 * mm

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(TEXT_DARK)
    c.drawString(10 * mm, y, "Amount in Words :")
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(LABEL_GREY)
    c.drawString(46 * mm, y, header_info.get("amount_in_words", ""))
    y -= 12 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # FOOTER  —  Bank Details | Terms & Conditions | Signature
    # ─────────────────────────────────────────────────────────────────────────
    footer_h = 42 * mm

    if y - footer_h < 18 * mm:
        c.showPage()
        y = H - 20 * mm

    _filled_rect(TABLE_LEFT, y - footer_h, TABLE_W, footer_h,
                 colors.HexColor("#f9fafb"), stroke=BORDER_LIGHT, lw=0.7)

    col3_w = TABLE_W / 3
    fc1    = TABLE_LEFT
    fc2    = TABLE_LEFT + col3_w
    fc3    = TABLE_LEFT + 2 * col3_w

    _vline(fc2, y - footer_h, y, lw=0.5, color=BORDER_LIGHT)
    _vline(fc3, y - footer_h, y, lw=0.5, color=BORDER_LIGHT)

    from utils.company import COMPANY_NAME

    def _footer_section_title(x, cy, text):
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 3 * mm, cy, text)

    def _footer_kv(x, cy, label, value):
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(LABEL_GREY)
        c.drawString(x + 3 * mm, cy, label)
        c.setFont("Helvetica", 8)
        c.drawString(x + 3 * mm + 22 * mm, cy, str(value))
        return cy - 5 * mm

    fy = y - 5 * mm

    _footer_section_title(fc1, fy, "BANK DETAILS")
    fy -= 6 * mm

    if _show_bank:
        bank_fields = [
            ("Bank :",    _bank_name),
            ("Branch :",  _bank_branch),
            ("A/C No. :", _bank_ac_no),
            ("IFSC :",    _bank_ifsc),
        ]
        by = fy
        for label, val in bank_fields:
            if val:
                by = _footer_kv(fc1, by, label, val)
    else:
        c.setFont("Helvetica", 8)
        c.setFillColor(LABEL_GREY)
        c.drawString(fc1 + 3 * mm, fy, "Not configured")

    ty2 = y - 5 * mm
    _footer_section_title(fc2, ty2, "TERMS & CONDITIONS")
    ty2 -= 6 * mm

    if _show_terms and _terms_text.strip():
        terms = [line.strip() for line in _terms_text.splitlines() if line.strip()]
    else:
        terms = [
            "1. Payment due within 15 days.",
            "2. Late payment: 18% p.a. interest.",
            "3. Goods once sold not returnable.",
            "4. Subject to local jurisdiction.",
            "5. E. & O.E.",
            "6. TDS cert. within 7 days.",
        ]

    c.setFont("Helvetica", 7.5)
    c.setFillColor(LABEL_GREY)
    for line in terms:
        c.drawString(fc2 + 3 * mm, ty2, str(line))
        ty2 -= 5 * mm

    sy = y - 5 * mm
    _footer_section_title(fc3, sy, f"FOR {COMPANY_NAME()}")
    sig_line_y = y - footer_h + 12 * mm
    c.setStrokeColor(LABEL_GREY)
    c.setLineWidth(0.5)
    sig_start = fc3 + 6 * mm
    sig_end   = TABLE_RIGHT - 4 * mm
    c.line(sig_start, sig_line_y, sig_end, sig_line_y)
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(LABEL_GREY)
    c.drawCentredString((sig_start + sig_end) / 2, sig_line_y - 4 * mm,
                        "Authorised Signatory")
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawCentredString((sig_start + sig_end) / 2, sig_line_y - 8.5 * mm,
                        "(Stamp & Signature)")

    y -= footer_h + 8 * mm

    # ─────────────────────────────────────────────────────────────────────────
    # QR CODE + DECLARATION
    # ─────────────────────────────────────────────────────────────────────────
    if _show_qr and _qr_path and os.path.exists(_qr_path):
        try:
            qr_size = 30 * mm
            qr_x    = 12 * mm
            qr_y    = y - qr_size - 5 * mm

            _filled_rect(qr_x, qr_y + qr_size + 2 * mm, 40 * mm, 7 * mm, DARK_BG)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(qr_x + 2 * mm, qr_y + qr_size + 4 * mm, "SCAN & PAY via UPI")

            c.drawImage(_qr_path, qr_x, qr_y,
                        width=qr_size, height=qr_size,
                        preserveAspectRatio=True, mask='auto')

            c.setFont("Helvetica", 7)
            c.setFillColor(LABEL_GREY)
            c.drawString(qr_x, qr_y - 5 * mm, f"UPI ID: {_upi_id}")

            dec_x = qr_x + qr_size + 8 * mm
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(TEXT_DARK)
            c.drawString(dec_x, qr_y + qr_size - 2 * mm, "DECLARATION")
            c.setFont("Helvetica", 7.5)
            c.setFillColor(LABEL_GREY)
            declaration = (
                "We declare that this invoice shows the actual price of the goods/services "
                "described and that all particulars are true and correct."
            )
            dec_y = qr_y + qr_size - 8 * mm
            for line in simpleSplit(declaration, "Helvetica", 7.5, 110 * mm):
                c.drawString(dec_x, dec_y, line)
                dec_y -= 5 * mm

        except Exception as e:
            print("QR Error:", e)

    # ─────────────────────────────────────────────────────────────────────────
    # DARK FOOTER BAR
    # ─────────────────────────────────────────────────────────────────────────
    _filled_rect(0, 0, W, 10 * mm, DARK_BG)
    c.setFillColor(colors.HexColor("#aaaaaa"))
    c.setFont("Helvetica", 7)

    from utils.company import COMPANY_NAME
    footer_text = f"{COMPANY_NAME()}  |  info@company.in  |  +91-000-000-0000"
    c.drawCentredString(W / 2, 3 * mm, footer_text)

    c.save()
