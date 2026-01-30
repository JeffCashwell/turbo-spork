import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import zipfile

# --- CONFIGURATION ---
st.set_page_config(page_title="Invoice Generator", layout="centered")

# --- HELPER FUNCTIONS ---
def clean_currency(value):
    """Parses currency strings like '(40,000.00)' into floats."""
    if pd.isna(value):
        return 0.0
    s = str(value).strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    is_negative = False
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1].strip()
    s = s.replace(',', '').replace('$', '')
    try:
        val = float(s)
        return -val if is_negative else val
    except ValueError:
        return 0.0

def generate_pdf_bytes(po_number, company_name, items_df):
    """Generates PDF and returns the binary data (RAM) instead of saving to disk."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 50, str(company_name))

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 100, "INVOICE / PO REFERENCE")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 120, f"PO #: {po_number}")

    # Table Header
    y_position = height - 170
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y_position, "Item Description")
    c.drawRightString(width - 50, y_position, "Amount")
    c.line(50, y_position - 5, width - 50, y_position - 5)
    y_position -= 25

    # Line Items
    c.setFont("Helvetica", 12)
    total_amount = 0
    item_counter = 1

    for index, row in items_df.iterrows():
        amount = clean_currency(row['Amount'])
        display_name = f"Item {item_counter}"
        item_counter += 1
        total_amount += amount

        if y_position < 50:
            c.showPage()
            y_position = height - 50

        c.drawString(50, y_position, display_name)
        
        amount_str = f"({abs(amount):,.2f})" if amount < 0 else f"{amount:,.2f}"
        c.drawRightString(width - 50, y_position, amount_str)
        y_position -= 20

    # Total
    c.line(50, y_position + 10, width - 50, y_position + 10)
    y_position -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(width - 200, y_position, "Total:")
    total_str = f"({abs(total_amount):,.2f})" if total_amount < 0 else f"${total_amount:,.2f}"
    c.drawRightString(width - 50, y_position, total_str)

    c.save()
    buffer.seek(0)
    return buffer

# --- MAIN UI ---
st.title("Invoice Generator")
st.write("""
This app allows you to quickly create "fake" invoices associated to real vendors 
and purchase orders in your environment -- useful for testing and demo purposes.
""")

with st.expander("Show Instructions"):
    st.write("""
    1. Create a Saved Search to find open Purchase Orders.
    2. Under Criteria set Type to 'is Purchase Order', set Status to 'is any of Purchase Order:Partially Received, Purchase Order:Pending Bill, etc.'
    3. Under Results set fields to Name, Document Number, Item, Amount.
    4. Export the Saved Search to CSV and upload below.
    """)

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        # Read CSV
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()

        # Validate Columns
        required_columns = ['Name', 'Document Number', 'Amount', 'Item']
        if not all(col in df.columns for col in required_columns):
            st.error(f"CSV is missing columns: {', '.join([c for c in required_columns if c not in df.columns])}")
        else:
            # Process Data
            grouped = df.groupby('Document Number')
            
            # Prepare ZIP file in memory
            zip_buffer = io.BytesIO()
            count = 0

            with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                progress_bar = st.progress(0)
                total_groups = len(grouped)
                
                for i, (po_number, group) in enumerate(grouped):
                    # Find Company Name
                    valid_names = group['Name'].dropna()
                    company_name = valid_names.iloc[0] if not valid_names.empty else "Unknown Company"
                    
                    # Filter Header Rows
                    details = group[group['Item'].notna() & (group['Item'].astype(str).str.strip() != '')]
                    if details.empty: details = group

                    # Generate PDF Bytes
                    pdf_bytes = generate_pdf_bytes(po_number, company_name, details)
                    
                    # Add to ZIP
                    filename = f"Invoice_{str(po_number)}.pdf"
                    zip_file.writestr(filename, pdf_bytes.getvalue())
                    
                    count += 1
                    progress_bar.progress((i + 1) / total_groups)

            st.success(f"Generated {count} invoices!")

            # Download Button
            st.download_button(
                label="Download All Invoices (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="generated_invoices.zip",
                mime="application/zip"
            )

    except Exception as e:
        st.error(f"An error occurred: {e}")