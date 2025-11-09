from io import BytesIO
from flask import Flask, request, render_template_string, send_file, Response
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from functools import wraps

app = Flask(__name__)

# --- Autenticación básica ---
def check_auth(username, password):
    return username == 'admin' and password == os.getenv('PAYMENT_PASS', '')

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

# --- Datos de clientes/beneficiarios ---
BENEFICIARIES = {
    "1f9730e1c32a48aba7284dc8e5496cc7f373b2be": {
        "company_name": "BIDGEAR JOINT STOCK COMPANY",
        "address_line1": "Tầng 3, Số 1, lô 10A, Khu đô thị mới Trung Yên,",
        "address_line2": "Phường Trung Hòa, Quận Cầu Giấy,",
        "address_line3": "Thành phố Hà Nội, Việt Nam",
        "phone": "+84 96 399 84 15",
        "email": "liam.nguyen@bidgear.com",
        "website": "www.bidgear.com",
        "beneficiary_name": "Tung Nguyen Huu",
        "account_type": "Checking",
        "bank_name": "First Century Bank",
        "bank_address": "1731 N Elm St, Commerce, GA 30529, USA",
        "routing_number": "061120084",
        "account_number": "4030000434322"
    },
    "DEC022022": {
        "company_name": "ANA SOPHIA TAMAYO CORDERO",
        "address_line1": "Colambo y Limoncillo 781-31",
        "address_line2": "Loja, Ecuador",
        "address_line3": "",
        "phone": "+593 99 405 3325",
        "email": "ana.tamayo@unl.edu.ec",
        "website": "",
        "beneficiary_name": "Ana Sophia Tamayo Cordero",
        "account_type": "Savings",
        "bank_name": "Banco [Pendiente]",
        "bank_address": "[Pendiente]",
        "routing_number": "[Pendiente]",
        "account_number": "[Pendiente]"
    }
}

# --- Interfaz del formulario ---
INDEX_HTML = """
<!doctype html>
<html>
<head>
<title>AF STREAM - Payment Remittance Generator</title>
<style>
    body { font-family: Arial, sans-serif; padding: 20px; max-width: 700px; margin: 0 auto; }
    h2 { color: #333; }
    label { display: block; margin-top: 15px; font-weight: bold; }
    input[type="text"], input[type="date"], input[type="number"], select { 
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
        background: #28a745; 
        color: white; 
        border: none; 
        cursor: pointer; 
        font-size: 16px;
    }
    button:hover { background: #218838; }
    .footer { margin-top: 20px; font-size: 0.9em; color: #666; }
    .readonly { background: #f0f0f0; }
</style>
</head>
<body>
<h2>AF STREAM - Payment Remittance Generator</h2>
<form method="post" action="/generate">
  
  <label>Agreement ID:</label>
  <select name="agreement" id="agreement" required>
    <option value="">Select Agreement</option>
    """ + "".join([f'<option value="{k}">{k[:25]}... - {v["company_name"]}</option>' for k, v in BENEFICIARIES.items()]) + """
  </select>
  
  <label>Performance Period (Month and Year):</label>
  <div class="inline-group">
    <div>
      <select name="month_name" id="month_name" required>
        <option value="">Select month</option>
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
        <option value="">Year</option>
      </select>
    </div>
  </div>
  <input type="hidden" name="performance_period" id="performance_period">
  
  <label>Document Reference (Invoice No.):</label>
  <input type="text" name="invoice_no" placeholder="0000091" required>
  
  <label>Payment Date:</label>
  <input type="date" name="payment_date_raw" id="payment_date_raw" required>
  <input type="hidden" name="payment_date" id="payment_date_formatted">
  
  <label>Payment Amount (USD):</label>
  <input type="number" name="payment_amount" step="0.01" min="0" placeholder="7500.00" required>
  
  <label>Payment Reference Number:</label>
  <input type="text" name="payment_ref" placeholder="849203458" required>
  
  <label>Beneficiary Information (auto-filled):</label>
  <input type="text" id="beneficiary_preview" class="readonly" readonly placeholder="Select Agreement ID first...">
  
  <button type="submit">Generate Payment Advice PDF</button>
</form>

<div class="footer">
  Protected with user: <b>admin</b> (password in PAYMENT_PASS variable)
</div>

<script>
// Generar años
const yearSelect = document.getElementById('year');
const currentYear = new Date().getFullYear();
for (let i = currentYear - 5; i <= currentYear + 5; i++) {
    const option = document.createElement('option');
    option.value = i;
    option.textContent = i;
    if (i === currentYear) option.selected = true;
    yearSelect.appendChild(option);
}

// Combinar mes y año
document.querySelector('form').addEventListener('submit', function(e) {
    const month = document.getElementById('month_name').value;
    const year = document.getElementById('year').value;
    document.getElementById('performance_period').value = month + ' ' + year;
    
    // Formatear fecha
    const dateRaw = document.getElementById('payment_date_raw').value;
    if (dateRaw) {
        const date = new Date(dateRaw + 'T00:00:00');
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December'];
        const formatted = months[date.getMonth()] + ' ' + date.getDate() + ', ' + date.getFullYear();
        document.getElementById('payment_date_formatted').value = formatted;
    }
});

// Auto-preview beneficiario
const beneficiaries = """ + str(BENEFICIARIES).replace("'", '"') + """;
document.getElementById('agreement').addEventListener('change', function() {
    const agreementId = this.value;
    const beneficiary = beneficiaries[agreementId];
    if (beneficiary) {
        document.getElementById('beneficiary_preview').value = 
            beneficiary.company_name + ' - ' + beneficiary.beneficiary_name;
    } else {
        document.getElementById('beneficiary_preview').value = '';
    }
});
</script>
</body>
</html>
"""

