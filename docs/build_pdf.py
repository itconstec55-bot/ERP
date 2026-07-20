import io, os, re, sys, unicodedata, tempfile
import arabic_reshaper
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Preformatted, HRFlowable, KeepTogether,
                                Image as RLImage)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT, TA_CENTER
from reportlab.lib import colors
from reportlab.lib.units import cm

FONT_PATH = r'C:\Windows\Fonts\arial.ttf'
BOLD_PATH = r'C:\Windows\Fonts\arialbd.ttf'
if not os.path.exists(BOLD_PATH):
    BOLD_PATH = FONT_PATH

pdfmetrics.registerFont(TTFont('Arabic', FONT_PATH))
pdfmetrics.registerFont(TTFont('Arabic-Bold', BOLD_PATH))
pdfmetrics.registerFontFamily('Arabic', normal='Arabic', bold='Arabic-Bold',
                              italic='Arabic', boldItalic='Arabic-Bold')

# ---------- SVG to PNG conversion ----------
def svg_to_png(svg_path, png_path, width_pt=450):
    """Convert SVG to PNG using cairosvg, falling back to a placeholder if unavailable."""
    try:
        import cairosvg
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=width_pt * 2)
        return True
    except Exception:
        return False

def get_image_or_placeholder(img_path, width_pt=450):
    """Try to load an image; return a placeholder table if image not available."""
    if os.path.exists(img_path):
        if img_path.lower().endswith('.svg'):
            png_path = img_path.rsplit('.', 1)[0] + '_tmp.png'
            if svg_to_png(img_path, png_path, width_pt):
                img_path = png_path
            else:
                return Table([[Paragraph('[صورة: ' + os.path.basename(img_path) + ']', codest)]],
                           colWidths=[width_pt])
        try:
            img = RLImage(img_path, width=width_pt, height=width_pt * 0.5)
            img.hAlign = 'CENTER'
            return img
        except Exception:
            pass
    return Table([[Paragraph('[صورة: ' + os.path.basename(img_path) + ']', codest)]],
               colWidths=[width_pt])

# ---------- Arabic shaping + Unicode BiDi ----------
LANG = sys.argv[1] if len(sys.argv) > 1 else 'ar'

try:
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False

def ar(text):
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
    # Fallback: simple reversal for pure Arabic text
    return shaped[::-1] if shaped else shaped

# ---------- Styles ----------
PAGE_W = 21 * cm
MARGIN = 2 * cm
AVAIL = PAGE_W - 2 * MARGIN

body = ParagraphStyle('body', fontName='Arabic', fontSize=10.5, leading=16,
                      alignment=TA_RIGHT, wordWrap='RTL', firstLineIndent=0)
h1 = ParagraphStyle('h1', parent=body, fontName='Arabic-Bold', fontSize=16,
                    leading=22, spaceBefore=12, spaceAfter=6, alignment=TA_RIGHT)
h2 = ParagraphStyle('h2', parent=body, fontName='Arabic-Bold', fontSize=13,
                    leading=19, spaceBefore=9, spaceAfter=4, alignment=TA_RIGHT)
h3 = ParagraphStyle('h3', parent=body, fontName='Arabic-Bold', fontSize=11.5,
                    leading=17, spaceBefore=6, spaceAfter=3, alignment=TA_RIGHT)
quote = ParagraphStyle('quote', parent=body, leftIndent=12, rightIndent=12,
                       backColor=colors.HexColor('#eef2f7'), borderPadding=5)
cellst = ParagraphStyle('cell', parent=body, fontSize=8.6, leading=12,
                        alignment=TA_RIGHT, wordWrap='RTL')
codest = ParagraphStyle('code', fontName='Arabic', fontSize=8, leading=11,
                        alignment=TA_LEFT, wordWrap='LTR',
                        backColor=colors.HexColor('#f4f4f4'), borderPadding=5,
                        textColor=colors.HexColor('#222222'))

def md_inline(s):
    return s.replace('`', '')

if LANG == 'en':
    for _st in (body, h1, h2, h3, quote, cellst):
        _st.alignment = TA_LEFT
        _st.wordWrap = 'LTR'
    codest.alignment = TA_LEFT
    codest.wordWrap = 'LTR'

