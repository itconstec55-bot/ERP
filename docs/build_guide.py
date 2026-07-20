#!/usr/bin/env python3
"""
Build PDF + HTML from Arabic Markdown.
Usage:
  python build_pdf.py ar                          (default: build PDF+HTML for the procedures guide)
  python build_pdf.py ar input.md output.pdf      (custom paths)
  python build_pdf.py en                          (English mode)
"""

import html as html_mod
import os
import re
import sys

import arabic_reshaper

try:
    from bidi.algorithm import get_display

    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False

# ── PDF imports (ReportLab) ──
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus import Image as RLImage

# ── Fonts ──
FONT_PATH = r'C:\Windows\Fonts\arial.ttf'
BOLD_PATH = r'C:\Windows\Fonts\arialbd.ttf'
if not os.path.exists(BOLD_PATH):
    BOLD_PATH = FONT_PATH
pdfmetrics.registerFont(TTFont('Arabic', FONT_PATH))
pdfmetrics.registerFont(TTFont('Arabic-Bold', BOLD_PATH))
pdfmetrics.registerFontFamily('Arabic', normal='Arabic', bold='Arabic-Bold', italic='Arabic', boldItalic='Arabic-Bold')

# ── Language ──
LANG = sys.argv[1] if len(sys.argv) > 1 else 'ar'


# ═══════════════════════════════════════════════════════
#  Arabic Text Processing
# ═══════════════════════════════════════════════════════
def ar(text):
    """Reshape Arabic + apply BiDi for PDF/ReportLab."""
    if LANG == 'en' or not text:
        return text
    try:
        shaped = arabic_reshaper.reshape(text)
    except Exception:
        shaped = text
    if HAS_BIDI:
        try:
            return get_display(shaped)
        except Exception:
            pass
    return shaped


def ar_html(text):
    """Keep original Arabic for HTML (browser handles BiDi natively)."""
    return text


# ═══════════════════════════════════════════════════════
#  SVG to PNG (optional)
# ═══════════════════════════════════════════════════════
def svg_to_png(svg_path, png_path, width_pt=450):
    try:
        import cairosvg

        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=width_pt * 2)
        return True
    except Exception:
        return False


def get_image_or_placeholder_rlab(img_path, width_pt=450, codest=None):
    if os.path.exists(img_path):
        if img_path.lower().endswith('.svg'):
            png_path = img_path.rsplit('.', 1)[0] + '_tmp.png'
            if svg_to_png(img_path, png_path, width_pt):
                img_path = png_path
            else:
                return Table([[Paragraph('[SVG: ' + os.path.basename(img_path) + ']', codest)]], colWidths=[width_pt])
        try:
            img = RLImage(img_path, width=width_pt, height=width_pt * 0.5)
            img.hAlign = 'CENTER'
            return img
        except Exception:
            pass
    return Table([[Paragraph('[image: ' + os.path.basename(img_path) + ']', codest)]], colWidths=[width_pt])


# ═══════════════════════════════════════════════════════
#  PDF Styles
# ═══════════════════════════════════════════════════════
PAGE_W = 21 * cm
MARGIN = 2 * cm
AVAIL = PAGE_W - 2 * MARGIN

body_st = ParagraphStyle('body', fontName='Arabic', fontSize=10.5, leading=16, alignment=TA_RIGHT, wordWrap='RTL')
h1_st = ParagraphStyle(
    'h1',
    parent=body_st,
    fontName='Arabic-Bold',
    fontSize=16,
    leading=22,
    spaceBefore=14,
    spaceAfter=6,
    alignment=TA_RIGHT,
)
h2_st = ParagraphStyle(
    'h2',
    parent=body_st,
    fontName='Arabic-Bold',
    fontSize=13,
    leading=19,
    spaceBefore=10,
    spaceAfter=4,
    alignment=TA_RIGHT,
)
h3_st = ParagraphStyle(
    'h3',
    parent=body_st,
    fontName='Arabic-Bold',
    fontSize=11.5,
    leading=17,
    spaceBefore=6,
    spaceAfter=3,
    alignment=TA_RIGHT,
)
quote_st = ParagraphStyle(
    'quote', parent=body_st, leftIndent=12, rightIndent=12, backColor=colors.HexColor('#eef2f7'), borderPadding=5
)
cell_st = ParagraphStyle('cell', parent=body_st, fontSize=8.6, leading=12, alignment=TA_RIGHT, wordWrap='RTL')
code_st = ParagraphStyle(
    'code',
    fontName='Arabic',
    fontSize=8,
    leading=11,
    alignment=TA_LEFT,
    wordWrap='LTR',
    backColor=colors.HexColor('#f4f4f4'),
    borderPadding=5,
    textColor=colors.HexColor('#222222'),
)

