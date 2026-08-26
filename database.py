from datetime import datetime
import sqlite3
from config import DATABASE_PATH


def get_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    """Create the necessary database tables if they do not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Table to track video files and upload status
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'pending', -- pending, scheduled, published, failed
                scheduled_time TEXT,
                published_time TEXT,
                youtube_id TEXT,
                instagram_id TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Table to track engagement metrics for the optimizer
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                platform TEXT NOT NULL, -- 'youtube' or 'instagram'
                post_day_of_week INTEGER NOT NULL, -- 0 (Monday) to 6 (Sunday)
                post_hour INTEGER NOT NULL, -- 0 to 23
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                retention_rate REAL DEFAULT 0.0,
                engagement_score REAL DEFAULT 0.0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos (id)
            )
        """
        )
        conn.commit()


def add_video(file_name: str, title: str, description: str = "") -> int:
    """Insert a new video record into the queue."""
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
        return cursor.lastrowid


def get_next_pending_video():
    """Retrieve the oldest pending video from the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM videos
            WHERE status = 'pending'
            ORDER BY id ASC
            LIMIT 1
        """
        )
        return cursor.fetchone()


def mark_video_published(
    video_id: int, youtube_id: str = None, instagram_id: str = None
):
    """Update status to published with platform IDs and current timestamp."""
    with get_connection() as conn:
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            """
            UPDATE videos
            SET status = 'published',
                published_time = ?,
                youtube_id = ?,
                instagram_id = ?
            WHERE id = ?
        """,
            (now, youtube_id, instagram_id, video_id),
        )
        conn.commit()


def save_analytics(
    video_id: int,
    platform: str,
    day_of_week: int,
    hour: int,
    views: int,
    likes: int,
    comments: int,
    shares: int,
    retention_rate: float,
):
    """Compute engagement score and record post performance."""
    # Composite score: views (40%), retention (30%), interactions (30%)
    interactions = likes + comments + shares
    score = (views * 0.4) + (retention_rate * 100 * 0.3) + (interactions * 0.3)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO analytics (
                video_id, platform, post_day_of_week, post_hour,
                views, likes, comments, shares, retention_rate, engagement_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                video_id,
                platform,
                day_of_week,
                hour,
                views,
                likes,
                comments,
                shares,
                retention_rate,
                score,
            ),
        )
        conn.commit()


def get_slot_performance_averages(platform: str) -> list:
    """Fetch average engagement scores grouped by day of week and hour."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                post_day_of_week,
                post_hour,
                AVG(engagement_score) as avg_score,
                COUNT(*) as sample_count
            FROM analytics
            WHERE platform = ?
            GROUP BY post_day_of_week, post_hour
            ORDER BY avg_score DESC
        """,
            (platform,),
        )
        return cursor.fetchall()


if __name__ == "__main__":
    initialize_database()