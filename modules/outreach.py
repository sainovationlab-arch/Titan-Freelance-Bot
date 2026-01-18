import datetime
import base64
import time
import random
import re
import pytz
from email.mime.text import MIMEText
from modules.services import get_gspread_client, get_gmail_service, get_service_for_email
import os

def send_email(service, to, subject, body):
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw}
    try:
        service.users().messages().send(userId='me', body=body).execute()
        print(f"Email sent to {to}")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

def get_sender_signature(email_address):
    """
    Generates a signature from the email address.
    Logic: Take the part before '@', replace dots/numbers with spaces, and Capitalize it.
    """
    try:
        local_part = email_address.split('@')[0]
        # Replace dots and digits with spaces
        clean_name = re.sub(r'[\.\d]', ' ', local_part)
        # Strip extra whitespace and title case
        signature = clean_name.strip().title()
        # Collapse multiple spaces
        signature = re.sub(r'\s+', ' ', signature)
        return signature
    except Exception:
        return "Titan Bot"

def send_outreach_emails():
    print("Running Outreach...")
    
    # Set Timezone to India (IST)
    ist = pytz.timezone('Asia/Kolkata')
    today_str = datetime.datetime.now(ist).strftime("%d/%m/%Y")
    print(f"🤖 SYSTEM DATE (IST): {today_str}")

    # Authenticate with Google Sheets
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Error opening sheet {SHEET_ID}: {e}")
        return

    # Get all records from the worksheet
    rows = worksheet.get_all_values()
    if not rows:
        print("No data found in the worksheet.")
        return

    print(f"📊 Total Rows in Sheet: {len(rows)}")

    headers = rows[0]
    try:
        # Required Columns
        date_col_idx = headers.index('Date')
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        gmail_col_idx = headers.index('Gmail Account')
        
        # Dynamic Data Columns
        name_col_idx = headers.index('Client Name')
        skill_col_idx = headers.index('Selected Skill')
        first_price_col_idx = headers.index('First Price')
        offer_price_col_idx = headers.index('Offer Price')
        free_gift_col_idx = headers.index('Free Gift')
        portfolio_col_idx = headers.index('Portfolio Link')

    except ValueError as e:
        print(f"Missing column in sheet: {e}")
        return

    consecutive_empty = 0
    pending_tasks = []

    # Pass 1: Identify Valid Rows
    for i, row in enumerate(rows[1:], start=2): # 1-based index, skip header
        if len(row) <= status_col_idx:
            # Row might be short, pad it
            row.extend([''] * (status_col_idx - len(row) + 1))
            
        # Empty Row Breaker Logic
        row_name = row[name_col_idx].strip() if len(row) > name_col_idx else ""
        row_email = row[email_col_idx].strip() if len(row) > email_col_idx else ""

        if not row_name or not row_email:
            consecutive_empty += 1
            if consecutive_empty > 5:
                print("⛔ Found 5 consecutive empty rows. Stopping scan.")
                break
            continue # Skip this empty row but don't break yet
        else:
            consecutive_empty = 0
            
        date_val = str(row[date_col_idx]).strip()
        status_val = str(row[status_col_idx]).strip()
        
        # Check date format match (assuming YYYY-MM-DD or simple string match)
        if date_val == today_str and status_val == "":
            pending_tasks.append(i)
        else:
             print(f" ❌ SKIP Row {i}: Date '{date_val}' != '{today_str}' or Status '{status_val}' not empty.")

    print(f"✅ Found {len(pending_tasks)} pending emails to send.")

    # Pass 2: Process Pending Tasks
    for idx_in_list, row_idx in enumerate(pending_tasks):
        # row_idx is 1-based index (Header is 1). So rows[...] index is row_idx - 1
        # because rows[0] is Header (row 1).
        # Wait: enumerate(rows[1:], start=2).
        # i=2 corresponds to rows[1] (which is the first data row).
        # So array_index = row_idx - 1.
        
        array_index = row_idx - 1
        row = rows[array_index]
        
        client_name = row[name_col_idx]
        client_email = row[email_col_idx]
        skill = row[skill_col_idx]
        first_price = row[first_price_col_idx]
        offer_price = row[offer_price_col_idx]
        free_gift = row[free_gift_col_idx]
        portfolio = row[portfolio_col_idx]
        
        # Dynamic Sender Selection
        try:
            sender_email = row[gmail_col_idx]
        except IndexError:
            print(f"Row {row_idx}: Missing Gmail Account")
            continue

        if not sender_email:
            print(f"Row {row_idx}: Empty Gmail Account cell")
            continue

        print(f"Processing row {row_idx}: Sending from {sender_email} to {client_email}")
        
        current_service = get_service_for_email(sender_email)
        if not current_service:
            print(f"Skipping row {row_idx}: Could not authenticate for {sender_email}")
            continue

        # Generate Signature
        sender_signature = get_sender_signature(sender_email)

        # Construct Email Content
        subject = f"Quick idea for {client_name}"
        
        body = f"""Hi {client_name},

I’ve been following {client_name} for a while and I genuinely love the work you are doing in the {skill} space. Your recent posts really caught my eye! 🔥

I noticed a small opportunity to help you stand out even more.

I am currently building a few premium case studies for my portfolio, and I’d love to include your brand.

Usually, for a project like this, I charge around {first_price}, but since I really want to add your logo to my portfolio, I can offer you a generic "Case Study" partner price of just {offer_price}.

This would include: ✅ Premium {skill} ✅ {free_gift} (My treat!) ✅ Unlimited Revisions

You can check my best work here: {portfolio}

No pressure at all—just thought it would be a great fit. Are you open to a quick 5-min chat to discuss?

Best regards, {sender_signature}"""

        if send_email(current_service, client_email, subject, body):
            worksheet.update_cell(row_idx, status_col_idx + 1, "Sent") 
            
            # --- Smart Sleep Logic ---
            if idx_in_list < len(pending_tasks) - 1:
                wait_time = random.randint(10, 30)
                print(f"Waiting for {wait_time} seconds before next email...")
                time.sleep(wait_time)
            else:
                 print("🚀 Last email sent. Skipping safety delay.") 

if __name__ == "__main__":
    send_outreach_emails()
