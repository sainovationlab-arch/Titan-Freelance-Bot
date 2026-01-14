import datetime
import base64
from email.mime.text import MIMEText
from modules.services import get_gspread_client, get_gmail_service
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
    sheet_name = os.getenv('SHEET_NAME', 'Clients')
    try:
        sh = gc.open(sheet_name)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Error opening sheet {sheet_name}: {e}")
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
        name_col_idx = headers.index('Client Name')
        skill_col_idx = headers.index('Selected Skill')
        portfolio_col_idx = headers.index('Portfolio Link')
    except ValueError as e:
        print(f"Missing column in sheet: {e}")
        return

    gmail_service = get_gmail_service()

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
            
            subject = f"Proposal for {skill}"
            body = f"Hi {client_name},\n\nI noticed you might need help with {skill}. Check out my portfolio: {portfolio}.\n\nBest,\nTitan Bot"
            
            if send_email(gmail_service, client_email, subject, body):
                worksheet.update_cell(i, status_col_idx + 1, "Sent") 

if __name__ == "__main__":
    run_outreach()
