import time
import random
from datetime import datetime
import pytz
from modules.services import get_gspread_client, get_gmail_service
from modules.outreach import send_email

def run_followup():
    print("Running Universal Follow-up Bot (3-Day Rule)...")
    
    # Set Timezone to India (IST)
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist)
    
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
        date_col_idx = headers.index('Date') # Required for 3-Day Rule
    except ValueError as e:
        print(f"❌ Missing required columns: {e}")
        return

    gmail_service = get_gmail_service()
    
    # 2. Scan Rows
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(status_col_idx, date_col_idx): 
            continue

        status = row[status_col_idx].strip()
        client_email = row[email_col_idx].strip()
        client_name = row[name_col_idx].strip()
        date_str = row[date_col_idx].strip()

        # 3. Target Logic: 'Sent' Status + 3 Days Passed
        if status == "Sent":
            
            # Date Check
            try:
                sent_date = datetime.strptime(date_str, "%d/%m/%Y")
                # Make sent_date timezone aware if needed, or just compare dates
                # Using simple date difference
                days_passed = (today.date() - sent_date.date()).days
                
                print(f"📅 Checking {client_name}: Sent on {date_str} ({days_passed} days ago)")
                
                if days_passed < 3:
                    # Too early
                    continue
                    
            except ValueError:
                print(f"⚠️ Invalid Date for {client_name}: '{date_str}'. Skipping.")
                continue

            # If we reached here, it's been >= 3 days
            print(f"👀 Ready to Nudge: {client_name} ({client_email})")
            
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
