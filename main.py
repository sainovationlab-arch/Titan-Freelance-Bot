import sys
from modules.outreach import send_outreach_emails
from modules.replier import process_replies

print('🟢 BOT STARTING: One-Time Execution Mode')

try:
    print('--- Step 1: Outreach ---')
    send_outreach_emails()
    print('✅ Outreach Finished')
except Exception as e:
    print(f'❌ Outreach Error: {e}')

try:
    print('--- Step 2: Follow-up Bot ---')
    from modules.followup import run_followup
    run_followup()
    print('✅ Follow-up Finished')
except Exception as e:
    print(f'❌ Follow-up Error: {e}')

try:
    print('--- Step 2: Replier ---')
    process_replies()
    print('✅ Replier Finished')
except Exception as e:
    print(f'❌ Replier Error: {e}')

print('🔴 ALL TASKS DONE. EXITING.')
sys.exit(0)
