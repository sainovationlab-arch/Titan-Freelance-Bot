import os
from modules.outreach import send_email
from modules.services import get_gspread_client, get_gmail_service

def run_delivery():
    print("Running Delivery...")
    gc = get_gspread_client()
    SHEET_ID = '1N3_jJkYNCtp1MQXEObtDH9FC_VzPyL2RLBW_MdfvfCM'
    try:
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.sheet1
    except Exception as e:
        print(f"Error accessing sheet: {e}")
        return

    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        # Correct Column Names
        final_link_idx = headers.index('Final Drive Link') # Was Final Work Link
        payment_status_idx = headers.index('Payment Status') # Was Payment Verification
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        name_col_idx = headers.index('Client Name')
    except ValueError as e:
        print(f"Missing columns for delivery: {e}")
        return

    gmail_service = get_gmail_service()

    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(final_link_idx, payment_status_idx, status_col_idx):
            continue 

        final_link = row[final_link_idx]
        payment_status = row[payment_status_idx]
        status = row[status_col_idx]
        client_email = row[email_col_idx]
        client_name = row[name_col_idx]

        # Fix Logic: ONLY send if Status is exactly 'Done'
        if status == "Done" and final_link:
            # Professional Email Body
            subject = "Your Project is Ready! 🚀"
            body = (
                f"Hi {client_name},\n\n"
                f"We are happy to deliver your project! Here is the link: {final_link}.\n\n"
                "Please review it. If you need changes, just reply. If you like it, let us know so we can verify payment.\n\n"
                "By the way, we offer 20+ other skills like AI automation & Design. Let us know if you need anything else!\n\n"
                "Best regards,\n"
                "SA Innovation Lab"
            )
            
            print(f"Attempting to deliver to {client_name} ({client_email})...")
            if send_email(gmail_service, client_email, subject, body):
                worksheet.update_cell(i, status_col_idx + 1, "Delivered")
                print(f"✅ Delivered work to {client_email}")

if __name__ == "__main__":
    run_delivery()
