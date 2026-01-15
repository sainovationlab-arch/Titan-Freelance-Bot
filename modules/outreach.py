import datetime
import base64
import time
import random
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
        date_col_idx = headers.index('Date')
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        gmail_col_idx = headers.index('Gmail Account')
        name_col_idx = headers.index('Client Name')
        skill_col_idx = headers.index('Selected Skill')
        portfolio_col_idx = headers.index('Portfolio Link')
        
        # Optional columns for dynamic content
        try:
            subject_col_idx = headers.index('Email Subject')
            body_col_idx = headers.index('Email Body')
        except ValueError:
            subject_col_idx = -1
            body_col_idx = -1
            
    except ValueError as e:
        print(f"Missing column in sheet: {e}")
        return

    # Removed global gmail_service initialization
    # gmail_service = get_gmail_service()

    for i, row in enumerate(rows[1:], start=2): # 1-based index, skip header
        if len(row) <= status_col_idx:
            # Row might be short, pad it
            row.extend([''] * (status_col_idx - len(row) + 1))
            
        date_val = row[date_col_idx]
        status_val = row[status_col_idx]
        
        # Check date format match (assuming YYYY-MM-DD or simple string match)
        if date_val == today and not status_val:
            client_name = row[name_col_idx]
            client_email = row[email_col_idx]
            skill = row[skill_col_idx]
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

            # Dynamic Content Logic
            subject_template = ""
            body_template = ""
            
            if subject_col_idx != -1 and len(row) > subject_col_idx:
                subject_template = row[subject_col_idx]
            
            if body_col_idx != -1 and len(row) > body_col_idx:
                body_template = row[body_col_idx]
                
            # Default Templates
            if not subject_template:
                subject_template = f"Proposal for {skill}"
            
            if not body_template:
                body_template = f"Hi {{Name}},\n\nI noticed you might need help with {{Skill}}. Check out my portfolio: {{Portfolio}}.\n\nBest,\nTitan Bot"

            # Placeholder Replacement
            # Placeholders: {{Name}}, {{Skill}}, {{Portfolio}}
            replacements = {
                "{{Name}}": client_name,
                "{{Skill}}": skill,
                "{{Portfolio}}": portfolio
            }
            
            subject = subject_template
            body = body_template
            
            for key, val in replacements.items():
                subject = subject.replace(key, val)
                body = body.replace(key, val)
            
            if send_email(current_service, client_email, subject, body):
                worksheet.update_cell(i, status_col_idx + 1, "Sent") 
                
                # Wait for random intervals
                wait_time = random.randint(180, 360)
                print(f"Waiting for {wait_time} seconds before next email...")
                time.sleep(wait_time) 

if __name__ == "__main__":
    send_outreach_emails()
