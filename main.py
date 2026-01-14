import time
import schedule
import os
from dotenv import load_dotenv
from modules.outreach import run_outreach
from modules.replier import run_replier
from modules.delivery import run_delivery
from modules.followup import run_followup

load_dotenv()

def job():
    print(f"Starting job cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    run_outreach()
    run_replier()
    run_delivery()
    run_followup()
    print("Job cycle complete.\n")

def main():
    print("Titan Freelance Bot Started.")
    
    # Schedule jobs
    # For testing, we can run immediately once
    job()
    
    # Schedule to run every hour
    schedule.every(1).hours.do(job)
    
    # Or specific times
    # schedule.every().day.at("09:00").do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
