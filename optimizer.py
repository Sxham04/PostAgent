from datetime import datetime
import random
import requests
from config import (
    DEFAULT_POST_HOUR,
    EXPLORATION_RATE,
    INSTAGRAM_ACCESS_TOKEN,
)
from database import get_connection, get_slot_performance_averages, save_analytics
from uploader import get_youtube_service

# Metric Collectors

def fetch_instagram_metrics(instagram_media_id: str) -> dict:
    """Fetch engagement numbers for a published Instagram Reel."""
    if not instagram_media_id or not INSTAGRAM_ACCESS_TOKEN:
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0}

    url = f"https://graph.facebook.com/v19.0/{instagram_media_id}/insights"
    params = {
        "metric": "plays,likes,comments,shares",
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }

    try:
        res = requests.get(url, params=params).json()
        data = res.get("data", [])
        metrics = {item["name"]: item["values"][0]["value"] for item in data}
        return {
            "views": metrics.get("plays", 0),
            "likes": metrics.get("likes", 0),
            "comments": metrics.get("comments", 0),
            "shares": metrics.get("shares", 0),
        }
    except Exception as e:
        print(f"Warning: Could not fetch Instagram metrics: {e}")
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0}


def fetch_youtube_metrics(youtube_video_id: str) -> dict:
    """Fetch view, like, and comment counts for a YouTube Short."""
    if not youtube_video_id:
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0}

    try:
        youtube = get_youtube_service()
        req = youtube.videos().list(part="statistics", id=youtube_video_id)
        res = req.execute()

        items = res.get("items", [])
        if not items:
            return {"views": 0, "likes": 0, "comments": 0, "shares": 0}

        stats = items[0]["statistics"]
        return {
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "shares": 0,  # YouTube Data API v3 does not expose share counts directly
        }
    except Exception as e:
        print(f"Warning: Could not fetch YouTube metrics: {e}")
        return {"views": 0, "likes": 0, "comments": 0, "shares": 0}


def sync_published_video_metrics():
    """Scan database for published videos and refresh analytics scores."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, published_time, youtube_id, instagram_id
            FROM videos
            WHERE status = 'published'
        """
        )
        videos = cursor.fetchall()

    for vid in videos:
        if not vid["published_time"]:
            continue

        pub_dt = datetime.fromisoformat(vid["published_time"])
        day_of_week = pub_dt.weekday()
        hour = pub_dt.hour

        # Sync Instagram metrics if available
        if vid["instagram_id"]:
            ig_data = fetch_instagram_metrics(vid["instagram_id"])
            save_analytics(
                video_id=vid["id"],
                platform="instagram",
                day_of_week=day_of_week,
                hour=hour,
                views=ig_data["views"],
                likes=ig_data["likes"],
                comments=ig_data["comments"],
                shares=ig_data["shares"],
                retention_rate=0.0,
            )

        # Sync YouTube metrics if available
        if vid["youtube_id"]:
            yt_data = fetch_youtube_metrics(vid["youtube_id"])
            save_analytics(
                video_id=vid["id"],
                platform="youtube",
                day_of_week=day_of_week,
                hour=hour,
                views=yt_data["views"],
                likes=yt_data["likes"],
                comments=yt_data["comments"],
                shares=yt_data["shares"],
                retention_rate=0.0,
            )

# Timing Strategy (Epsilon-Greedy Slot Selector)

def get_optimal_upload_slot(platform: str) -> tuple[int, int]:
    """
    Return (day_of_week, hour) to publish next.
    Uses epsilon-greedy exploration to discover peak engagement times.
    """
    # Explore: Pick a random hour between 09:00 and 22:00
    if random.random() < EXPLORATION_RATE:
        random_day = random.randint(0, 6)
        random_hour = random.randint(9, 22)
        return random_day, random_hour

    # Exploit: Find the historical slot with the highest average engagement score
    slots = get_slot_performance_averages(platform)
    if not slots:
        # Default fallback if no data exists yet
        today = datetime.now().weekday()
        return today, DEFAULT_POST_HOUR

    best_slot = slots[0]  # Ordered DESC by avg_score in database query
    return int(best_slot["post_day_of_week"]), int(best_slot["post_hour"])