if LANG == 'en':
    for _st in (body_st, h1_st, h2_st, h3_st, quote_st, cell_st):
        _st.alignment = TA_LEFT
        _st.wordWrap = 'LTR'


def md_inline(s):
    return s.replace('`', '')


# ═══════════════════════════════════════════════════════
#  Markdown -> PDF flowables
# ═══════════════════════════════════════════════════════
def parse_pdf(md_lines):
    flow = []
    i, n = 0, len(md_lines)
    in_code = False
    code_buf = []

    while i < n:
        line = md_lines[i]

        # Fenced code block
        if line.strip().startswith('```'):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                txt = '\n'.join(code_buf)
                safe = txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                t = Table([[Paragraph(safe, code_st)]], colWidths=[AVAIL])
                t.setStyle(
                    TableStyle(
                        [
                            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f4f4f4')),
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                        ]
                    )
                )
                flow.append(t)
                flow.append(Spacer(1, 4))
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Blank line
        if stripped == '':
            flow.append(Spacer(1, 5))
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^(-{3,}|\*{3,})$', stripped):
            flow.append(
                HRFlowable(width='100%', thickness=0.6, color=colors.HexColor('#bbbbbb'), spaceBefore=4, spaceAfter=4)
            )
            i += 1
            continue

        # Image ![alt](path)
        img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', stripped)
        if img_match:
            img_rel = img_match.group(2)
            img_abs = os.path.normpath(os.path.join(os.path.dirname(src), img_rel))
            flow.append(Spacer(1, 6))
            flow.append(get_image_or_placeholder_rlab(img_abs, width_pt=AVAIL * 0.85, codest=code_st))
            flow.append(Spacer(1, 6))
            i += 1
            continue

        # Blockquote
        if stripped.startswith('>'):
            buf = []
            while i < n and md_lines[i].strip().startswith('>'):
                buf.append(ar(md_inline(md_lines[i].strip()[1:].strip())))
                i += 1
            flow.append(Paragraph('<br/>'.join(buf), quote_st))
            flow.append(Spacer(1, 4))
            continue

        # Heading
        if stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            txt = ar(md_inline(stripped.lstrip('#').strip()))
            st = {1: h1_st, 2: h2_st, 3: h3_st}.get(level, body_st)
            flow.append(Paragraph(txt, st))
            i += 1
            continue

        # Bullet list
        if stripped.startswith('- ') or stripped.startswith('* '):
            buf = []
            while i < n and (md_lines[i].strip().startswith('- ') or md_lines[i].strip().startswith('* ')):
                buf.append('\u2022 ' + ar(md_inline(md_lines[i].strip()[2:].strip())))
                i += 1
            flow.append(Paragraph('<br/>'.join(buf), body_st))
            flow.append(Spacer(1, 3))
            continue

        # Table
        if stripped.startswith('|') and '|' in stripped[1:]:
            rows = []
            while i < n and md_lines[i].strip().startswith('|'):
                rows.append(md_lines[i].strip())
                i += 1
            data = []
            for ri, r in enumerate(rows):
                if ri == 1:
                    continue  # skip separator
                cells = [c.strip() for c in r.strip('|').split('|')]
                data.append([Paragraph(ar(md_inline(c)), cell_st) for c in cells])
            if data:
                colw = [AVAIL * 0.18, AVAIL * 0.30, AVAIL * 0.52][: len(data[0])]
                if len(colw) < len(data[0]):
                    colw = [AVAIL / len(data[0])] * len(data[0])
                tbl = Table(data, colWidths=colw, repeatRows=1)
                tbl.setStyle(
                    TableStyle(
                        [
                            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 4),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                            ('TOPPADDING', (0, 0), (-1, -1), 3),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fc')]),
                        ]
                    )
                )
                flow.append(tbl)
                flow.append(Spacer(1, 5))
            continue

        # Normal paragraph
        flow.append(Paragraph(ar(md_inline(stripped)), body_st))
        flow.append(Spacer(1, 4))
        i += 1

    return flow


