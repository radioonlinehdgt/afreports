from io import BytesIO
from flask import Flask, request, render_template_string, send_file, Response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_JUSTIFY
import os
from functools import wraps

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

    # --- Crear PDF tamaño carta con márgenes uniformes de 3cm ---
    buffer = BytesIO()
    page_width, page_height = letter
    margin = 3 * cm

    c = canvas.Canvas(buffer, pagesize=letter)
    x = margin
    y = page_height - margin

    # Calcular ancho disponible
    available_width = page_width - 2 * margin
    
    # Configurar fuente
    font_name = "Courier"
    font_size = 10
    line_height = 14
    
    def draw_text(text, font="Courier", size=10, bold=False):
        """Dibuja texto simple en una línea"""
        nonlocal y
        if bold:
            c.setFont(f"{font}-Bold", size)
        else:
            c.setFont(font, size)
        c.drawString(x, y, text)
        y -= line_height
    
    def draw_wrapped_text(text, font="Courier", size=10):
        """Dibuja texto con wrapping automático usando Paragraph"""
        nonlocal y
        
        # Crear estilo para el párrafo
        style = ParagraphStyle(
            'CustomStyle',
            fontName=font,
            fontSize=size,
            leading=line_height,
            leftIndent=0,
            rightIndent=0,
            alignment=TA_JUSTIFY,
            wordWrap='LTR',
            spaceBefore=0,
            spaceAfter=0
        )
        
        # Crear párrafo
        para = Paragraph(text, style)
        
        # Calcular alto necesario
        w, h = para.wrap(available_width, 1000)
        
        # Dibujar el párrafo en la posición actual
        para.drawOn(c, x, y - h + line_height)
        y -= h
    
    def draw_separator():
        """Dibuja línea separadora"""
        nonlocal y
        # Calcular cuántos guiones caben
        char_width = c.stringWidth("-", font_name, font_size)
        num_dashes = int(available_width / char_width)
        separator = "-" * num_dashes
        draw_text(separator)
    
    # Encabezado
    draw_text("AF STREAM", "Courier", 11, bold=True)
    draw_text(f"Revenue Report – {month}")
    draw_text(f"Date: {date}")
    draw_text(f"Agreement Id: {agreement}")
    draw_separator()
    # Texto de detalles
    details_text = f"Details of the revenue generated for {owner} through the insertion of digital audio ads in its digital media, under the terms of the respective agreement."
    draw_wrapped_text(details_text)
    draw_separator()

    # Items
    for name, amt in items:
        amt_str = "${:,.2f}".format(amt)
        name_width = available_width - c.stringWidth(amt_str + " ", font_name, font_size)
        
        # Truncar nombre si es necesario
        while c.stringWidth(name, font_name, font_size) > name_width and len(name) > 0:
            name = name[:-4] + "..."
        
        # Calcular espacios necesarios
        text_width = c.stringWidth(name + amt_str, font_name, font_size)
        space_width = c.stringWidth(" ", font_name, font_size)
        num_spaces = int((available_width - text_width) / space_width)
        
        line = f"{name}{' ' * num_spaces}{amt_str}"
        draw_text(line)

    # Total
    draw_separator()
    total_str = f"${total:,.2f}"
    total_label = "TOTAL"
    text_width = c.stringWidth(total_label + total_str, font_name, font_size)
    space_width = c.stringWidth(" ", font_name, font_size)
    num_spaces = int((available_width - text_width) / space_width)
    draw_text(f"{total_label}{' ' * num_spaces}{total_str}", "Courier", 10, bold=True)
    draw_separator()
    
    draw_text("End of Report")

    c.showPage()
    c.save()
    buffer.seek(0)

    filename = f"Revenue_{month.replace(' ','_')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

