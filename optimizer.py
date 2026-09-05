import sqlite3
from typing import List, Tuple
from config import BASE_DIR
from database import get_connection, update_video_metrics
from uploader import get_youtube_service

DEFAULT_EXPLORATION_SLOTS = [10, 14, 18, 22]


def sync_published_video_metrics() -> None:
    """Fetch latest view, like, and comment stats from YouTube API for published videos."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT youtube_id FROM videos 
        WHERE status = 'published' AND youtube_id IS NOT NULL
        """
    )
    video_rows = cursor.fetchall()
    conn.close()

    if not video_rows:
        return

    youtube = get_youtube_service()
    video_ids = [row["youtube_id"] for row in video_rows]

    # Process in chunks of 50 (YouTube API maximum per request)
    chunk_size = 50
    for i in range(0, len(video_ids), chunk_size):
        chunk = video_ids[i : i + chunk_size]
        try:
            response = (
                youtube.videos()
                .list(part="statistics", id=",".join(chunk))
                .execute()
            )

            for item in response.get("items", []):
                yid = item["id"]
                stats = item.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                likes = int(stats.get("likeCount", 0))
                comments = int(stats.get("commentCount", 0))
                update_video_metrics(
                    youtube_id=yid, views=views, likes=likes, comments=comments
                )

            print(
                f"[Optimizer] Synced analytics for {len(response.get('items', []))} videos."
            )
        except Exception as e:
            print(f"[Optimizer] Metric sync failed: {e}")


def get_top_performing_slots(top_n: int = 4) -> List[int]:
    """
    Analyze past performance to find the best upload hours.
    Falls back to DEFAULT_EXPLORATION_SLOTS if less than 10 data points exist.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                publish_hour,
                COUNT(*) as sample_count,
                AVG(engagement_score) as avg_score
            FROM videos
            WHERE status = 'published' AND publish_hour IS NOT NULL
            GROUP BY publish_hour
            HAVING sample_count >= 2
            ORDER BY avg_score DESC
            LIMIT ?
            """,
            (top_n,),
        )
        results = cursor.fetchall()

    if len(results) < top_n:
        return DEFAULT_EXPLORATION_SLOTS

    return [row["publish_hour"] for row in results]


def get_slot_summary() -> List[Tuple[int, int, float]]:
    """Return raw statistics (hour, uploads_count, avg_score) for CLI review."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                publish_hour,
                COUNT(*) as count,
                ROUND(AVG(engagement_score), 2) as avg_score
            FROM videos
            WHERE status = 'published' AND publish_hour IS NOT NULL
            GROUP BY publish_hour
            ORDER BY avg_score DESC
            """
        )
        return cursor.fetchall()