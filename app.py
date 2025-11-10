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

# --- Diccionario de contratos activos ---
CONTRACTS = {
    "3f36b96871a64b1387389c433dca29e4b7d6e8d2": "BIDGEAR JOINT STOCK COMPANY",
    "157fbb43f471431ca5abbc1082d59570610c6eb7": "ANA SOPHIA TAMAYO CORDERO",
    "PENDIENTE": "Suizo"
}

# --- Interfaz mejorada ---
INDEX_HTML = """
<!doctype html>
<html>
<head>
<title>AF STREAM - Revenue Report Generator</title>
<style>
    body { font-family: Arial, sans-serif; padding: 20px; max-width: 700px; margin: 0 auto; }
    h2 { color: #333; }
    label { display: block; margin-top: 15px; font-weight: bold; }
    input[type="text"], input[type="date"], select, textarea { 
        width: 100%; 
        padding: 8px; 
        margin-top: 5px; 
        box-sizing: border-box;
        font-family: monospace;
    }
    .inline-group { display: flex; gap: 10px; }
    .inline-group > div { flex: 1; }
    button { 
        margin-top: 20px; 
        padding: 12px 24px; 
        background: #007bff; 
        color: white; 
        border: none; 
        cursor: pointer; 
        font-size: 16px;
    }
    button:hover { background: #0056b3; }
    .footer { margin-top: 20px; font-size: 0.9em; color: #666; }
</style>
</head>
<body>
<h2>AF STREAM - Revenue Report Generator</h2>
<form method="post" action="/generate">
  
  <label>Mes y Año:</label>
  <div class="inline-group">
    <div>
      <select name="month_name" id="month_name" required>
        <option value="">Seleccionar mes</option>
        <option value="January">January</option>
        <option value="February">February</option>
        <option value="March">March</option>
        <option value="April">April</option>
        <option value="May">May</option>
        <option value="June">June</option>
        <option value="July">July</option>
        <option value="August">August</option>
        <option value="September">September</option>
        <option value="October">October</option>
        <option value="November">November</option>
        <option value="December">December</option>
      </select>
    </div>
    <div>
      <select name="year" id="year" required>
        <option value="">Año</option>
      </select>
    </div>
  </div>
  <input type="hidden" name="month" id="month_combined">
  
  <label>Fecha del reporte:</label>
  <input type="date" name="date_raw" id="date_raw" required>
  <input type="hidden" name="date" id="date_formatted">
  
  <label>Agreement Id:</label>
  <select name="agreement" id="agreement" required>
    <option value="">Seleccionar contrato</option>
    """ + "".join([f'<option value="{k}">{k[:20]}... - {v}</option>' for k, v in CONTRACTS.items()]) + """
  </select>
  
  <label>Dueño / Cliente:</label>
  <input type="text" name="owner" id="owner" readonly style="background: #f0f0f0;" required>
  
  <label>Radios (una por línea: radio, monto):</label>
  <textarea name="lines" rows="10" placeholder="mangabuddy.com, 1200" required></textarea>
  
  <button type="submit">Generar PDF</button>
</form>

<div class="footer">
  Protegido con usuario: <b>admin</b> (contraseña en variable REPORT_PASS)
</div>

<script>
// Generar años (últimos 5 y próximos 5)
const yearSelect = document.getElementById('year');
const currentYear = new Date().getFullYear();
for (let i = currentYear - 5; i <= currentYear + 5; i++) {
    const option = document.createElement('option');
    option.value = i;
    option.textContent = i;
    if (i === currentYear) option.selected = true;
    yearSelect.appendChild(option);
}

// Combinar mes y año antes de enviar
document.querySelector('form').addEventListener('submit', function(e) {
    const month = document.getElementById('month_name').value;
    const year = document.getElementById('year').value;
    document.getElementById('month_combined').value = month + ' ' + year;
    
    // Formatear fecha
    const dateRaw = document.getElementById('date_raw').value;
    if (dateRaw) {
        const date = new Date(dateRaw + 'T00:00:00');
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December'];
        const formatted = months[date.getMonth()] + ' ' + date.getDate() + ', ' + date.getFullYear();
        document.getElementById('date_formatted').value = formatted;
    }
});

// Auto-llenar Dueño/Cliente cuando se selecciona Agreement Id
const contracts = """ + str(CONTRACTS).replace("'", '"') + """;
document.getElementById('agreement').addEventListener('change', function() {
    const agreementId = this.value;
    document.getElementById('owner').value = contracts[agreementId] || '';
});
</script>
</body>
</html>
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
    draw_text(f"Revenue Report for the month of {month}")
    draw_text(f"Date: {date}")
    draw_text(f"Agreement Id: {agreement}")
    draw_separator()
    # Texto de detalles
    details_text = f"Details of the revenue generated for {owner} during the aforementioned month through the insertion of digital audio ads in its digital media, under the terms of the respective agreement."
    draw_wrapped_text(details_text)
    draw_separator()

    # Items
    for name, amt in items:
        amt_str = "${:,.2f} USD".format(amt)
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
    total_str = f"${total:,.2f} USD"
    total_label = "TOTAL"
    text_width = c.stringWidth(total_label + total_str, font_name, font_size)
    space_width = c.stringWidth(" ", font_name, font_size)
    num_spaces = int((available_width - text_width) / space_width)
    draw_text(f"{total_label}{' ' * num_spaces}{total_str}", "Courier", 10, bold=True)
    draw_separator()
    
    draw_text("End of Report")
    draw_text("")  # Espacio
    draw_text("")  # Espacio adicional
    
    # Instrucciones de facturación
    draw_text("Could you please send to billing@afstream.com the corresponding invoice?")
    draw_text("")  # Espacio
    draw_text("Billing information:", bold=True)
    draw_text("AF STREAM, LLC")
    draw_text("1549 NE 123rd St")
    draw_text("North Miami, FL 33161")
    draw_text("")  # Espacio
    draw_text("In the details of the Invoice, write the following:", bold=True)
    # Extraer mes y año del campo month
    month_parts = month.split()
    month_name = month_parts[0] if len(month_parts) > 0 else month
    year_value = month_parts[1] if len(month_parts) > 1 else ""
    draw_text(f"Audio ad revenue on our digital properties in {month_name} {year_value}")

    c.showPage()
    c.save()
    buffer.seek(0)

    #filename = f"Revenue_{month.replace(' ','_')}.pdf"
    filename = f"Revenue_{owner.replace(' ','_')}_{month.replace(' ','_')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))




