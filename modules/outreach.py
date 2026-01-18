import datetime
import base64
import time
import random
import re
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
    # Get today's date in YYYY-MM-DD format
    today = datetime.date.today().strftime("%Y-%m-%d")

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

    for i, row in enumerate(rows[1:], start=2): # 1-based index, skip header
        if len(row) <= status_col_idx:
            # Row might be short, pad it
            row.extend([''] * (status_col_idx - len(row) + 1))
            
        date_val = row[date_col_idx]
        status_val = row[status_col_idx]
        
        # Check date format match (assuming YYYY-MM-DD or simple string match)
        if date_val == today and not status_val:
            # Extract Data
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
                print(f"Row {i}: Missing Gmail Account")
                continue

            if not sender_email:
                print(f"Row {i}: Empty Gmail Account cell")
                continue

            print(f"Processing row {i}: Sending from {sender_email} to {client_email}")
            
            current_service = get_service_for_email(sender_email)
            if not current_service:
                print(f"Skipping row {i}: Could not authenticate for {sender_email}")
                continue

            # Generate Signature
            sender_signature = get_sender_signature(sender_email)

            # Construct Email Content
            subject = f"Quick collab for {skill}?"
            
            body = f"""Hi {client_name},

I was looking at your work and I love what you are doing.

Usually, I charge {first_price} for {skill}, but I want to build more case studies in your niche. So, I can do this for you for just {offer_price}.

As a bonus, I will include {free_gift} for free.

Here is my latest work: {portfolio}

Are you open to a quick 5-min chat?

Best Regards, {sender_signature}"""

            if send_email(current_service, client_email, subject, body):
                worksheet.update_cell(i, status_col_idx + 1, "Sent") 
                
                # Wait for random intervals
                wait_time = random.randint(180, 360)
                print(f"Waiting for {wait_time} seconds before next email...")
                time.sleep(wait_time) 

if __name__ == "__main__":
    send_outreach_emails()
