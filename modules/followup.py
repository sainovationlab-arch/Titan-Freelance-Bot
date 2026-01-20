import time
import random
from datetime import datetime
import pytz
from modules.services import get_gspread_client, get_service_for_email
from modules.outreach import send_email

def run_followup():
    print("Running Universal Follow-up Bot (Multi-Account Safe)...")
    
    # Set Timezone to India (IST)
    ist = pytz.timezone('Asia/Kolkata')
    today = datetime.now(ist)
    today_date = today.date()
    
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
    if not rows:
        print("❌ Sheet is empty.")
        return

    headers = rows[0]

    try:
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        name_col_idx = headers.index('Client Name')
        date_col_idx = headers.index('Date')
        gmail_col_idx = headers.index('Gmail Account')
    except ValueError as e:
        print(f"❌ Missing required columns: {e}")
        return

    # 2. Identify Unique Accounts
    unique_accounts = set()
    for row in rows[1:]:
        if len(row) > gmail_col_idx:
            acc = row[gmail_col_idx].strip().lower()
            if acc:
                unique_accounts.add(acc)
    
    print(f"📋 Found {len(unique_accounts)} unique Gmail accounts for follow-ups.")

    # 3. Loop by Account
    for current_account in unique_accounts:
        print(f"\n🔄 Switching to account: {current_account}")
        
        # Login
        gmail_service = get_service_for_email(current_account)
        if not gmail_service:
            print(f"⚠️ Token not found for {current_account}. Skipping.")
            continue
            
        # Verify Identity (Safety Check)
        try:
             profile = gmail_service.users().getProfile(userId='me').execute()
             logged_in_email = profile.get('emailAddress').lower()
             if logged_in_email != current_account:
                 print(f"❌ Mismatch! Logged in as {logged_in_email}, but expected {current_account}. Skipping safely.")
                 continue
        except Exception as e:
            print(f"❌ Error verifying identity for {current_account}: {e}")
            continue

        # 4. Scan Rows for THIS Account
        for i, row in enumerate(rows[1:], start=2):
            # Basic validation
            if len(row) <= max(status_col_idx, date_col_idx, gmail_col_idx): 
                continue

            # STRICT ACCOUNT CHECK
            target_account = row[gmail_col_idx].strip().lower()
            if target_account != current_account:
                continue

            status = row[status_col_idx].strip()
            client_email = row[email_col_idx].strip()
            client_name = row[name_col_idx].strip()
            date_str = row[date_col_idx].strip()

            # 5. Target Logic: 'Sent' Status + 3 Days Passed
            if status == "Sent":
                
                # Date Check
                try:
                    sent_date = datetime.strptime(date_str, "%d/%m/%Y").date()
                    days_passed = (today_date - sent_date).days
                    
                    if days_passed < 3:
                        # Too early
                        continue
                        
                except ValueError:
                    print(f"⚠️ Invalid Date for {client_name}: '{date_str}'. Skipping.")
                    continue

                # If we reached here, it's been >= 3 days
                print(f"👀 Ready to Nudge: {client_name} ({client_email}) via {current_account}")
                
                # 6. Content (Signature based on account)
                # Simple signature logic or pull from helper if imported
                if "solanki" in current_account:
                    sender_sig = "Solanki Art"
                elif "royal" in current_account:
                    sender_sig = "Royal NXS" # Example fallback
                else:
                    sender_sig = "Titan Bot"

                subject = "Quick check-in regarding your project"
                body = (
                    f"Hi {client_name},\n\n"
                    "I just wanted to quickly bump this up in your inbox. Did you get a chance to review my previous email?\n\n"
                    "We are ready to start your design/automation work immediately.\n\n"
                    "Best regards,\n"
                    f"{sender_sig}"
                )

                # 7. Send & Update
                if send_email(gmail_service, client_email, subject, body):
                    worksheet.update_cell(i, status_col_idx + 1, "Followed Up")
                    print(f"✅ Nudge sent to {client_name}. Status updated to 'Followed Up'.")
                    
                    # Safety Sleep
                    time.sleep(random.randint(5, 15))

if __name__ == "__main__":
    run_followup()
