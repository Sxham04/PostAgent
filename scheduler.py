import csv
from datetime import datetime
from pathlib import Path
import time
import schedule

from config import BASE_DIR
from main import process_pending_videos

LOG_FILE = BASE_DIR / "post_history.csv"

# The 4 daily time slots (24-hour format)
TIME_SLOTS = ["09:00", "13:00", "18:00", "22:00"]


def log_scheduled_run():
    """Logs the execution timestamp and day of week to track slot analytics."""
    file_exists = LOG_FILE.exists()
    now = datetime.now()

    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "day_of_week", "time_slot", "status"])

        writer.writerow(
            [
                now.strftime("%Y-%m-%d %H:%M:%S"),
                now.strftime("%A"),
                now.strftime("%H:%M"),
                "Triggered",
            ]
        )


def scheduled_upload_job():
    """Triggered automatically at each defined time slot."""
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{current_time}] Scheduled trigger fired. Initiating upload...")
    log_scheduled_run()

    # Processes exactly one video from pending and moves it to published
    process_pending_videos()


def run_scheduler():
    # Register the 4 time slots
    for slot in TIME_SLOTS:
        schedule.every().day.at(slot).do(scheduled_upload_job)
        print(f"Registered daily upload slot at: {slot}")

    print("\nScheduler is actively running. Press Ctrl+C to stop.")

    # Keep script alive and evaluate pending triggers every 30 seconds
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    run_scheduler()