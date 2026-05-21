import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
import num2words
from utils.company import COMPANY_NAME, COMPANY_ADDRESS, COMPANY_PHONE
from utils.paths import INVOICE_DIR

os.makedirs(INVOICE_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────────
# COLOUR PALETTE  (RIFA-style: clean black & white, traditional)
# ─────────────────────────────────────────────────────────────────
_BLACK      = colors.HexColor("#000000")
_DARK_TEXT  = colors.HexColor("#1a1a1a")
_HDR_BG     = colors.HexColor("#d6d6d6")
_ROW_ALT    = colors.HexColor("#f7f7f7")
_RULE       = colors.HexColor("#000000")
_MUTED      = colors.HexColor("#555555")
_SECTION_BG = colors.HexColor("#efefef")
_TOTALS_BG  = colors.HexColor("#f0f0f0")
_WHITE      = colors.white
_ACCENT_LINE= colors.HexColor("#000000")

_SUMMARY_BG       = colors.HexColor("#1e293b")
_SUMMARY_DUE_BG   = colors.HexColor("#dc2626")
_SUMMARY_PAY_BG   = colors.HexColor("#1d4ed8")


# ─────────────────────────────────────────────────────────────────
# SETTINGS HELPERS
# ─────────────────────────────────────────────────────────────────
def _load_settings():
    defaults = {
        "business_state":   "West Bengal",
        "show_qr":          False,
        "qr_path":          "",
        "show_terms":       False,
        "terms_text":       "",
        "show_bank":        False,
        "bank_name":        "",
        "bank_account_no":  "",
        "bank_ifsc":        "",
        "bank_branch":      "",
    }
    try:
        from PySide6.QtCore import QSettings
        s = QSettings("MayurSoft", "BillingSoftware")
        return {
            "business_state":  s.value("business_state",  defaults["business_state"]),
            "show_qr":         s.value("show_qr",         defaults["show_qr"],  type=bool),
            "qr_path":         s.value("qr_path",         defaults["qr_path"]),
            "show_terms":      s.value("show_terms",       defaults["show_terms"], type=bool),
            "terms_text":      s.value("terms_text",       defaults["terms_text"]),
            "show_bank":       s.value("show_bank",        defaults["show_bank"],  type=bool),
            "bank_name":       s.value("bank_name",        defaults["bank_name"]),
            "bank_account_no": s.value("bank_account_no",  defaults["bank_account_no"]),
            "bank_ifsc":       s.value("bank_ifsc",        defaults["bank_ifsc"]),
            "bank_branch":     s.value("bank_branch",      defaults["bank_branch"]),
        }
    except Exception:
        return defaults


# ─────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────
def _wrap_pts(text, font_name, font_size, max_width_pts):
    return simpleSplit(str(text), font_name, font_size, max_width_pts)


def _rrect(c, x, y, w, h, r, fill, stroke=None, lw=0.5):
    c.saveState()
    c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(lw)
        c.roundRect(x, y, w, h, r, fill=1, stroke=1)
    else:
        c.roundRect(x, y, w, h, r, fill=1, stroke=0)
    c.restoreState()


def _parse_discount(discount, base, gst_amt):
    total_before = base + gst_amt
    if isinstance(discount, tuple):
        val, is_pct = discount
        val = float(val)
        if is_pct:
            return f"{val:.2f}%", total_before * val / 100
        else:
            return f"₹{val:.2f}", val
    s = str(discount).strip()
    if not s or s in ("0", "0.0"):
        return "", 0.0
    if "%" in s:
        val = float(s.replace("%", "").strip())
        return f"{val:.2f}%", total_before * val / 100
    val = float(s.replace("₹", "").replace("Rs.", "").strip() or 0)
    display = f"₹{val:.2f}" if val else ""
    return display, val


# ─────────────────────────────────────────────────────────────────
# AMOUNT IN WORDS
# ─────────────────────────────────────────────────────────────────
def amount_in_words(amount: float) -> str:
    rupees = int(amount)
    paise  = round((amount - rupees) * 100)
    text   = num2words.num2words(rupees, lang="en_IN").title()
    if paise:
        text += f" and {paise}/100"
    text += " Rupees Only"
    return text


# ─────────────────────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────────────────────
def generate_invoice_pdf(
    filename,
    title,
    header_info,
    table_headers,
    table_rows,
    grand_total,
    invoice_discount=0
):
    """
    table_rows row format (8 items — preferred):
        [name, description, hsn, qty, rate, gst, discount, amount]

    Backward-compatible formats still accepted:
        [name, hsn, qty, rate, gst, discount, amount]  (7 items — no description)
        [name, hsn, qty, rate, gst, amount]            (6 items — no description, no discount)

    description is printed in smaller italic text below the product name
    in the same cell.
    """
    cfg = _load_settings()

    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    header_info    = dict(header_info or {})
    BUSINESS_STATE = cfg["business_state"]

    customer_state = header_info.get("customer_state", "")
    same_state = (
        customer_state.strip().lower() == BUSINESS_STATE.strip().lower()
        if customer_state and BUSINESS_STATE else False
    )

    _total_due    = header_info.get("total_due",   None)
    _net_payable  = header_info.get("net_payable", None)
    _show_summary = _total_due is not None

    # Detect column visibility — check position 2 (hsn) and 6 (discount) for
    # 8-item rows; fall back to positions 1 and 5 for legacy 6/7-item rows.
    def _hsn_val(r):
        return r[2] if len(r) >= 8 else (r[1] if len(r) > 1 else "")

    def _disc_val(r):
        return r[6] if len(r) >= 8 else (r[5] if len(r) > 5 else 0)

    def _is_nonzero(val):
        if not val:
            return False
        try:
            return float(str(val).replace("₹", "").replace("%", "").strip()) != 0
        except Exception:
            return bool(val)

    show_hsn      = any(_hsn_val(r) for r in table_rows)
    show_discount = any(_is_nonzero(_disc_val(r)) for r in table_rows)

    if show_discount and show_hsn:
        cols = [(15,52,"L"),(68,18,"C"),(87,14,"R"),(102,18,"R"),
                (121,18,"R"),(140,13,"C"),(154,18,"R"),(173,22,"R")]
        hdr_labels = ["Product","HSN","Qty","Rate","Net Rate","GST%","Discount","Amount"]
    elif show_discount:
        cols = [(15,68,"L"),(84,14,"R"),(99,18,"R"),(118,18,"R"),
                (137,13,"C"),(151,18,"R"),(170,25,"R")]
        hdr_labels = ["Product","Qty","Rate","Net Rate","GST%","Discount","Amount"]
    elif show_hsn:
        cols = [(15,58,"L"),(74,18,"C"),(93,14,"R"),(108,18,"R"),
                (127,18,"R"),(146,13,"C"),(160,35,"R")]
        hdr_labels = ["Product","HSN","Qty","Rate","Net Rate","GST%","Amount"]
    else:
        cols = [(15,78,"L"),(94,14,"R"),(109,18,"R"),(128,18,"R"),
                (147,13,"C"),(161,34,"R")]
        hdr_labels = ["Product","Qty","Rate","Net Rate","GST%","Amount"]

    product_col_w_pts = cols[0][1] * mm
    TABLE_LEFT  = 15 * mm
    TABLE_RIGHT = width - 15 * mm
    TABLE_W     = TABLE_RIGHT - TABLE_LEFT

    # ─────────────────────────────────────────────────────────────
    # DRAW HELPERS
    # ─────────────────────────────────────────────────────────────
    def _bordered_rect(x, y, w, h, fill=_WHITE, lw=0.6):
        c.saveState()
        c.setFillColor(fill)
        c.setStrokeColor(_BLACK)
        c.setLineWidth(lw)
        c.rect(x, y, w, h, fill=1, stroke=1)
        c.restoreState()

    def _col_text(cx, cw, align, py, text, font="Helvetica", size=9,
                  color=_DARK_TEXT):
        c.saveState()
        c.setFont(font, size)
        c.setFillColor(color)
        pad = 2 * mm
        if align == "R":
            c.drawRightString((cx + cw) * mm - pad, py, str(text))
        elif align == "C":
            c.drawCentredString((cx + cw / 2) * mm, py, str(text))
        else:
            c.drawString(cx * mm + pad, py, str(text))
        c.restoreState()

    def _hline(y, x0=None, x1=None, lw=0.5, color=_BLACK):
        c.saveState()
        c.setStrokeColor(color)
        c.setLineWidth(lw)
        c.line(x0 or TABLE_LEFT, y, x1 or TABLE_RIGHT, y)
        c.restoreState()

    def _vline(x, y0, y1, lw=0.5):
        c.saveState()
        c.setStrokeColor(_BLACK)
        c.setLineWidth(lw)
        c.line(x, y0, x, y1)
        c.restoreState()

    # ─────────────────────────────────────────────────────────────
    # CREDIT SUMMARY BOX
    # ─────────────────────────────────────────────────────────────
    def draw_credit_summary(y_top):
        box_h    = 18 * mm
        show_net = _net_payable is not None
        if show_net:
            mid_x = TABLE_LEFT + TABLE_W / 2
            c.setFillColor(_SUMMARY_PAY_BG)
            c.setStrokeColor(_BLACK)
            c.setLineWidth(0.8)
            c.rect(TABLE_LEFT, y_top - box_h, TABLE_W / 2, box_h, fill=1, stroke=1)
            c.setFillColor(_SUMMARY_DUE_BG)
            c.rect(mid_x, y_top - box_h, TABLE_W / 2, box_h, fill=1, stroke=1)
            c.setFillColor(_WHITE)
            c.setFont("Helvetica", 7.5)
            c.drawString(TABLE_LEFT + 4 * mm, y_top - 4.5 * mm, "NET PAYABLE (per visit)")
            c.setFont("Helvetica-Bold", 13)
            c.drawString(TABLE_LEFT + 4 * mm, y_top - 11 * mm, f"₹ {_net_payable:,.2f}")
            c.setFont("Helvetica", 7.5)
            c.drawString(mid_x + 4 * mm, y_top - 4.5 * mm, "TOTAL DUE (outstanding)")
            c.setFont("Helvetica-Bold", 13)
            c.drawString(mid_x + 4 * mm, y_top - 11 * mm, f"₹ {_total_due:,.2f}")
        else:
            c.setFillColor(_SUMMARY_DUE_BG)
            c.setStrokeColor(_BLACK)
            c.setLineWidth(0.8)
            c.rect(TABLE_LEFT, y_top - box_h, TABLE_W, box_h, fill=1, stroke=1)
            c.setFillColor(_WHITE)
            c.setFont("Helvetica", 7.5)
            c.drawCentredString(width / 2, y_top - 4.5 * mm, "TOTAL DUE (outstanding balance)")
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(width / 2, y_top - 12 * mm, f"₹ {_total_due:,.2f}")
        return y_top - box_h - 2 * mm

    # ─────────────────────────────────────────────────────────────
    # PAGE HEADER
    # ─────────────────────────────────────────────────────────────
    def draw_page_header(y_top):
        header_h = 36 * mm
        _bordered_rect(TABLE_LEFT, y_top - header_h, TABLE_W, header_h, fill=_WHITE, lw=1.0)
        gstin = header_info.get("company_gstin", "")
        if gstin:
            c.setFont("Helvetica", 7.5)
            c.setFillColor(_MUTED)
            c.drawString(TABLE_LEFT + 3 * mm, y_top - 4.5 * mm, f"GSTIN : {gstin}")
        c.setFont("Helvetica-Bold", 17)
        c.setFillColor(_DARK_TEXT)
        c.drawCentredString(width / 2, y_top - 10 * mm, COMPANY_NAME())
        addr_y = y_top - 15.5 * mm
        c.setFont("Helvetica", 8)
        c.setFillColor(_MUTED)
        if COMPANY_ADDRESS:
            c.drawCentredString(width / 2, addr_y, COMPANY_ADDRESS())
            addr_y -= 4.5 * mm
        if COMPANY_PHONE:
            c.drawCentredString(width / 2, addr_y, f"Tel. : {COMPANY_PHONE()}")
        rule_y = y_top - 23 * mm
        _hline(rule_y, TABLE_LEFT, TABLE_RIGHT, lw=0.8)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(_DARK_TEXT)
        c.drawCentredString(width / 2, rule_y - 6 * mm, title.upper())
        return y_top - header_h - 1 * mm

    # ─────────────────────────────────────────────────────────────
    # META / BILLING INFO
    # ─────────────────────────────────────────────────────────────
    def draw_meta(y):
        mid_x = TABLE_LEFT + TABLE_W / 2
        col_w = TABLE_W / 2

        meta_fields_left = [
            ("Invoice No.", header_info.get("invoice_no", "")),
            ("Vehicle No.", header_info.get("vehicle_no", "")),
            ("Place of Supply", header_info.get("place_of_supply", "")),
            ("Reverse Charge", header_info.get("reverse_charge", "N")),
        ]
        meta_fields_right = [
            ("Dated", header_info.get("date_time", "")),
            ("Station", header_info.get("station", "")),
            ("E-Way Bill No.", header_info.get("eway_bill", "")),
            ("Time", header_info.get("time", "")),
        ]

        n_meta     = max(len(meta_fields_left), len(meta_fields_right))
        meta_row_h = 5.5 * mm
        meta_h     = n_meta * meta_row_h + 2 * mm

        _bordered_rect(TABLE_LEFT, y - meta_h, TABLE_W, meta_h, lw=0.7)
        _vline(mid_x, y - meta_h, y)

        for i, (lbl, val) in enumerate(meta_fields_left):
            ty = y - (i + 0.8) * meta_row_h
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(_DARK_TEXT)
            c.drawString(TABLE_LEFT + 3 * mm, ty, f"{lbl} :")
            c.setFont("Helvetica", 8)
            c.setFillColor(_MUTED)
            c.drawString(TABLE_LEFT + 3 * mm + 28 * mm, ty, str(val))

        for i, (lbl, val) in enumerate(meta_fields_right):
            ty = y - (i + 0.8) * meta_row_h
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(_DARK_TEXT)
            c.drawString(mid_x + 3 * mm, ty, f"{lbl} :")
            c.setFont("Helvetica", 8)
            c.setFillColor(_MUTED)
            c.drawString(mid_x + 3 * mm + 28 * mm, ty, str(val))

        y -= meta_h

        bill_lines = []
        if header_info.get("customer_name"):
            bill_lines.append(("bold",   header_info["customer_name"]))
        if header_info.get("customer_address"):
            bill_lines.append(("normal", header_info["customer_address"]))
        if header_info.get("customer_phone"):
            bill_lines.append(("normal", f"Ph: {header_info['customer_phone']}"))
        if header_info.get("customer_gstin"):
            bill_lines.append(("normal", f"GSTIN / UIN : {header_info['customer_gstin']}"))

        bill_h = max(28 * mm, (len(bill_lines) + 2) * 5.5 * mm)

        _bordered_rect(TABLE_LEFT, y - bill_h, TABLE_W, bill_h, lw=0.7)
        _vline(mid_x, y - bill_h, y)

        label_row_h = 6 * mm
        c.setFillColor(_SECTION_BG)
        c.setStrokeColor(_BLACK)
        c.setLineWidth(0.5)
        c.rect(TABLE_LEFT, y - label_row_h, col_w, label_row_h, fill=1, stroke=0)
        c.rect(mid_x,      y - label_row_h, col_w, label_row_h, fill=1, stroke=0)
        _hline(y - label_row_h, lw=0.5)

        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(_DARK_TEXT)
        c.drawString(TABLE_LEFT + 3 * mm, y - 4 * mm, "Billed to :")
        c.drawString(mid_x      + 3 * mm, y - 4 * mm, "Shipped to :")

        cy = y - label_row_h - 5 * mm
        for style, text in bill_lines:
            font = "Helvetica-Bold" if style == "bold" else "Helvetica"
            size = 9 if style == "bold" else 8
            c.setFont(font, size)
            c.setFillColor(_DARK_TEXT if style == "bold" else _MUTED)
            c.drawString(TABLE_LEFT + 3 * mm, cy, text)
            c.drawString(mid_x      + 3 * mm, cy, text)
            cy -= 5 * mm

        return y - bill_h - 1 * mm

    # ─────────────────────────────────────────────────────────────
    # TABLE HEADER
    # ─────────────────────────────────────────────────────────────
    def draw_table_header(y):
        row_h = 8 * mm
        c.setFillColor(_HDR_BG)
        c.setStrokeColor(_BLACK)
        c.setLineWidth(0.7)
        c.rect(TABLE_LEFT, y - row_h, TABLE_W, row_h, fill=1, stroke=1)
        for i, (cx, cw, _) in enumerate(cols[:-1]):
            _vline((cx + cw) * mm, y - row_h, y, lw=0.5)
        for (cx, cw, align), label in zip(cols, hdr_labels):
            _col_text(cx, cw, align, y - 5.5 * mm, label,
                      font="Helvetica-Bold", size=8.5, color=_DARK_TEXT)
        return y - row_h

    # ─────────────────────────────────────────────────────────────
    # FIRST PAGE
    # ─────────────────────────────────────────────────────────────
    y = height - 5 * mm
    if _show_summary:
        y = draw_credit_summary(y)
    y = draw_page_header(y)
    y = draw_meta(y)
    y = draw_table_header(y)

    # ─────────────────────────────────────────────────────────────
    # TABLE ROWS
    # ─────────────────────────────────────────────────────────────
    sub_total      = 0.0
    gst_total      = 0.0
    discount_total = 0.0
    cgst_total     = 0.0
    sgst_total     = 0.0
    igst_total     = 0.0

    LINE_H = 10   # pts per text line
    DESC_SIZE = 7.5
    MIN_Y  = 52 * mm

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

        base    = qty * rate
        gst_amt = base * gst_pct / 100
        net_rate= rate + (rate * gst_pct / 100)

        sub_total += base
        if same_state:
            cgst_total += gst_amt / 2
            sgst_total += gst_amt / 2
        else:
            igst_total += gst_amt
        gst_total += gst_amt

        discount_display, discount_amt = _parse_discount(discount, base, gst_amt)
        discount_total += discount_amt

        qty_str = str(int(qty)) if qty == int(qty) else str(qty)
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
        wrapped      = _wrap_pts(values[0], "Helvetica", 9, product_col_w_pts - 4 * mm)
        desc_wrapped = (
            _wrap_pts(str(description), "Helvetica-Oblique", DESC_SIZE, product_col_w_pts - 4 * mm)
            if description else []
        )
        n_lines = max(1, len(wrapped)) + len(desc_wrapped)
        row_h   = n_lines * LINE_H + 6

        if y - row_h < MIN_Y:
            c.showPage()
            y = height - 15 * mm
            y = draw_table_header(y)

        row_fill = _ROW_ALT if row_idx % 2 == 0 else _WHITE
        c.setFillColor(row_fill)
        c.setStrokeColor(_BLACK)
        c.setLineWidth(0.4)
        c.rect(TABLE_LEFT, y - row_h, TABLE_W, row_h, fill=1, stroke=0)

        for cx, cw, _ in cols[:-1]:
            _vline((cx + cw) * mm, y - row_h, y, lw=0.4)
        _vline(TABLE_LEFT,  y - row_h, y, lw=0.7)
        _vline(TABLE_RIGHT, y - row_h, y, lw=0.7)

        text_y = y - LINE_H + 1

        # Product name lines.
        c.setFont("Helvetica", 9)
        c.setFillColor(_DARK_TEXT)
        for li, wline in enumerate(wrapped):
            c.drawString(cols[0][0] * mm + 2 * mm, text_y - li * LINE_H, wline)

        # Description lines (italic, muted, smaller).
        if desc_wrapped:
            desc_y = text_y - len(wrapped) * LINE_H
            for li, dline in enumerate(desc_wrapped):
                c.setFont("Helvetica-Oblique", DESC_SIZE)
                c.setFillColor(_MUTED)
                c.drawString(cols[0][0] * mm + 2 * mm, desc_y - li * LINE_H, dline)

        # Remaining column values on the first text line.
        for (cx, cw, align), val in zip(cols[1:], values[1:]):
            _col_text(cx, cw, align, text_y, val, size=9, color=_DARK_TEXT)

        _hline(y - row_h, lw=0.4)
        y -= row_h

        if y < MIN_Y:
            c.showPage()
            y = height - 15 * mm

    _hline(y, lw=0.7)

    # ─────────────────────────────────────────────────────────────
    # TAX SUMMARY TABLE
    # ─────────────────────────────────────────────────────────────
    y -= 3 * mm
    tax_row_h = 6.5 * mm
    tax_cols  = [
        (TABLE_LEFT,                   TABLE_W * 0.25),
        (TABLE_LEFT + TABLE_W * 0.25,  TABLE_W * 0.25),
        (TABLE_LEFT + TABLE_W * 0.50,  TABLE_W * 0.25),
        (TABLE_LEFT + TABLE_W * 0.75,  TABLE_W * 0.25),
    ]
    tax_hdr = ["Tax Rate", "Taxable Amt.", "Tax Amt.", "Total Tax"]

    if same_state:
        tax_rows_data = [(
            f"{18:.0f}%",
            f"₹ {sub_total:.2f}",
            f"CGST ₹{cgst_total:.2f}  SGST ₹{sgst_total:.2f}",
            f"₹ {gst_total:.2f}",
        )]
    else:
        tax_rows_data = [(
            f"{18:.0f}%",
            f"₹ {sub_total:.2f}",
            f"IGST ₹ {igst_total:.2f}",
            f"₹ {gst_total:.2f}",
        )]

    total_tax_rows = 1 + len(tax_rows_data)
    tax_block_h    = total_tax_rows * tax_row_h

    if y - tax_block_h < MIN_Y:
        c.showPage()
        y = height - 15 * mm

    c.setFillColor(_HDR_BG)
    c.setStrokeColor(_BLACK)
    c.setLineWidth(0.6)
    c.rect(TABLE_LEFT, y - tax_row_h, TABLE_W, tax_row_h, fill=1, stroke=1)
    for i, (tx, tw) in enumerate(tax_cols):
        if i > 0:
            _vline(tx, y - tax_row_h, y, lw=0.4)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(_DARK_TEXT)
        c.drawCentredString(tx + tw / 2, y - 4.5 * mm, tax_hdr[i])

    y -= tax_row_h
    for trow in tax_rows_data:
        c.setFillColor(_WHITE)
        c.setStrokeColor(_BLACK)
        c.setLineWidth(0.5)
        c.rect(TABLE_LEFT, y - tax_row_h, TABLE_W, tax_row_h, fill=1, stroke=1)
        for i, (tx, tw) in enumerate(tax_cols):
            if i > 0:
                _vline(tx, y - tax_row_h, y, lw=0.4)
            c.setFont("Helvetica", 8)
            c.setFillColor(_DARK_TEXT)
            c.drawCentredString(tx + tw / 2, y - 4.5 * mm, trow[i])
        y -= tax_row_h

    y -= 3 * mm

    # ─────────────────────────────────────────────────────────────
    # TOTALS SECTION
    # ─────────────────────────────────────────────────────────────
    product_discount = max(0.0, discount_total - invoice_discount)

    n_tot = 2
    n_tot += 2 if same_state else 1
    if show_discount and product_discount > 0:
        n_tot += 1
    if invoice_discount > 0:
        n_tot += 1

    tot_row_h = 7 * mm
    tot_h     = n_tot * tot_row_h + 4 * mm

    if y - tot_h < MIN_Y:
        c.showPage()
        y = height - 15 * mm

    y -= 2 * mm

    block_x = TABLE_LEFT + TABLE_W * 0.52
    block_w = TABLE_RIGHT - block_x

    c.setFillColor(_TOTALS_BG)
    c.setStrokeColor(_BLACK)
    c.setLineWidth(0.7)
    c.rect(block_x, y - tot_h, block_w, tot_h, fill=1, stroke=1)

    ty      = y - 6 * mm
    LABEL_X = block_x + 4 * mm
    VALUE_X = block_x + block_w - 4 * mm

    def _tot_line(label, value, bold=False):
        nonlocal ty
        fnt = "Helvetica-Bold" if bold else "Helvetica"
        sz  = 9 if bold else 8.5
        c.setFont(fnt, sz)
        c.setFillColor(_DARK_TEXT)
        c.drawString(LABEL_X, ty, label)
        c.drawRightString(VALUE_X, ty, value)
        c.setStrokeColor(colors.HexColor("#cccccc"))
        c.setLineWidth(0.3)
        c.line(LABEL_X, ty - 2.5 * mm, VALUE_X, ty - 2.5 * mm)
        ty -= tot_row_h

    _tot_line("Sub Total", f"₹ {sub_total:.2f}")
    if same_state:
        _tot_line("CGST Total", f"₹ {cgst_total:.2f}")
        _tot_line("SGST Total", f"₹ {sgst_total:.2f}")
    else:
        _tot_line("IGST Total", f"₹ {igst_total:.2f}")
    if show_discount and product_discount > 0:
        _tot_line("Product Discount", f"- ₹ {product_discount:.2f}")
    if invoice_discount > 0:
        _tot_line("Invoice Discount", f"- ₹ {invoice_discount:.2f}")

    c.setStrokeColor(_BLACK)
    c.setLineWidth(0.8)
    c.line(LABEL_X, ty + 4.5 * mm, VALUE_X, ty + 4.5 * mm)
    ty -= 1 * mm
    _tot_line("Grand Total", f"₹ {grand_total:.2f}", bold=True)

    # ─────────────────────────────────────────────────────────────
    # AMOUNT IN WORDS
    # ─────────────────────────────────────────────────────────────
    words_text    = header_info.get("amount_in_words") or amount_in_words(grand_total)
    words_region_w = (block_x - TABLE_LEFT) - 6 * mm
    words_lines   = _wrap_pts(words_text, "Helvetica-Oblique", 8, words_region_w) or [words_text]

    words_y      = y - 2 * mm
    label_offset = 16 * mm

    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(_DARK_TEXT)
    c.drawString(TABLE_LEFT, words_y, "Rupees :")

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(_MUTED)
    line_gap = 4.5 * mm
    for i, wline in enumerate(words_lines):
        c.drawString(TABLE_LEFT + label_offset, words_y - i * line_gap, wline)

    y = y - tot_h - 6 * mm

    # ─────────────────────────────────────────────────────────────
    # FOOTER: BANK DETAILS | TERMS & CONDITIONS | SIGNATURE
    # ─────────────────────────────────────────────────────────────
    show_bank  = cfg["show_bank"]
    show_terms = cfg["show_terms"]

    content_cols = []
    if show_bank:
        content_cols.append("bank")
    if show_terms:
        content_cols.append("terms")
    content_cols.append("signature")

    n_footer_cols = len(content_cols)
    col_w_footer  = TABLE_W / n_footer_cols

    terms_lines = []
    if show_terms and cfg["terms_text"].strip():
        raw_lines = cfg["terms_text"].strip().splitlines()
        for raw in raw_lines:
            wrapped_t = _wrap_pts(raw, "Helvetica", 7, col_w_footer - 6 * mm)
            terms_lines.extend(wrapped_t or [raw])

    bank_fields = []
    if show_bank:
        for label, key in [
            ("Bank",    "bank_name"),
            ("A/C No.", "bank_account_no"),
            ("IFSC",    "bank_ifsc"),
            ("Branch",  "bank_branch"),
        ]:
            val = cfg.get(key, "").strip()
            if val:
                bank_fields.append((label, val))

    min_footer_h = 34 * mm
    needed_h     = max(
        min_footer_h,
        (len(terms_lines) + 3) * 4.5 * mm,
        (len(bank_fields) + 3) * 5.0 * mm,
    )
    footer_info_h = needed_h

    if y - footer_info_h < 18 * mm:
        c.showPage()
        y = height - 15 * mm

    col_starts = [
        TABLE_LEFT + i * col_w_footer
        for i in range(n_footer_cols)
    ]

    c.setFillColor(_WHITE)
    c.setStrokeColor(_BLACK)
    c.setLineWidth(0.7)
    c.rect(TABLE_LEFT, y - footer_info_h, TABLE_W, footer_info_h, fill=1, stroke=1)

    for cx in col_starts[1:]:
        _vline(cx, y - footer_info_h, y, lw=0.5)

    for col_idx, col_type in enumerate(content_cols):
        cx    = col_starts[col_idx]
        cx_r  = cx + col_w_footer
        inner = cx + 3 * mm
        ry    = y - 5 * mm

        if col_type == "bank":
            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(_DARK_TEXT)
            c.drawString(inner, ry, "Bank Details")
            _hline(ry - 1.5 * mm, cx, cx_r, lw=0.4)
            ry -= 6 * mm
            if bank_fields:
                for lbl, val in bank_fields:
                    c.setFont("Helvetica-Bold", 7.5)
                    c.setFillColor(_DARK_TEXT)
                    c.drawString(inner, ry, f"{lbl} :")
                    c.setFont("Helvetica", 7.5)
                    c.setFillColor(_MUTED)
                    c.drawString(inner + 12 * mm, ry, val)
                    ry -= 5 * mm
            else:
                c.setFont("Helvetica-Oblique", 7.5)
                c.setFillColor(_MUTED)
                c.drawString(inner, ry, "Not configured")

        elif col_type == "terms":
            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(_DARK_TEXT)
            c.drawString(inner, ry, "Terms & Conditions")
            _hline(ry - 1.5 * mm, cx, cx_r, lw=0.4)
            ry -= 6 * mm
            if terms_lines:
                for tline in terms_lines:
                    c.setFont("Helvetica", 7)
                    c.setFillColor(_MUTED)
                    c.drawString(inner, ry, tline)
                    ry -= 4.5 * mm
                    if ry < y - footer_info_h + 4 * mm:
                        break
            else:
                c.setFont("Helvetica-Oblique", 7.5)
                c.setFillColor(_MUTED)
                c.drawString(inner, ry, "Not configured")

        elif col_type == "signature":
            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(_DARK_TEXT)
            c.drawString(inner, ry, f"For {COMPANY_NAME()}")

            sig_line_y = y - footer_info_h + 10 * mm
            sig_start  = cx + 6 * mm
            sig_end    = TABLE_RIGHT - 4 * mm if col_idx == n_footer_cols - 1 else cx_r - 4 * mm
            c.setStrokeColor(_BLACK)
            c.setLineWidth(0.5)
            c.line(sig_start, sig_line_y, sig_end, sig_line_y)
            c.setFont("Helvetica", 7.5)
            c.setFillColor(_MUTED)
            c.drawCentredString(
                (sig_start + sig_end) / 2,
                sig_line_y - 4 * mm,
                "Authorised Signatory",
            )

    y -= footer_info_h

    # ─────────────────────────────────────────────────────────────
    # FOOTER STRIP
    # ─────────────────────────────────────────────────────────────
    footer_y = 8 * mm
    c.setFillColor(_SECTION_BG)
    c.setStrokeColor(_BLACK)
    c.setLineWidth(0.5)
    c.rect(TABLE_LEFT, footer_y, TABLE_W, 8 * mm, fill=1, stroke=1)
    c.setFillColor(_MUTED)
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, footer_y + 2.5 * mm,
                        "Thank you for your Business  |  E. & O.E.")

    # ─────────────────────────────────────────────────────────────
    # QR CODE
    # ─────────────────────────────────────────────────────────────
    try:
        if cfg["show_qr"] and cfg["qr_path"] and os.path.exists(cfg["qr_path"]):
            qr_size = 30 * mm
            qr_x    = 15 * mm
            qr_y    = 12 * mm
            c.drawImage(
                cfg["qr_path"], qr_x, qr_y,
                width=qr_size, height=qr_size,
                preserveAspectRatio=True, mask="auto",
            )
            c.setFont("Helvetica", 8)
            c.setFillColor(colors.HexColor("#444444"))
            c.drawString(qr_x, qr_y - 5 * mm, "Scan to Pay")
    except Exception as e:
        print("QR Error:", e)

    c.save()
