import os

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors

H = 860
W = 600
X, BW, BH = 130, 340, 56


def ry(top_y, h=BH):
    return H - top_y - h


boxes = [
    (56, '1 . Browser', 'HTTP GET/POST + CSRF token', colors.HexColor('#4e73df'), colors.white),
    (142, '2 . Nginx', 'Reverse Proxy / TLS termination', colors.HexColor('#4e73df'), colors.white),
    (228, '3 . Gunicorn / runserver', 'WSGI @ 127.0.0.1:8012', colors.HexColor('#4e73df'), colors.white),
    (314, '4 . Middleware', 'Throttle -> Session -> CSRF', colors.HexColor('#4e73df'), colors.white),
    (400, '5 . URL Router', 'include(apps) + namespaces', colors.HexColor('#4e73df'), colors.white),
    (486, '6 . View', 'permission check -> ORM query', colors.HexColor('#f6c23e'), colors.HexColor('#222222')),
    (572, '7 . Database', 'SQLite / PostgreSQL (atomic+lock)', colors.HexColor('#1cc88a'), colors.white),
    (658, '8 . Context + Template', 'DTL render + static assets', colors.HexColor('#4e73df'), colors.white),
]

d = Drawing(W, H)

# connectors (solid, top->down)
for i in range(len(boxes) - 1):
    y1 = ry(boxes[i][0], BH)
    y2 = ry(boxes[i + 1][0], 0)
    d.add(Line(W / 2, y1, W / 2, y2, strokeColor=colors.HexColor('#33475b'), strokeWidth=2.5))
    # arrowhead pointing toward next (downward on screen => +y in reportlab)
    d.add(
        Polygon(
            [W / 2 - 6, y2 - 2, W / 2 + 6, y2 - 2, W / 2, y2 + 8],
            fillColor=colors.HexColor('#33475b'),
            strokeColor=colors.HexColor('#33475b'),
        )
    )

# boxes
for top_y, lbl, sub, fill, tcol in boxes:
    y = ry(top_y)
    d.add(Rect(X, y, BW, BH, rx=9, ry=9, fillColor=fill, strokeColor=colors.HexColor('#2e4fb0'), strokeWidth=1.5))
    d.add(
        String(W / 2, y + BH / 2 + 7, lbl, fontSize=15, fillColor=tcol, textAnchor='middle', fontName='Helvetica-Bold')
    )
    d.add(String(W / 2, y + BH / 2 - 9, sub, fontSize=10, fillColor=colors.HexColor('#eef2ff'), textAnchor='middle'))

# return (response) dashed arrow on the right
xr = X + BW + 20
y8 = ry(658, 28)
y1 = ry(56, 28)
d.add(Line(xr, y8, xr, y1, strokeColor=colors.HexColor('#1cc88a'), strokeWidth=2.5, strokeDashArray=[6, 4]))
# arrowhead at top (pointing up toward box1)
d.add(
    Polygon(
        [xr - 6, y1 + 2, xr + 6, y1 + 2, xr, y1 - 8],
        fillColor=colors.HexColor('#1cc88a'),
        strokeColor=colors.HexColor('#1cc88a'),
    )
)

d.add(
    String(
        W / 2,
        30,
        'Data Flow: Browser <-> Django Backend',
        fontSize=18,
        fillColor=colors.HexColor('#222222'),
        textAnchor='middle',
        fontName='Helvetica-Bold',
    )
)

out = os.path.join(os.path.dirname(__file__), 'data_flow.pdf')
renderPDF.drawToFile(d, out, 'Data Flow Diagram')
print('PDF written:', out)