@app.route("/")
@requires_auth
def index():
    return render_template_string(INDEX_HTML)

@app.route("/health")
def health():
    """Health check endpoint for Render"""
    return {"status": "healthy"}, 200

@app.route("/generate", methods=["POST"])
@requires_auth
def generate():
    agreement = request.form.get("agreement", "").strip()
    performance_period = request.form.get("performance_period", "").strip()
    invoice_no = request.form.get("invoice_no", "").strip()
    payment_date = request.form.get("payment_date", "").strip()
    payment_amount = request.form.get("payment_amount", "").strip()
    payment_ref = request.form.get("payment_ref", "").strip()
    
    # Obtener datos del beneficiario
    beneficiary = BENEFICIARIES.get(agreement, {})
    if not beneficiary:
        return "Agreement ID not found", 400
    
    # Registrar fuente monoespaciada con soporte Unicode
    try:
        font_dir = os.path.join(os.path.dirname(__file__), 'fonts')
        pdfmetrics.registerFont(TTFont('SourceCodePro', os.path.join(font_dir, 'SourceCodePro-Regular.ttf')))
        pdfmetrics.registerFont(TTFont('SourceCodePro-Bold', os.path.join(font_dir, 'SourceCodePro-Bold.ttf')))
        font_name = "SourceCodePro"
    except Exception as e:
        # Fallback a Courier si la fuente no está disponible
        print(f"Warning: Could not load SourceCodePro font: {e}")
        font_name = "Courier"
    
    # Crear PDF
    buffer = BytesIO()
    page_width, page_height = letter
    margin = 3 * cm
    
    c = canvas.Canvas(buffer, pagesize=letter)
    x = margin
    y = page_height - margin
    
    font_size = 10
    line_height = 14
    
    def draw_text(text, font=None, size=10, bold=False):
        nonlocal y
        if font is None:
            font = font_name
        if bold:
            if font_name == "SourceCodePro":
                c.setFont("SourceCodePro-Bold", size)
            else:
                c.setFont(f"{font}-Bold", size)
        else:
            c.setFont(font, size)
        c.drawString(x, y, text)
        y -= line_height
    
    # Título
    draw_text("PAYMENT REMITTANCE ADVICE", None, 12, bold=True)
    draw_text(f"Performance Period: {performance_period}")
    draw_text("")  # Espacio
    
    # From
    draw_text("From:", bold=True)
    draw_text("AF STREAM, LLC")
    draw_text("1549 NE 123rd St")
    draw_text("North Miami, FL 33161")
    draw_text("United States")
    draw_text("Phone: +1 407 610-0090")
    draw_text("Email: billing@afstream.com")
    draw_text("Website: www.afstream.com")
    draw_text("")  # Espacio
    
    # To
    draw_text("To:", bold=True)
    draw_text(beneficiary["company_name"])
    draw_text(beneficiary["address_line1"])
    draw_text(beneficiary["address_line2"])
    if beneficiary["address_line3"]:
        draw_text(beneficiary["address_line3"])
    draw_text(f"Phone: {beneficiary['phone']}")
    draw_text(f"Email: {beneficiary['email']}")
    draw_text(f"Website: {beneficiary['website']}")
    draw_text("")  # Espacio
    
    # Description
    draw_text("DESCRIPTION:", bold=True)
    draw_text(f"Net payment for audio ads delivered on {beneficiary['company_name']}'s digital")
    draw_text("properties using AF Stream's ad delivery infrastructure.")
    draw_text("")  # Espacio
    
    # Amount
    draw_text("AMOUNT PAYABLE:", bold=True)
    draw_text(f"$ {float(payment_amount):,.2f}")
    draw_text("")  # Espacio
    
    # Payment Details
    draw_text("PAYMENT DETAILS", bold=True)
    draw_text(f"Document Reference: Invoice No. {invoice_no}")
    draw_text(f"Payment Date: {payment_date}")
    draw_text("Payment Currency: USD")
    draw_text(f"Payment Amount: {float(payment_amount):,.2f}")
    draw_text(f"Payment Reference Number: {payment_ref}")
    draw_text(f"Beneficiary Name: {beneficiary['beneficiary_name']}")
    draw_text(f"Account Type: {beneficiary['account_type']}")
    draw_text(f"Bank Name: {beneficiary['bank_name']}")
    draw_text(f"Bank Address: {beneficiary['bank_address']}")
    draw_text(f"Routing Number: {beneficiary['routing_number']}")
    draw_text(f"Account Number: {beneficiary['account_number']}")
    draw_text("")  # Espacio
    
    # Agreement ID
    draw_text("Agreement ID:")
    draw_text(agreement)
    draw_text("")  # Espacio
    
    draw_text("End of Payment Advice")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    
    filename = f"Payment_Remittance_{performance_period.replace(' ', '_')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
