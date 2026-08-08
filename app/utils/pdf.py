"""PDF hujjatlar (hisob-faktura). Reportlab — qo'shimcha tizim kutubxonasi talab qilmaydi."""

from __future__ import annotations

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.fmt import fmt_short_date, money_usd, money_uzs

#: Standart PDF shriftlarida yo'q belgilarni almashtiramiz
_REPLACEMENTS = {
    "ʻ": "'",  # ʻ (o'zbekcha o'/g')
    "ʼ": "'",  # ʼ
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "№": "No",
    " ": " ",
}


def safe(text: object) -> str:
    """Matnni PDF shrifti tushunadigan ko'rinishga keltiradi."""
    value = "" if text is None else str(text)
    for src, dst in _REPLACEMENTS.items():
        value = value.replace(src, dst)
    return value.encode("latin-1", "replace").decode("latin-1")


async def build_invoice_pdf(session: AsyncSession, order) -> io.BytesIO:
    """Buyurtma bo'yicha hisob-faktura."""
    from app.services.settings_service import get_setting

    company = await get_setting(session, "company_name") or "DXL Dental Implant"
    phone = await get_setting(session, "company_phone") or ""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=safe(order.number),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleUz", parent=styles["Title"], fontSize=16, spaceAfter=4
    )
    small = ParagraphStyle("SmallUz", parent=styles["Normal"], fontSize=9)
    normal = ParagraphStyle("NormalUz", parent=styles["Normal"], fontSize=10)

    story: list = [
        Paragraph(safe(company), title_style),
        Paragraph(safe(f"Tel: {phone}") if phone else "", small),
        Spacer(1, 6 * mm),
        Paragraph(safe(f"HISOB-FAKTURA  {order.number}"), styles["Heading2"]),
        Spacer(1, 2 * mm),
    ]

    info_rows = [
        ["Sana:", safe(fmt_short_date(order.created_at))],
        ["Vrach:", safe(order.doctor_name or "-")],
        ["Telefon:", safe(order.doctor_phone or "-")],
        ["Agent:", safe(order.agent_name or "-")],
        ["Kurs (USD/UZS):", safe(f"{Decimal(order.fx_rate):,.0f}".replace(",", " "))],
        ["To'lov muddati:", safe(fmt_short_date(order.due_date))],
    ]
    info_table = Table(info_rows, colWidths=[38 * mm, 120 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#555555")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story += [info_table, Spacer(1, 5 * mm)]

    head = ["#", "Mahsulot", "Razmer", "Soni", "Narx", "Chegirma", "Summa"]
    data = [head]
    for index, item in enumerate(order.items, start=1):
        data.append(
            [
                str(index),
                safe(f"{item.sku or ''} {item.product_name or ''}".strip()),
                safe(item.size or "-"),
                str(item.qty),
                safe(money_usd(item.price_usd)),
                safe(f"{Decimal(item.discount_pct):g}%"),
                safe(money_usd(item.line_total_usd)),
            ]
        )

    table = Table(
        data,
        colWidths=[10 * mm, 62 * mm, 22 * mm, 14 * mm, 22 * mm, 18 * mm, 26 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F6FEB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story += [table, Spacer(1, 5 * mm)]

    totals = [
        ["Jami:", safe(money_usd(order.subtotal_usd))],
        [f"Chegirma ({Decimal(order.discount_pct):g}%):", safe(money_usd(order.discount_usd))],
        ["To'lash uchun (USD):", safe(money_usd(order.total_usd))],
        ["To'lash uchun (so'm):", safe(money_uzs(order.total_uzs or 0))],
    ]
    totals_table = Table(totals, colWidths=[60 * mm, 40 * mm], hAlign="RIGHT")
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("LINEABOVE", (0, 2), (-1, 2), 0.6, colors.black),
                ("FONTNAME", (0, 2), (-1, -1), "Helvetica-Bold"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story += [totals_table, Spacer(1, 8 * mm)]

    if order.comment:
        story += [Paragraph(safe(f"Izoh: {order.comment}"), small), Spacer(1, 4 * mm)]

    story += [
        Paragraph(safe("Topshirdi: ______________________"), normal),
        Spacer(1, 4 * mm),
        Paragraph(safe("Qabul qildi: ______________________"), normal),
    ]

    doc.build(story)
    buffer.seek(0)
    return buffer
