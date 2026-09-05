from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from config import BASE_DIR

DB_PATH = BASE_DIR / "data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    """Initialize database tables with hourly slot and engagement metric tracking."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT UNIQUE,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'pending',
                youtube_id TEXT,
                instagram_id TEXT,
                published_at TIMESTAMP,
                publish_hour INTEGER,
                publish_day INTEGER,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                engagement_score REAL DEFAULT 0.0
            )
            """
        )
        conn.commit()


def add_video(file_name: str, title: str, description: str = "") -> None:
    """Register a new video into the queue if not already present."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO videos (file_name, title, description, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (file_name, title, description),
        )
        conn.commit()


def get_next_pending_video() -> Optional[Dict[str, Any]]:
    """Retrieve the oldest pending video from the queue."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, file_name, title, description 
            FROM videos 
            WHERE status = 'pending' 
            ORDER BY id ASC 
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def mark_video_published(
    video_id: int, youtube_id: Optional[str], instagram_id: Optional[str]
) -> None:
    """Mark a video as published, saving timestamps and upload hour slots."""
    now = datetime.now()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET status = 'published',
                youtube_id = ?,
                instagram_id = ?,
                published_at = ?,
                publish_hour = ?,
                publish_day = ?
            WHERE id = ?
            """,
            (youtube_id, instagram_id, now, now.hour, now.weekday(), video_id),
        )
        conn.commit()


def update_video_metrics(
    youtube_id: str, views: int, likes: int, comments: int
) -> None:
    """Update view/engagement metrics and compute weighted performance score."""
    score = views + (likes * 5.0) + (comments * 10.0)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE videos
            SET view_count = ?,
                like_count = ?,
                comment_count = ?,
                engagement_score = ?
            WHERE youtube_id = ?
            """,
            (views, likes, comments, score, youtube_id),
        )
        conn.commit()


def get_published_youtube_ids() -> List[str]:
    """Return all YouTube IDs that need metric updates."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT youtube_id 
            FROM videos 
            WHERE status = 'published' AND youtube_id IS NOT NULL
            """
        )
        rows = cursor.fetchall()
        return [row["youtube_id"] for row in rows]