# ═══════════════════════════════════════════════════════
#  Markdown -> HTML
# ═══════════════════════════════════════════════════════
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Cairo', 'Arial', sans-serif; direction: rtl;
       background: #f5f6fa; color: #222; line-height: 1.8; }
.container { max-width: 960px; margin: 0 auto; padding: 30px 24px; background: #fff;
             box-shadow: 0 2px 20px rgba(0,0,0,.08); min-height: 100vh; }
h1 { font-size: 1.8rem; color: #1a237e; border-bottom: 3px solid #1a237e;
     padding-bottom: 8px; margin: 28px 0 16px; }
h2 { font-size: 1.4rem; color: #0d47a1; margin: 22px 0 12px;
     border-right: 4px solid #ff6f00; padding-right: 12px; }
h3 { font-size: 1.15rem; color: #333; margin: 16px 0 8px; }
p { margin: 8px 0; text-align: justify; }
a { color: #0d47a1; text-decoration: none; }
a:hover { text-decoration: underline; }
strong { color: #1a237e; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.9rem; }
th { background: #1a237e; color: #fff; padding: 8px 10px; text-align: right; }
td { padding: 7px 10px; border: 1px solid #ddd; text-align: right; }
tr:nth-child(even) td { background: #f6f8fc; }
blockquote { background: #eef2f7; border-right: 4px solid #90caf9;
             padding: 12px 16px; margin: 12px 0; border-radius: 4px; }
pre { background: #f4f4f4; border: 1px solid #ccc; border-radius: 6px;
      padding: 14px; direction: ltr; text-align: left; overflow-x: auto;
      font-size: 0.82rem; line-height: 1.5; margin: 12px 0; }
code { background: #f0f0f0; padding: 2px 5px; border-radius: 3px; font-size: 0.88em; }
pre code { background: none; padding: 0; }
ul { margin: 8px 20px 8px 0; }
li { margin: 4px 0; }
hr { border: none; border-top: 1px solid #ddd; margin: 20px 0; }
img { max-width: 100%; height: auto; display: block; margin: 16px auto; border-radius: 6px; }
.toc { background: #f8f9fb; border: 1px solid #e0e0e0; border-radius: 8px;
       padding: 20px 24px; margin: 20px 0; }
.toc a { display: block; padding: 3px 0; color: #1a237e; }
.toc a:hover { color: #ff6f00; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
         font-size: 0.8rem; color: #fff; margin-left: 4px; }
.badge-green { background: #2e7d32; }
.badge-red { background: #c62828; }
.badge-blue { background: #1565c0; }
.badge-orange { background: #e65100; }
@media print {
  body { background: #fff; }
  .container { box-shadow: none; padding: 10px; }
  .no-print { display: none !important; }
}
@media (max-width: 768px) {
  .container { padding: 16px 12px; }
  table { font-size: 0.8rem; }
  th, td { padding: 5px 6px; }
}
"""


def md_to_html(md_text, doc_title):
    """Convert Markdown to styled HTML with native Arabic support."""
    lines = md_text.split('\n')
    parts = []
    in_code = False
    code_buf = []
    in_table = False
    table_rows = []
    in_toc = False

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            return ''
        header = table_rows[0]
        sep_idx = 1 if len(table_rows) > 1 and re.match(r'^[\s|:-]+$', table_rows[1]) else 0
        data_rows = table_rows[sep_idx + 1 :] if sep_idx else table_rows[1:]
        hdr_cells = [c.strip() for c in header.strip('|').split('|')]
        h_html = ''.join(f'<th>{html_mod.escape(c)}</th>' for c in hdr_cells)
        body_html = ''
        for r in data_rows:
            cells = [c.strip() for c in r.strip('|').split('|')]
            body_html += '<tr>' + ''.join(f'<td>{inline_md(c)}</td>' for c in cells) + '</tr>'
        in_table = False
        table_rows = []
        return f'<table><thead><tr>{h_html}</tr></thead><tbody>{body_html}</tbody></table>'

    def inline_md(text):
        t = html_mod.escape(text)
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
        t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)
        return t

    for line in lines:
        stripped = line.strip()

        # Fenced code
        if stripped.startswith('```'):
            if not in_code:
                if in_table:
                    parts.append(flush_table())
                in_code = True
                code_buf = []
            else:
                in_code = False
                code_text = html_mod.escape('\n'.join(code_buf))
                parts.append(f'<pre><code>{code_text}</code></pre>')
            continue
        if in_code:
            code_buf.append(line)
            continue

        # Table rows
        if stripped.startswith('|') and '|' in stripped[1:]:
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(stripped)
            continue
        elif in_table:
            parts.append(flush_table())

        # Blank
        if stripped == '':
            continue

        # HR
        if re.match(r'^(-{3,}|\*{3,})$', stripped):
            parts.append('<hr>')
            continue

        # Image
        img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', stripped)
        if img_match:
            alt = html_mod.escape(img_match.group(1))
            src_attr = html_mod.escape(img_match.group(2))
            parts.append(f'<img src="{src_attr}" alt="{alt}">')
            continue

        # Headings
        if stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            txt = inline_md(stripped.lstrip('#').strip())
            tag = f'h{min(level, 6)}'
            parts.append(f'<{tag}>{txt}</{tag}>')
            continue

        # Blockquote
        if stripped.startswith('>'):
            buf = []
            while stripped.startswith('>'):
                buf.append(inline_md(stripped[1:].strip()))
                lines.pop(0) if lines else None
                if not lines:
                    break
                stripped = lines[0].strip()
            parts.append(f'<blockquote>{"<br>".join(buf)}</blockquote>')
            continue

        # Bullet
        if stripped.startswith('- ') or stripped.startswith('* '):
            items = []
            while stripped.startswith('- ') or stripped.startswith('* '):
                items.append(f'<li>{inline_md(stripped[2:].strip())}</li>')
                lines.pop(0) if lines else None
                if not lines:
                    break
                stripped = lines[0].strip()
            parts.append('<ul>' + ''.join(items) + '</ul>')
            continue

        # Normal paragraph
        parts.append(f'<p>{inline_md(stripped)}</p>')

    if in_table:
        parts.append(flush_table())

    body = '\n'.join(parts)
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_mod.escape(doc_title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
{body}
</div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════
if LANG == 'en':
    src = r'J:\2027\accounting_system\docs\technical_spec_workflow.en.md'
    pdf_out = r'J:\2027\accounting_system\docs\technical_spec_workflow.en.pdf'
    doc_title = 'Technical Specification Document - Workflow'
elif len(sys.argv) > 2:
    src = sys.argv[2]
    pdf_out = sys.argv[3] if len(sys.argv) > 3 else src.rsplit('.', 1)[0] + '.pdf'
    doc_title = 'دليل الإجراءات التقنية الموحدة'
else:
    src = r'D:\accounting_system\docs\دليل_الإجراءات_التقنية_الموحدة.md'
    pdf_out = r'D:\accounting_system\docs\دليل_الإجراءات_التقنية_الموحدة.pdf'
    doc_title = 'دليل الإجراءات التقنية الموحدة'

md_text = open(src, encoding='utf-8').read()

# ── Build PDF ──
md_lines = md_text.split('\n')
doc = SimpleDocTemplate(
    pdf_out,
    pagesize=(21 * cm, 29.7 * cm),
    leftMargin=MARGIN,
    rightMargin=MARGIN,
    topMargin=MARGIN,
    bottomMargin=MARGIN,
    title=doc_title,
    author='Engineering',
)
doc.build(parse_pdf(md_lines))
print('PDF OK:', os.path.getsize(pdf_out), 'bytes')

# ── Build HTML ──
html_out = pdf_out.rsplit('.', 1)[0] + '.html'
html_content = md_to_html(md_text, doc_title)
open(html_out, 'w', encoding='utf-8').write(html_content)
print('HTML OK:', os.path.getsize(html_out), 'bytes')
