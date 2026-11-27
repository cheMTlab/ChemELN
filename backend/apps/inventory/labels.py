"""Printable container labels with a QR code (PDF)."""

from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# name -> (label width, label height, columns, rows, page margins left/top, gaps x/y)
LAYOUTS = {
    # One label per page: thermal label printers (Brother QL 62 mm tape, Zebra, Dymo).
    "roll-62x29": {"size": (62 * mm, 29 * mm), "grid": None},
    # A4 sheet, 3 × 7 labels of 63.5 × 38.1 mm (Avery L7160 and compatibles).
    "a4-3x7": {
        "size": (63.5 * mm, 38.1 * mm),
        "grid": {
            "cols": 3,
            "rows": 7,
            "left": 7.2 * mm,
            "top": 15.1 * mm,
            "gap_x": 2.5 * mm,
            "gap_y": 0,
        },
    },
}


def _fit(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _draw_label(c: canvas.Canvas, container, x: float, y: float, w: float, h: float) -> None:
    pad = 2 * mm
    qr_size = h - 2 * pad
    widget = QrCodeWidget(container.barcode, barLevel="M")
    x1, y1, x2, y2 = widget.getBounds()
    drawing = Drawing(
        qr_size, qr_size, transform=[qr_size / (x2 - x1), 0, 0, qr_size / (y2 - y1), 0, 0]
    )
    drawing.add(widget)
    renderPDF.draw(drawing, c, x + pad, y + pad)

    tx = x + qr_size + 2 * pad
    max_chars = int((w - qr_size - 3 * pad) / (1.9 * mm))
    compound = container.compound
    line_y = y + h - pad - 3 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(tx, line_y, _fit(compound.name, max_chars))
    c.setFont("Helvetica", 6.5)
    lines = [
        f"CAS {compound.cas}" if compound.cas else compound.formula,
        f"{container.amount.normalize():f} {container.unit}"
        + (f" · {container.purity.normalize():f} %" if container.purity else ""),
        container.group.name,
        " ".join(compound.ghs_pictograms)
        + (f" {compound.signal_word.upper()}" if compound.signal_word else ""),
    ]
    for line in lines:
        if line:
            line_y -= 3.2 * mm
            c.drawString(tx, line_y, _fit(line, max_chars + 4))
    c.setFont("Courier-Bold", 7)
    c.drawString(tx, y + pad, container.barcode)


def render_labels(containers, layout: str = "roll-62x29") -> bytes:
    spec = LAYOUTS[layout]
    w, h = spec["size"]
    buf = BytesIO()
    grid = spec["grid"]
    c = canvas.Canvas(buf, pagesize=(w, h) if grid is None else A4)
    c.setTitle("CheMTlab labels")
    if grid is None:
        for container in containers:
            _draw_label(c, container, 0, 0, w, h)
            c.showPage()
    else:
        per_page = grid["cols"] * grid["rows"]
        page_h = A4[1]
        for i, container in enumerate(containers):
            slot = i % per_page
            if i and slot == 0:
                c.showPage()
            col, row = slot % grid["cols"], slot // grid["cols"]
            x = grid["left"] + col * (w + grid["gap_x"])
            y = page_h - grid["top"] - (row + 1) * h - row * grid["gap_y"]
            _draw_label(c, container, x, y, w, h)
        c.showPage()
    c.save()
    return buf.getvalue()
