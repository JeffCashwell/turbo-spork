import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
import zipfile
import random
from datetime import date, timedelta, datetime

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
def get_random_date_last_year():
    """Returns a random date string (MM/DD/YYYY) from the previous calendar year."""
    current_year = datetime.now().year
    last_year = current_year - 1
    start_date = date(last_year, 1, 1)
    end_date = date(last_year, 12, 31)
    
    days_between = (end_date - start_date).days
    random_days = random.randrange(days_between + 1)
    random_date = start_date + timedelta(days=random_days)
    return random_date.strftime("%m/%d/%Y")

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
    """Generates a random dataframe of line items with Qty and Rate."""
    num_items = random.randint(1, 5)
    items = []
    for _ in range(num_items):
        item_name = random.choice(GENERIC_ITEMS)
        # Random amount between $100 and $5,000
        amount = round(random.uniform(100.00, 5000.00), 2)
        
        # Random Quantity (1 to 10)
        qty = random.randint(1, 10)
        
        # Calculate Rate
        rate = amount / qty
        
        items.append({
            'Item': item_name, 
            'Amount': amount,
            'Quantity': qty,
            'Item Rate': rate
        })
    return pd.DataFrame(items)

def generate_pdf_bytes(company_name, items_df, po_number=None):
    """Generates PDF and returns the binary data (RAM)."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # --- Header Information ---
    # Company Name
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2, height - 50, str(company_name))

    # Invoice Label
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 100, "INVOICE")
    
    # Generate Random Date
    invoice_date = get_random_date_last_year()
    c.drawRightString(width - 50, height - 100, f"Date: {invoice_date}")

    # PO or Invoice Number
    if po_number:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 120, f"PO #: {po_number}")
    else:
        c.setFont("Helvetica-Bold", 14)
        rand_inv = f"INV-{random.randint(10000, 99999)}"
        c.drawString(50, height - 120, f"Invoice #: {rand_inv}")

    # --- Table Header ---
    y_position = height - 170
    c.setFont("Helvetica-Bold", 10)
    
    # Column X-Positions
    col_desc = 50
    col_qty = 340
    col_rate = 400
    col_amt = width - 50 # Right aligned

    c.drawString(col_desc, y_position, "Item Description")
    c.drawString(col_qty, y_position, "Qty")
    c.drawString(col_rate, y_position, "Rate")
    c.drawRightString(col_amt, y_position, "Amount")
    
    c.line(50, y_position - 5, width - 50, y_position - 5)
    y_position -= 25

    # --- Line Items ---
    c.setFont("Helvetica", 10)
    total_amount = 0
    item_counter = 1

    for index, row in items_df.iterrows():
        # Parse Amount
        raw_amt = row.get('Amount', 0)
        amount = clean_currency(raw_amt) if isinstance(raw_amt, str) else float(raw_amt)
        
        # Parse Quantity
        raw_qty = row.get('Quantity', 1)
        # If blank or nan, default to 1
        try:
            qty = float(clean_currency(raw_qty)) if isinstance(raw_qty, str) else float(raw_qty)
            if qty == 0: qty = 1
        except:
            qty = 1

        # Parse Rate
        raw_rate = row.get('Item Rate', 0)
        # If CSV, rate might be string; if random, it's float
        try:
             rate = clean_currency(raw_rate) if isinstance(raw_rate, str) else float(raw_rate)
        except:
             rate = 0.0

        # Handle Item Name
        if 'Item' in row and pd.notna(row['Item']):
             if po_number: # CSV mode
                 display_name = f"Item {item_counter}"
             else: # Random Mode
                 display_name = str(row['Item'])
        else:
            display_name = f"Item {item_counter}"

        item_counter += 1
        total_amount += amount

        # Page Break Check
        if y_position < 50:
            c.showPage()
            y_position = height - 50

        # Draw Row
        c.drawString(col_desc, y_position, display_name)
        c.drawString(col_qty, y_position, f"{qty:,.0f}") # Display Qty as integer-like if possible
        c.drawString(col_rate, y_position, f"{rate:,.2f}")
        
        amount_str = f"({abs(amount):,.2f})" if amount < 0 else f"{amount:,.2f}"
        c.drawRightString(col_amt, y_position, amount_str)
        y_position -= 20

    # --- Total ---
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

# --- TOGGLE SWITCH ---
no_po_mode = st.toggle("Generate invoices without POs")

with st.expander("Show Instructions", expanded=True):
    if no_po_mode:
        st.markdown("""
        **Vendor-Only Mode Instructions:**
        1. Export a `.csv` file list of vendors by navigating to **Lists > Relationships > Vendors**. 
        2. Upload below.
        
        **Note:** If there are a lot of records in the .csv file it's advised to remove rows so that you are generating a handful of invoices at a time.
        """)
    else:
        st.markdown("""
        **Purchase Order Mode Instructions:**
        1. Create a Saved Search to find open Purchase Orders.
        2. Under Criteria set Type to 'is Purchase Order', set Status to 'is any of Purchase Order:Partially Received, Purchase Order:Pending Bill, etc.'
        3. Under Results set fields to **Name**, **Document Number**, **Item**, **Quantity**, **Item Rate**, **Amount**.
        4. Export the Saved Search to `.csv` and upload below.
        
        **Note:** If there are a lot of records in the `.csv` file it's advised to remove rows so that you are generating a handful of invoices at a time.
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
                        # Generate Random Items (Calculates Qty/Rate automatically)
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
            # Updated Required Columns
            required_columns = ['Name', 'Document Number', 'Amount', 'Item', 'Quantity', 'Item Rate']
            
            # Check for missing columns
            missing_cols = [col for col in required_columns if col not in df.columns]
            
            if missing_cols:
                st.error(f"CSV is missing columns: {', '.join(missing_cols)}")
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
                        
                        # Filter Header Rows (Item must not be empty)
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
