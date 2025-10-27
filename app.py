from flask import Flask, render_template_string, request, send_file, Response
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from datetime import datetime
import os

app = Flask(__name__)

# --- Configuración de login simple ---
USERNAME = "admin"
PASSWORD = os.getenv("REPORT_PASS", "1234")

# --- HTML del formulario ---
HTML_FORM = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AF STREAM - Revenue Report</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #111; color: #eee; display: flex; justify-content: center; align-items: center; height: 100vh; }
        form { background: #1c1c1c; padding: 30px; border-radius: 12px; box-shadow: 0 0 10px rgba(255,255,255,0.1); width: 420px; }
        input, textarea { width: 100%; padding: 8px; margin: 6px 0; border-radius: 6px; border: none; font-size: 14px; }
        input[type="submit"] { background: #0078ff; color: white; cursor: pointer; font-weight: bold; }
        input[type="submit"]:hover { background: #005fcc; }
        label { font-weight: bold; color: #ccc; }
        h2 { text-align: center; color: #fff; }
    </style>
</head>
<body>
    <form method="POST" action="/generate">
        <h2>📄 Revenue Report</h2>
        <label>Owner Name:</label>
        <input type="text" name="owner" required>
        <label>Month and Year:</label>
        <input type="text" name="period" placeholder="e.g., September 2025" required>
        <label>Date of Report:</label>
        <input type="text" name="date" value="{{ today }}" required>
        <label>Agreement ID:</label>
        <input type="text" name="agreement" required>
        <label>Radio List and Amounts:</label>
        <textarea name="details" rows="8" placeholder="Example:\nradio1.com  $100.00\nradio2.com  $200.00" required></textarea>
        <input type="submit" value="Generate PDF">
    </form>
</body>
</html>
"""

# --- Página de login simple ---
LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login - AF STREAM Reports</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #111; color: #eee; display: flex; justify-content: center; align-items: center; height: 100vh; }
        form { background: #1c1c1c; padding: 30px; border-radius: 12px; box-shadow: 0 0 10px rgba(255,255,255,0.1); width: 320px; }
        input { width: 100%; padding: 8px; margin: 6px 0; border-radius: 6px; border: none; font-size: 14px; }
        input[type="submit"] { background: #0078ff; color: white; cursor: pointer; font-weight: bold; }
        input[type="submit"]:hover { background: #005fcc; }
        h2 { text-align: center; color: #fff; }
    </style>
</head>
<body>
    <form method="POST" action="/login">
        <h2>🔐 Login</h2>
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <input type="submit" value="Enter">
    </form>
</body>
</html>
"""

# --- Autenticación simple ---
@app.route("/", methods=["GET"])
def home():
    auth = request.authorization
    if not auth or not (auth.username == USERNAME and auth.password == PASSWORD):
        return Response('Login required', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
    today = datetime.now().strftime("%B %d, %Y")
    return render_template_string(HTML_FORM, today=today)

# --- Generar PDF ---
@app.route("/generate", methods=["POST"])
def generate_pdf():
    owner = request.form["owner"]
    period = request.form["period"]
    date = request.form["date"]
    agreement = request.form["agreement"]
    details = request.form["details"].strip()

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    # Configurar márgenes (5 cm en todos los lados)
    margin = 5 * cm
    width, height = letter
    usable_width = width - 2 * margin
    y = height - margin

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(width / 2, y, "AF STREAM, LLC")
    y -= 30

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(width / 2, y, f"Revenue Report – {period}")
    y -= 20

    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, y, f"Date: {date}")
    y -= 15
    pdf.drawString(margin, y, f"Agreement Id: {agreement}")
    y -= 25

    pdf.setFont("Helvetica", 10)
    text = pdf.beginText(margin, y)
    text.setLeading(15)
    text.textLines(
        f"Details of the revenue generated for {owner} through the insertion of digital audio ads "
        "in its digital media, where AF STREAM utilizes its advertising technology "
        "in accordance with the terms of the respective agreement.\n"
    )
    pdf.drawText(text)

    y = text.getY() - 20

    pdf.setFont("Courier", 10)
    pdf.drawString(margin, y, "-" * 80)
    y -= 15
    pdf.drawString(margin, y, f"{'Radio Station':<40}{'Total':>20}")
    y -= 10
    pdf.drawString(margin, y, "-" * 80)
    y -= 15

    lines = details.split("\n")
    for line in lines:
        pdf.drawString(margin, y, line)
        y -= 15

    pdf.drawString(margin, y, "-" * 80)
    y -= 15

    # Calcular total (solo si hay números)
    total = 0.0
    for line in lines:
        parts = line.split("$")
        if len(parts) > 1:
            try:
                total += float(parts[1].replace(",", "").strip())
            except ValueError:
                pass

    pdf.drawString(margin, y, f"{'TOTAL':<40}${total:,.2f}")
    y -= 15
    pdf.drawString(margin, y, "-" * 80)
    y -= 30

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawCentredString(width / 2, y, "End of Report")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name=f"Revenue_{period.replace(' ', '_')}.pdf", mimetype="application/pdf")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
