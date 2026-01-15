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

def run_outreach():
    print("Running Outreach...")
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Error opening sheet {SHEET_ID}: {e}")
        return

    records = worksheet.get_all_records()
    # Assuming headers: 'Email Sending Date', 'Gmail Account', 'Client Name', 'Email', 'Selected Skill', 'Portfolio Link', 'Status'
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # We need to use row index to update, so let's iterate with enumeration or range
    # get_all_records returns list of dicts. 
    # To update, we might need the cell coordinates. 
    # A simple way for small sheets is iterating rows directly.
    
    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        date_col_idx = headers.index('Email Sending Date')
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        gmail_col_idx = headers.index('Gmail Account')
        name_col_idx = headers.index('Client Name')
        skill_col_idx = headers.index('Selected Skill')
        portfolio_col_idx = headers.index('Portfolio Link')
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

            subject = f"Proposal for {skill}"
            body = f"Hi {client_name},\n\nI noticed you might need help with {skill}. Check out my portfolio: {portfolio}.\n\nBest,\nTitan Bot"
            
            if send_email(current_service, client_email, subject, body):
                worksheet.update_cell(i, status_col_idx + 1, "Sent") 
                
                # Wait for random intervals
                wait_time = random.randint(180, 360)
                print(f"Waiting for {wait_time} seconds before next email...")
                time.sleep(wait_time) 

if __name__ == "__main__":
    run_outreach()
