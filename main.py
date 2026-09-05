import re
import shutil
import time
from pathlib import Path
from config import (
    BASE_DIR,
    DEFAULT_INSTAGRAM_CAPTION,
    DEFAULT_YOUTUBE_DESCRIPTION,
)
from uploader import upload_instagram_reel, upload_youtube_short

PENDING_DIR = BASE_DIR / "videos" / "pending"
PUBLISHED_DIR = BASE_DIR / "videos" / "published"


def clean_title(filename_stem: str) -> str:
    """Remove trailing hashtags from filename for a clean YouTube title."""
    cleaned = re.sub(r"#\S+", "", filename_stem).strip()
    return cleaned if cleaned else filename_stem


def process_pending_videos():
    """Scan pending folder and upload one video to both Instagram and YouTube."""
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

    video_files = sorted(list(PENDING_DIR.glob("*.mp4")))
    if not video_files:
        print("No pending videos found.")
        return

    print(f"Found {len(video_files)} video(s) in queue. Processing next video...")

    for video_path in video_files:
        raw_title = video_path.stem
        display_title = clean_title(raw_title)

        print("\n" + "=" * 50)
        print(f"Processing: {video_path.name}")
        print("=" * 50)

        # 1. Instagram Reels Upload (Strictly uses the default caption)
        try:
            ig_id = upload_instagram_reel(video_path, caption=DEFAULT_INSTAGRAM_CAPTION)
            print(f"-> Instagram Reel Published [ID: {ig_id}]")
        except Exception as e:
            print(f"-> Instagram Upload Failed: {e}")

        # Cooldown between platforms
        time.sleep(5)

        # 2. YouTube Shorts Upload (Clean title + strictly default description)
        try:
            yt_id = upload_youtube_short(
                video_path=video_path,
                title=display_title,
                description=DEFAULT_YOUTUBE_DESCRIPTION,
            )
            print(f"-> YouTube Short Published [ID: {yt_id}]")
        except Exception as e:
            print(f"-> YouTube Upload Failed: {e}")

        # 3. Archive processed video
        destination = PUBLISHED_DIR / video_path.name
        shutil.move(str(video_path), str(destination))
        print(f"-> Moved to published archive: {destination.name}")

        print("\nSingle post complete. Exiting batch run.")
        break


if __name__ == "__main__":
    process_pending_videos()