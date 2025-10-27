# app.py
from io import BytesIO
from flask import Flask, request, render_template_string, send_file, abort
from reportlab.lib.pagesizes import mm
from reportlab.pdfgen import canvas
import os
from functools import wraps
from flask import Response

app = Flask(__name__)

# Basic auth decorator
def check_auth(username, password):
    return username == 'admin' and password == os.getenv('REPORT_PASS', '')

def authenticate():
    return Response(
        'Authentication required', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

INDEX_HTML = """
<!doctype html>
<title>AF STREAM - Revenue Ticket Generator</title>
<h2>AF STREAM - Revenue Ticket Generator</h2>
<form method=post action="/generate">
  Mes y Año: <input type="text" name="month" placeholder="May 2025" required><br><br>
  Fecha del reporte: <input type="text" name="date" placeholder="June 1, 2025" required><br><br>
  Agreement Id: <input type="text" name="agreement" placeholder="1f97..." required size=40><br><br>
  Dueño / Cliente: <input type="text" name="owner" placeholder="BIDGEAR JOINT STOCK COMPANY" required size=50><br><br>
  Radios (una por línea: radio, monto):<br>
  <textarea name="lines" rows=10 cols=60 placeholder="mangabuddy.com, 1200" required></textarea><br><br>
  <button type="submit">Generar PDF (ticket)</button>
</form>
<p style="font-size:0.9em;color:#666">Protegido con usuario: <b>admin</b> (contraseña en variable REPORT_PASS)</p>
"""

@app.route("/")
@requires_auth
def index():
    return render_template_string(INDEX_HTML)

@app.route("/generate", methods=["POST"])
@requires_auth
def generate():
    month = request.form.get("month","").strip()
    date = request.form.get("date","").strip()
    agreement = request.form.get("agreement","").strip()
    owner = request.form.get("owner","").strip()
    lines_raw = request.form.get("lines","").strip()

    # parse lines
    items = []
    total = 0.0
    for ln in lines_raw.splitlines():
        ln = ln.strip()
        if not ln: continue
        if ',' in ln:
            name, amount = ln.split(',',1)
            try:
                amt = float(amount.replace('$','').replace(',','').strip())
            except:
                amt = 0.0
            items.append((name.strip(), amt))
            total += amt
        else:
            # if no comma, consider whole line name and zero amount
            items.append((ln, 0.0))

    # create PDF in memory (ticket width 80mm)
    buffer = BytesIO()
    width_mm = 80
    # convert mm to points (1 mm = 2.83465 points)
    page_width = width_mm * 2.83465
    # set a tall height; reportlab needs a fixed pagesize; we'll use 200mm height (~ enough) but text won't overflow for reasonable content
    page_height = 200 * 2.83465

    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    x = 10
    y = page_height - 15

    # monospaced-like look
    c.setFont("Courier", 9)

    def draw_line(text):
        nonlocal y
        c.drawString(x, y, text)
        y -= 12

    draw_line("AF STREAM, LLC")
    draw_line(f"Revenue Report – {month}")
    draw_line(f"Date: {date}")
    draw_line(f"Agreement Id: {agreement}")
    draw_line("")
    draw_line(f"Details of the revenue generated for {owner}")
    draw_line("-" * 28)

    for name, amt in items:
        # format amount with commas and two decimals
        amt_str = "${:,.2f}".format(amt)
        # pad/truncate name so columns align visually
        max_name_len = 24
        if len(name) > max_name_len:
            name = name[:max_name_len-3] + "..."
        # create line with spacing
        space = max_name_len - len(name) + 1
        line = f"{name}{' ' * space}{amt_str}"
        draw_line(line)

    draw_line("-" * 28)
    draw_line(f"TOTAL{' ' * 18}${total:,.2f}")
    draw_line("-" * 28)
    draw_line("")
    draw_line("End of Report")

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"Revenue_{month.replace(' ','_')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))