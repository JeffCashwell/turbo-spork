import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import zipfile
import random

# --- CONFIGURATION ---
st.set_page_config(page_title="Invoice Generator", layout="centered")

# --- CONSTANTS FOR RANDOM GENERATION ---
GENERIC_ITEMS = [
    "Professional Services", "Consulting Fees", "Software Subscription", 
    "Hardware Support", "Maintenance Agreement", "Installation Services", 
    "Training Session", "Office Supplies", "Shipping & Handling", 
    "Legal Services", "Marketing Services", "IT Support"
]

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

def sanitize_filename(text):
    """Removes illegal characters for safe filenames."""
    if not isinstance(text, str):
        text = str(text)
    clean = "".join([c for c in text if c.isalpha() or c.isdigit() or c in (' ', '-', '_')])
    return clean.strip()

def generate_random_data():
    """Generates a random dataframe of line items."""
    num_items = random.randint(1, 5)
    items = []
    for _ in range(num_items):
        item_name = random.choice(GENERIC_ITEMS)
        # Random amount between $100 and $5,000
        amount = round(random.uniform(100.00, 5000.00), 2)
        items.append({'Item': item_name, 'Amount': amount})
    return pd.DataFrame(items)

def generate_pdf_bytes(company_name, items_df, po_number=None):
    """Generates PDF and returns the binary data (RAM)."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 50, str(company_name))

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 100, "INVOICE")
    
    # Only draw PO Number if it exists
    if po_number:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 120, f"PO #: {po_number}")
    else:
        # If no PO, we generate a random Invoice Number for realism
        c.setFont("Helvetica-Bold", 14)
        rand_inv = f"INV-{random.randint(10000, 99999)}"
        c.drawString(50, height - 120, f"Invoice #: {rand_inv}")

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
        # Handle Amount (Clean it if coming from CSV, just float if random)
        raw_amt = row['Amount']
        if isinstance(raw_amt, str):
            amount = clean_currency(raw_amt)
        else:
            amount = float(raw_amt)

        # Handle Item Name (Use CSV value or Fallback to Counter)
        if 'Item' in row and pd.notna(row['Item']):
             # If using random generator, use the name generated. 
             # If using CSV, use "Item 1, Item 2" convention
             if po_number: # Logic for CSV mode
                 display_name = f"Item {item_counter}"
             else: # Logic for Random Mode
                 display_name = str(row['Item'])
        else:
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
(and optionally, purchase orders) in the environment — useful for testing and demo purposes when acquiring invoices to test is not possible or limited.
""")

# Toggle for "No PO" mode
no_po_mode = st.checkbox("Generate invoices without POs")

with st.expander("Show Instructions", expanded=True):
    if no_po_mode:
        st.markdown("""
        **Vendor-Only Mode Instructions:**
        1. Export a `.xls` file list of vendors by navigating to **Lists > Relationships > Vendors**. 
        2. Ensure the `.xls` contains the **"Name"** field (header case-sensitive).
        3. Before uploading, convert the `.xls` file to `.csv`.
        4. Upload below.
        
        **Note:** If there are a lot of records in the .csv file it's advised to remove rows so that you are generating a handful of invoices at a time.
        """)
    else:
        st.markdown("""
        **Purchase Order Mode Instructions:**
        1. Create a Saved Search to find open Purchase Orders.
        2. Under Criteria set Type to 'is Purchase Order', set Status to 'is any of Purchase Order:Partially Received, Purchase Order:Pending Bill, etc.'
        3. Under Results set fields to **Name**, **Document Number**, **Item**, **Amount**.
        4. Export the Saved Search to CSV and upload below.
        
        **Note:** If there are a lot of records in the .csv file it's advised to remove rows so that you are generating a handful of invoices at a time.
        """)

uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file is not None:
    try:
        # Read CSV
        df = pd.read_csv(uploaded_file)
        df.columns = df.columns.str.strip()

        # --- LOGIC BRANCHING ---
        
        if no_po_mode:
            # === RANDOM MODE (NO PO) ===
            if 'Name' not in df.columns:
                st.error("CSV is missing the 'Name' column.")
            else:
                # Get unique names
                unique_vendors = df['Name'].dropna().unique()
                
                zip_buffer = io.BytesIO()
                count = 0
                
                with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                    progress_bar = st.progress(0)
                    total = len(unique_vendors)

                    for i, vendor_name in enumerate(unique_vendors):
                        # Generate Random Items
                        random_items_df = generate_random_data()
                        
                        # Generate PDF (No PO Number passed)
                        pdf_bytes = generate_pdf_bytes(vendor_name, random_items_df, po_number=None)
                        
                        # Filename: Name_Random.pdf
                        clean_name = sanitize_filename(vendor_name)
                        filename = f"{clean_name}_Invoice.pdf"
                        
                        zip_file.writestr(filename, pdf_bytes.getvalue())
                        count += 1
                        progress_bar.progress((i + 1) / total)
                
                st.success(f"Generated {count} random vendor invoices!")
                st.download_button("Download All (ZIP)", zip_buffer.getvalue(), "vendor_invoices.zip", "application/zip")

        else:
            # === STANDARD MODE (WITH PO) ===
            required_columns = ['Name', 'Document Number', 'Amount', 'Item']
            if not all(col in df.columns for col in required_columns):
                st.error(f"CSV is missing columns: {', '.join([c for c in required_columns if c not in df.columns])}")
            else:
                grouped = df.groupby('Document Number')
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

                        # Generate PDF
                        pdf_bytes = generate_pdf_bytes(company_name, details, po_number=po_number)
                        
                        # Filename
                        clean_name = sanitize_filename(company_name)
                        clean_po = sanitize_filename(po_number)
                        if not clean_name: clean_name = "Invoice"
                        filename = f"{clean_name}_{clean_po}.pdf"
                        
                        zip_file.writestr(filename, pdf_bytes.getvalue())
                        count += 1
                        progress_bar.progress((i + 1) / total_groups)

                st.success(f"Generated {count} PO invoices!")
                st.download_button("Download All (ZIP)", zip_buffer.getvalue(), "po_invoices.zip", "application/zip")

    except Exception as e:
        st.error(f"An error occurred: {e}")



