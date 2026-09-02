import argparse
from datetime import datetime
from pathlib import Path
import shutil
import time

from apscheduler.schedulers.background import BackgroundScheduler
from config import (
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_USER_ID,
    PENDING_DIR,
    PUBLISHED_DIR,
)
from database import (
    add_video,
    get_next_pending_video,
    initialize_database,
    mark_video_published,
)
from optimizer import get_optimal_upload_slot, sync_published_video_metrics
from uploader import upload_instagram_reel, upload_youtube_short

# ---------------------------------------------------------------------------
# Ingestion and Publishing Routines
# ---------------------------------------------------------------------------


def scan_and_register_pending_videos():
    """Find new MP4 files in the pending folder and add them to the database."""
    video_extensions = {".mp4", ".mov", ".mkv"}
    for file_path in PENDING_DIR.iterdir():
        if file_path.suffix.lower() in video_extensions:
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

    # Step 2: Upload to Instagram Reels (optional fallback)
    if INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID:
        try:
            ig_id = upload_instagram_reel(
                video_path=source_path, caption=video["title"]
            )
            print(f"[Dispatcher] Instagram Reel published. ID: {ig_id}")
        except Exception as e:
            print(f"[Dispatcher] Instagram upload failed: {e}")
    else:
        print(
            "[Dispatcher] Instagram credentials not configured. Skipping Instagram."
        )

    # Step 3: Update database & move file only if at least one upload succeeded
    if yt_id or ig_id:
        mark_video_published(
            video_id=video["id"], youtube_id=yt_id, instagram_id=ig_id
        )
        dest_path = PUBLISHED_DIR / file_name
        shutil.move(str(source_path), str(dest_path))
        print(f"[Dispatcher] Moved {file_name} to published folder.")
    else:
        print(
            f"[Dispatcher] Both uploads failed. Retaining {file_name} in pending queue."
        )


# ---------------------------------------------------------------------------
# Dynamic Slot Dispatcher
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main Execution Loop & CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PostAgent Automation Daemon")
    parser.add_argument(
        "--now",
        action="store_true",
        help="Run an immediate upload job without waiting for the scheduler.",
    )
    args = parser.parse_args()

    # Ensure database tables and folders exist
    initialize_database()

    # Initial scan of directory
    scan_and_register_pending_videos()

    if args.now:
        print("[CLI] Immediate publish flag triggered.")
        publish_next_video()
    else:
        scheduler = BackgroundScheduler()

        # Job 1: Scan pending folder every 5 minutes
        scheduler.add_job(
            scan_and_register_pending_videos,
            "interval",
            minutes=5,
            id="scan_videos",
        )

        # Job 2: Check slot every hour
        scheduler.add_job(
            check_and_dispatch, "cron", minute=0, id="check_upload_slot"
        )

        # Job 3: Sync analytics every 6 hours
        scheduler.add_job(
            sync_published_video_metrics,
            "interval",
            hours=6,
            id="sync_metrics",
        )

        scheduler.start()
        print("[Agent] PostAgent scheduler running. Press Ctrl+C to exit.")

        try:
            while True:
                time.sleep(2)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            print("\n[Agent] Shutting down cleanly.")