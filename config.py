import os
from pathlib import Path
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")

# Instagram Credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "og_clips04")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

# YouTube Credentials & Scopes
YOUTUBE_CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

DEFAULT_INSTAGRAM_CAPTION = (
    "今晚,V走进人群,欣赏了Vogue World: Hollywood的现场表演。"
    "以独特时尚造型而闻名的他,这次依旧保持一贯的高级感,展现出 effortless 的魅力。\n\n"
    "#clips #funnyclips #twitchclips #streamer #fyp"
)

DEFAULT_YOUTUBE_DESCRIPTION = "#Shorts #Gaming #Highlights #Viral"