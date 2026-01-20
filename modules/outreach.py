import datetime
import base64
import time
import random
import re
import pytz
from email.mime.text import MIMEText
from modules.services import get_gspread_client, get_service_for_email
import os

MAX_EMAILS_PER_ACCOUNT_PER_RUN = 10

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
    try:
        local_part = email_address.split('@')[0]
        # Replace dots and digits with spaces
        clean_name = re.sub(r'[\.\d]', ' ', local_part)
        signature = clean_name.strip().title()
        signature = re.sub(r'\s+', ' ', signature)
        return signature
    except Exception:
        return "Titan Bot"

def send_outreach_emails():
    print("Running Outreach (Batch Mode)...")
    
    ist = pytz.timezone('Asia/Kolkata')
    today_str = datetime.datetime.now(ist).strftime("%d/%m/%Y")
    print(f"🤖 SYSTEM DATE (IST): {today_str}")

    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Error opening sheet {SHEET_ID}: {e}")
        return

    rows = worksheet.get_all_values()
    if not rows:
        print("No data found.")
        return

    headers = rows[0]
    try:
        date_col_idx = headers.index('Date')
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        gmail_col_idx = headers.index('Gmail Account')
        name_col_idx = headers.index('Client Name')
        skill_col_idx = headers.index('Selected Skill')
        first_price_col_idx = headers.index('First Price')
        offer_price_col_idx = headers.index('Offer Price')
        free_gift_col_idx = headers.index('Free Gift')
        portfolio_col_idx = headers.index('Portfolio Link')
    except ValueError as e:
        print(f"Missing column: {e}")
        return

    # Pass 1: Group Pending Tasks by Account
    pending_by_account = {} # {account_email: [row_index, ...]}
    
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= status_col_idx: continue
        
        # Validation
        if len(row) > name_col_idx and not row[name_col_idx].strip(): continue
        if len(row) > email_col_idx and not row[email_col_idx].strip(): continue
        
        date_val = str(row[date_col_idx]).strip()
        status_val = str(row[status_col_idx]).strip()
        
        if date_val == today_str and status_val == "":
            sender = row[gmail_col_idx].strip().lower() if len(row) > gmail_col_idx else ""
            if sender:
                if sender not in pending_by_account:
                    pending_by_account[sender] = []
                pending_by_account[sender].append(i)

    print(f"📊 Found pending tasks for {len(pending_by_account)} accounts.")

    # Pass 2: Process by Group
    for sender_account, row_indices in pending_by_account.items():
        print(f"\n🔄 Switching to account: {sender_account}")
        
        current_service = get_service_for_email(sender_account)
        if not current_service:
            print(f"⚠️ Token not found for {sender_account}. Skipping batch.")
            continue
            
        # Batch Limit
        batch_indices = row_indices[:MAX_EMAILS_PER_ACCOUNT_PER_RUN]
        print(f"   Processing {len(batch_indices)} emails (Limit: {MAX_EMAILS_PER_ACCOUNT_PER_RUN}).")
        
        sender_signature = get_sender_signature(sender_account)

        for i, row_idx in enumerate(batch_indices):
            row = rows[row_idx - 1]
            client_email = row[email_col_idx]
            client_name = row[name_col_idx]
            
            # Construct Content
            subject = f"Quick idea for {client_name}"
            body = f"""Hi {client_name},

I’ve been following {client_name} for a while and I genuinely love the work you are doing in the {row[skill_col_idx]} space. Your recent posts really caught my eye! 🔥

I noticed a small opportunity to help you stand out even more.

I am currently building a few premium case studies for my portfolio, and I’d love to include your brand.

Usually, for a project like this, I charge around {row[first_price_col_idx]}, but since I really want to add your logo to my portfolio, I can offer you a generic "Case Study" partner price of just {row[offer_price_col_idx]}.

This would include: ✅ Premium {row[skill_col_idx]} ✅ {row[free_gift_col_idx]} (My treat!) ✅ Unlimited Revisions

You can check my best work here: {row[portfolio_col_idx]}

No pressure at all—just thought it would be a great fit. Are you open to a quick 5-min chat to discuss?

Best regards, {sender_signature}"""

            print(f"   Sending ({i+1}/{len(batch_indices)}) to {client_email}...")
            if send_email(current_service, client_email, subject, body):
                worksheet.update_cell(row_idx, status_col_idx + 1, "Sent")
                
                # Rate Limit (45-90s)
                if i < len(batch_indices) - 1:
                    sleep_time = random.randint(45, 90)
                    print(f"      Sleeping for {sleep_time}s...")
                    time.sleep(sleep_time)
            
        print(f"   ✅ Finished batch for {sender_account}.")

if __name__ == "__main__":
    send_outreach_emails()
