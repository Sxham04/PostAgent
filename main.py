from datetime import datetime
import shutil
import time
from apscheduler.schedulers.background import BackgroundScheduler
from config import PENDING_DIR, PUBLISHED_DIR
from database import (
    add_video,
    get_next_pending_video,
    initialize_database,
    mark_video_published,
)
from optimizer import get_optimal_upload_slot, sync_published_video_metrics
from uploader import upload_instagram_reel, upload_youtube_short

# Ingestion and Publishing Routines

def scan_and_register_pending_videos():
    """Find new MP4 files in the pending folder and add them to the database."""
    video_extensions = {".mp4", ".mov", ".mkv"}
    for file_path in PENDING_DIR.iterdir():
        if file_path.suffix.lower() in video_extensions:
            # Generate default title from filename
            clean_title = file_path.stem.replace("_", " ").title()
            add_video(
                file_name=file_path.name,
                title=clean_title,
                description=f"Watch this clip: {clean_title}",
            )


def publish_next_video():
    """Publish the next video in the queue to YouTube and Instagram."""
    video = get_next_pending_video()
    if not video:
        print("[Dispatcher] No pending videos found in queue.")
        return

    file_name = video["file_name"]
    source_path = PENDING_DIR / file_name

    if not source_path.exists():
        print(f"[Dispatcher] Error: File {source_path} does not exist on disk.")
        return

    print(f"[Dispatcher] Starting publish process for: {file_name}")

    yt_id = None
    ig_id = None

    # Step 1: Upload to YouTube Shorts
    try:
        yt_id = upload_youtube_short(
            video_path=source_path,
            title=video["title"],
            description=video["description"],
        )
        print(f"[Dispatcher] YouTube Short published. ID: {yt_id}")
    except Exception as e:
        print(f"[Dispatcher] YouTube upload failed: {e}")

    # Step 2: Upload to Instagram Reels
    try:
        ig_id = upload_instagram_reel(
            video_path=source_path, caption=video["title"]
        )
        print(f"[Dispatcher] Instagram Reel published. ID: {ig_id}")
    except Exception as e:
        print(f"[Dispatcher] Instagram upload failed: {e}")

    # Step 3: Update database record
    mark_video_published(video_id=video["id"], youtube_id=yt_id, instagram_id=ig_id)

    # Step 4: Move local file from pending to published folder
    dest_path = PUBLISHED_DIR / file_name
    shutil.move(str(source_path), str(dest_path))
    print(f"[Dispatcher] Moved {file_name} to published folder.")


# Dynamic Slot Dispatcher

def check_and_dispatch():
    """Check if the current hour matches the optimal upload window."""
    now = datetime.now()
    current_day = now.weekday()
    current_hour = now.hour

    optimal_day, optimal_hour = get_optimal_upload_slot(platform="youtube")
    print(
        f"[Optimizer] Current: (Day {current_day}, Hour {current_hour}) | Target Slot: (Day {optimal_day}, Hour {optimal_hour})"
    )

    if current_day == optimal_day and current_hour == optimal_hour:
        print("[Optimizer] Target slot active. Firing upload job.")
        publish_next_video()

# Main Execution Loop

if __name__ == "__main__":
    # Ensure database tables and folders exist
    initialize_database()

    scheduler = BackgroundScheduler()

    # Job 1: Scan pending folder every 5 minutes for new videos
    scheduler.add_job(
        scan_and_register_pending_videos, "interval", minutes=5, id="scan_videos"
    )

    # Job 2: Run optimal slot check every hour on the hour
    scheduler.add_job(
        check_and_dispatch, "cron", minute=0, id="check_upload_slot"
    )

    # Job 3: Sync post metrics every 6 hours to update optimizer scores
    scheduler.add_job(
        sync_published_video_metrics,
        "interval",
        hours=6,
        id="sync_metrics",
    )

    scheduler.start()
    print("[Agent] AutoShorts scheduler running. Press Ctrl+C to exit.")

    # Initial scan on startup
    scan_and_register_pending_videos()

    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        print("\n[Agent] Shutting down cleanly.")