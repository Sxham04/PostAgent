import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory paths
BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "videos"
PENDING_DIR = VIDEOS_DIR / "pending"
PUBLISHED_DIR = VIDEOS_DIR / "published"
DATABASE_PATH = BASE_DIR / "data.db"

# Create directories if they do not exist
PENDING_DIR.mkdir(parents=True, exist_ok=True)
PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

# Instagram API credentials
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

# YouTube API credentials
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv(
    "YOUTUBE_CLIENT_SECRETS_FILE", str(BASE_DIR / "client_secrets.json")
)
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# S3 / Public storage (Required for Instagram Reel upload)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Optimizer settings
DEFAULT_POST_HOUR = int(os.getenv("DEFAULT_POST_HOUR", "18"))
EXPLORATION_RATE = float(os.getenv("EXPLORATION_RATE", "0.20"))