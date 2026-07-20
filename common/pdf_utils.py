"""
PDF Export utilities for reports using reportlab.
Supports Arabic text with Cairo font.
"""
import io
from datetime import datetime
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    pdfmetrics.registerFont(TTFont('Cairo', 'C:/Windows/Fonts/arial.ttf'))
    ARABIC_FONT = 'Cairo'
except Exception:
    try:
        # محاولة بديلة: خط arialuni
        pdfmetrics.registerFont(TTFont('Cairo', 'C:/Windows/Fonts/arialuni.ttf'))
        ARABIC_FONT = 'Cairo'
    except Exception:
        ARABIC_FONT = 'Helvetica'


def export_to_pdf(title, headers, rows, filename="report", summary=None):
    """
    Export a table to PDF.

    title: Report title (Arabic)
    headers: list of header strings
    rows: list of lists (each inner list is a row)
    filename: output filename
    summary: optional dict with summary data
    """
    buffer = io.BytesIO()
    try:
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=2*cm, bottomMargin=1.5*cm)

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('ArabicTitle', parent=styles['Title'], fontName=ARABIC_FONT, fontSize=16, alignment=1, spaceAfter=10)
        header_style = ParagraphStyle('ArabicHeader', parent=styles['Normal'], fontName=ARABIC_FONT, fontSize=9, textColor=colors.white, alignment=1)
        cell_style = ParagraphStyle('ArabicCell', parent=styles['Normal'], fontName=ARABIC_FONT, fontSize=8, alignment=1)
        summary_style = ParagraphStyle('Summary', parent=styles['Normal'], fontName=ARABIC_FONT, fontSize=10, alignment=1, spaceBefore=10)

        elements = []
        elements.append(Paragraph(title, title_style))

        date_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        date_style = ParagraphStyle('Date', parent=styles['Normal'], fontName=ARABIC_FONT, fontSize=8, alignment=1, textColor=colors.grey)
        elements.append(Paragraph(f'تاريخ التقرير: {date_str}', date_style))
        elements.append(Spacer(1, 10))

        if not headers:
            headers = ['لا توجد بيانات']

        table_data = [[Paragraph(str(h), header_style) for h in headers]]
        for row in rows:
            table_data.append([Paragraph(str(cell), cell_style) for cell in row])

        num_cols = len(headers)
        available_width = landscape(A4)[0] - 3*cm
        col_width = available_width / num_cols

        table = Table(table_data, colWidths=[col_width]*num_cols, repeatRows=1)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A237E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), ARABIC_FONT),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F5F5')]),
        ])
        table.setStyle(style)
        elements.append(table)

        if summary:
            elements.append(Spacer(1, 15))
            for key, value in summary.items():
                elements.append(Paragraph(f'{key}: {value}', summary_style))

        doc.build(elements)
    finally:
        buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    response['Content-Disposition'] = f'attachment; filename="{filename}_{ts}.pdf"'
    return response
