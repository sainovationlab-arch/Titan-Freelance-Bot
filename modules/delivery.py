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
    except Exception:
        return

    rows = worksheet.get_all_values()
    headers = rows[0]
    
    try:
        final_link_idx = headers.index('Final Work Link')
        payment_ver_idx = headers.index('Payment Verification')
        status_col_idx = headers.index('Status')
        email_col_idx = headers.index('Email')
        name_col_idx = headers.index('Client Name')
    except ValueError:
        print("Missing columns for delivery.")
        return

    gmail_service = get_gmail_service()

    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(final_link_idx, payment_ver_idx, status_col_idx):
            continue 

        final_link = row[final_link_idx]
        payment_ver = row[payment_ver_idx]
        status = row[status_col_idx]
        client_email = row[email_col_idx]
        client_name = row[name_col_idx]

        if final_link and payment_ver and status != "Delivered":
            # Ready to deliver
            subject = "Your Project is Ready!"
            body = f"Hi {client_name},\n\nWe have received payment and your work is ready.\n\nHere is the link: {final_link}\n\nThanks for your business!\n\nBest,\nTitan Bot"
            
            if send_email(gmail_service, client_email, subject, body):
                worksheet.update_cell(i, status_col_idx + 1, "Delivered")
                print(f"Delivered work to {client_email}")

if __name__ == "__main__":
    run_delivery()
