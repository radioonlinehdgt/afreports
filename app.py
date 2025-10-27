from io import BytesIO
from flask import Flask, request, render_template_string, send_file, abort, Response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import os
from functools import wraps
import textwrap

app = Flask(__name__)

# --- Autenticación básica ---
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

# --- Interfaz simple ---
INDEX_HTML = """
<!doctype html>
<title>AF STREAM - Revenue Report Generator</title>
<h2>AF STREAM - Revenue Report Generator</h2>
<form method=post action="/generate">
  Mes y Año: <input type="text" name="month" placeholder="May 2025" required><br><br>
  Fecha del reporte: <input type="text" name="date" placeholder="June 1, 2025" required><br><br>
  Agreement Id: <input type="text" name="agreement" placeholder="1f97..." required size=40><br><br>
  Dueño / Cliente: <input type="text" name="owner" placeholder="BIDGEAR JOINT STOCK COMPANY" required size=50><br><br>
  Radios (una por línea: radio, monto):<br>
  <textarea name="lines" rows=10 cols=60 placeholder="mangabuddy.com, 1200" required></textarea><br><br>
  <button type="submit">Generar PDF (hoja carta)</button>
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

    # Parsear líneas de radios
    items = []
    total = 0.0
    for ln in lines_raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ',' in ln:
            name, amount = ln.split(',', 1)
            try:
                amt = float(amount.replace('$','').replace(',','').strip())
            except:
                amt = 0.0
            items.append((name.strip(), amt))
            total += amt
        else:
            items.append((ln, 0.0))

    # --- Crear PDF tamaño carta con márgenes amplios ---
    buffer = BytesIO()
    page_width, page_height = letter
    margin = 5 * cm  # márgenes de 5 cm en todos los lados

    c = canvas.Canvas(buffer, pagesize=letter)
    x = margin
    y = page_height - margin

    c.setFont("Courier", 10)


    def draw_line(text, font="Courier", size=10, leading=14):
        """Dibuja texto con saltos automáticos respetando los márgenes reales"""
        nonlocal y
        c.setFont(font, size)
        max_width = page_width - 2 * margin
        words = text.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if c.stringWidth(test_line, font, size) <= max_width:
                line = test_line
            else:
                c.drawString(x, y, line)
                y -= leading
                line = word
        if line:
            c.drawString(x, y, line)
            y -= leading


    
    
    draw_line("AF STREAM, LLC", "Courier-Bold", 11)
    draw_line(f"Revenue Report – {month}")
    draw_line(f"Date: {date}")
    draw_line(f"Agreement Id: {agreement}")
    draw_line("")
    draw_line(f"Details of the revenue generated for {owner} through the insertion of digital audio ads in its digital media, under the terms of the respective agreement.")
    draw_line("-" * 90)

    for name, amt in items:
        amt_str = "${:,.2f}".format(amt)
        max_name_len = 40
        if len(name) > max_name_len:
            name = name[:max_name_len-3] + "..."
        space = max_name_len - len(name) + 1
        line = f"{name}{' ' * space}{amt_str}"
        draw_line(line)

    draw_line("-" * 90)
    c.setFont("Courier-Bold", 10)
    draw_line(f"TOTAL{' ' * 34}${total:,.2f}")
    c.setFont("Courier", 10)
    draw_line("-" * 90)
    draw_line("")
    draw_line("End of Report")


    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"Revenue_{month.replace(' ','_')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))






