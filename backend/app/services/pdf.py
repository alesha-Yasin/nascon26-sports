"""PDF receipt generation using WeasyPrint."""
import base64
from io import BytesIO


def generate_receipt_pdf(order_id: str, total_minor: int, currency: str, items: list) -> str:
    """Generate a PDF receipt and return as base64 string."""
    try:
        from weasyprint import HTML
        total_major = total_minor / 100
        items_html = "".join(
            f"<tr><td>{item['variant_id']}</td><td>{item['quantity']}</td>"
            f"<td>{currency} {item['unit_price_minor']/100:.2f}</td></tr>"
            for item in items
        )
        html_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Receipt</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; }}
h1 {{ color: #333; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
.total {{ font-weight: bold; font-size: 1.2em; margin-top: 20px; }}
</style></head>
<body>
<h1>Receipt</h1>
<p><strong>Order ID:</strong> {order_id}</p>
<table>
<tr><th>Item</th><th>Qty</th><th>Price</th></tr>
{items_html}
</table>
<p class="total">Total: {currency} {total_major:.2f}</p>
</body></html>"""
        pdf_bytes = HTML(string=html_content).write_pdf()
        return base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception:
        # Fallback: minimal valid PDF
        pdf_content = (
            f"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            f"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            f"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
            f"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
            f"4 0 obj<</Length 80>>stream\nBT /F1 12 Tf 50 750 Td "
            f"(Order: {order_id} Total: {currency} {total_minor/100:.2f}) Tj ET\nendstream endobj\n"
            f"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            f"xref\n0 6\n0000000000 65535 f\ntrailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF"
        )
        return base64.b64encode(pdf_content.encode("latin-1")).decode("utf-8")
