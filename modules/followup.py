import time
import random
from modules.services import get_gspread_client, get_gmail_service
from modules.outreach import send_email

def run_followup():
    print("Running Universal Follow-up Bot...")
    
    # 1. Connect to Sheet
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"❌ Error connecting to Sheet: {e}")
        return

    rows = worksheet.get_all_values()
    headers = rows[0]

    try:
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        name_col_idx = headers.index('Client Name')
        # We don't need Client Type anymore because we are treating everyone equally.
    except ValueError as e:
        print(f"❌ Missing required columns: {e}")
        return

    gmail_service = get_gmail_service()
    
    # 2. Scan Rows
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= status_col_idx: 
            continue

        status = row[status_col_idx].strip()
        client_email = row[email_col_idx].strip()
        client_name = row[name_col_idx].strip()

        # 3. Universal Target Logic
        # Send to ANYONE whose status is exactly 'Sent'
        if status == "Sent":
            
            print(f"👀 Found Unresponsive Lead: {client_name} ({client_email})")
            
            # 4. Content
            subject = "Quick check-in regarding your project"
            body = (
                f"Hi {client_name},\n\n"
                "I just wanted to quickly bump this up in your inbox. Did you get a chance to review my previous email?\n\n"
                "We are ready to start your design/automation work immediately.\n\n"
                "Best regards,\n"
                "SA Innovation Lab"
            )

            # 5. Send & Update
            if send_email(gmail_service, client_email, subject, body):
                worksheet.update_cell(i, status_col_idx + 1, "Followed Up")
                print(f"✅ Nudge sent to {client_name}. Status updated to 'Followed Up'.")
                
                # Safety Sleep
                time.sleep(random.randint(5, 15))

if __name__ == "__main__":
    run_followup()