# ---------- Markdown -> flowables ----------
def parse(md_lines):
    flow = []
    i = 0
    n = len(md_lines)
    in_code = False
    code_buf = []
    while i < n:
        line = md_lines[i]
        if line.strip().startswith('```'):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                txt = '\n'.join(code_buf)
                t = Table([[Paragraph(txt.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), codest)]],
                          colWidths=[AVAIL])
                t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f4f4f4')),
                                       ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc'))]))
                flow.append(t)
                flow.append(Spacer(1, 4))
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()
        if stripped == '':
            flow.append(Spacer(1, 5))
            i += 1
            continue
        if re.match(r'^(-{3,}|\*{3,})$', stripped):
            flow.append(HRFlowable(width='100%', thickness=0.6,
                                   color=colors.HexColor('#bbbbbb'), spaceBefore=4, spaceAfter=4))
            i += 1
            continue
        # Image: ![alt](path)
        img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', stripped)
        if img_match:
            alt_text = img_match.group(1)
            img_rel = img_match.group(2)
            # Resolve relative to the source markdown file's directory
            img_abs = os.path.join(os.path.dirname(src), img_rel)
            img_abs = os.path.normpath(img_abs)
            flow.append(Spacer(1, 6))
            flow.append(get_image_or_placeholder(img_abs, width_pt=AVAIL * 0.85))
            flow.append(Spacer(1, 6))
            i += 1
            continue
        if stripped.startswith('>'):
            buf = []
            while i < n and md_lines[i].strip().startswith('>'):
                buf.append(ar(md_inline(md_lines[i].strip()[1:].strip())))
                i += 1
            flow.append(Paragraph('<br/>'.join(buf), quote))
            flow.append(Spacer(1, 4))
            continue
        if stripped.startswith('#'):
            level = len(stripped) - len(stripped.lstrip('#'))
            txt = ar(md_inline(stripped.lstrip('#').strip()))
            st = {1: h1, 2: h2, 3: h3}.get(level, body)
            flow.append(Paragraph(txt, st))
            i += 1
            continue
        if stripped.startswith('- ') or stripped.startswith('* '):
            buf = []
            while i < n and (md_lines[i].strip().startswith('- ') or md_lines[i].strip().startswith('* ')):
                buf.append('• ' + ar(md_inline(md_lines[i].strip()[2:].strip())))
                i += 1
            flow.append(Paragraph('<br/>'.join(buf), body))
            flow.append(Spacer(1, 3))
            continue
        if stripped.startswith('|') and '|' in stripped[1:]:
            rows = []
            while i < n and md_lines[i].strip().startswith('|'):
                rows.append(md_lines[i].strip())
                i += 1
            # rows[0]=header, rows[1]=separator (discard)
            data = []
            for ri, r in enumerate(rows):
                if ri == 1:
                    continue
                cells = [c.strip() for c in r.strip('|').split('|')]
                data.append([Paragraph(ar(md_inline(c)), cellst) for c in cells])
            if data:
                colw = [AVAIL * 0.18, AVAIL * 0.30, AVAIL * 0.52][:len(data[0])]
                if len(colw) < len(data[0]):
                    colw = [AVAIL / len(data[0])] * len(data[0])
                tbl = Table(data, colWidths=colw, repeatRows=1)
                tbl.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4e73df')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 4),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8fc')]),
                ]))
                flow.append(tbl)
                flow.append(Spacer(1, 5))
            continue
        # normal paragraph
        flow.append(Paragraph(ar(md_inline(stripped)), body))
        flow.append(Spacer(1, 4))
        i += 1
    return flow

if LANG == 'en':
    src = r'J:\2027\accounting_system\docs\technical_spec_workflow.en.md'
    out = r'J:\2027\accounting_system\docs\technical_spec_workflow.en.pdf'
    doc_title = 'Technical Specification Document - Workflow'
elif len(sys.argv) > 2:
    src = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else src.rsplit('.', 1)[0] + '.pdf'
    doc_title = 'دليل الإجراءات التقنية الموحدة'
else:
    src = r'D:\accounting_system\docs\دليل_الإجراءات_التقنية_الموحدة.md'
    out = r'D:\accounting_system\docs\دليل_الإجراءات_التقنية_الموحدة.pdf'
    doc_title = 'دليل الإجراءات التقنية الموحدة'
lines = io.open(src, encoding='utf-8').read().split('\n')
doc = SimpleDocTemplate(out, pagesize=(21 * cm, 29.7 * cm),
                        leftMargin=MARGIN, rightMargin=MARGIN,
                        topMargin=MARGIN, bottomMargin=MARGIN,
                        title=doc_title,
                        author='Engineering')
doc.build(parse(lines))
print('PDF built OK:', os.path.getsize(out), 'bytes')
