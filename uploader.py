import time
from pathlib import Path
import boto3
from botocore.exceptions import NoCredentialsError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import requests

from config import (
    AWS_ACCESS_KEY_ID,
    AWS_REGION,
    AWS_SECRET_ACCESS_KEY,
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_USER_ID,
    S3_BUCKET_NAME,
    YOUTUBE_CLIENT_SECRETS_FILE,
    YOUTUBE_SCOPES,
)

# ---------------------------------------------------------------------------
# Storage Helper: AWS S3
# ---------------------------------------------------------------------------


def upload_to_s3(file_path: Path) -> str:
    """Upload a local video file to AWS S3 and return its public URL."""
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    object_name = f"temp_videos/{file_path.name}"

    try:
        s3_client.upload_file(
            str(file_path),
            S3_BUCKET_NAME,
            object_name,
            ExtraArgs={"ContentType": "video/mp4"},
        )
        url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{object_name}"
        return url
    except NoCredentialsError:
        print("Error: AWS credentials not found.")
        return ""


def delete_from_s3(file_name: str) -> None:
    """Delete a temporary video file from AWS S3 after publishing."""
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )
    object_name = f"temp_videos/{file_name}"
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=object_name)
    except Exception as e:
        print(f"Warning: Could not delete temporary S3 file: {e}")


# ---------------------------------------------------------------------------
# Platform: Instagram Reels
# ---------------------------------------------------------------------------


def upload_instagram_reel(video_path: Path, caption: str) -> str:
    """Upload a video as an Instagram Reel using Meta Graph API."""
    # Step 1: Upload to S3 to get a public URL
    public_url = upload_to_s3(video_path)
    if not public_url:
        raise RuntimeError("Failed to generate public video URL for Instagram.")

    base_api = "https://graph.facebook.com/v19.0"

    # Step 2: Create media container
    create_url = f"{base_api}/{INSTAGRAM_USER_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": public_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }
    res = requests.post(create_url, data=payload).json()
    container_id = res.get("id")

    if not container_id:
        delete_from_s3(video_path.name)
        raise RuntimeError(f"Instagram container creation failed: {res}")

    # Step 3: Poll status until video processing finishes
    status_url = f"{base_api}/{container_id}"
    ready = False
    for _ in range(15):  # Wait up to 150 seconds
        time.sleep(10)
        status_res = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": INSTAGRAM_ACCESS_TOKEN},
        ).json()
        status_code = status_res.get("status_code")

        if status_code == "FINISHED":
            ready = True
            break
        elif status_code == "ERROR":
            delete_from_s3(video_path.name)
            raise RuntimeError(f"Instagram media processing error: {status_res}")

    if not ready:
        delete_from_s3(video_path.name)
        raise TimeoutError("Instagram media processing timed out.")

    # Step 4: Publish container
    publish_url = f"{base_api}/{INSTAGRAM_USER_ID}/media_publish"
    publish_res = requests.post(
        publish_url,
        data={
            "creation_id": container_id,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        },
    ).json()

    # Step 5: Clean up temporary S3 file
    delete_from_s3(video_path.name)

    return publish_res.get("id", "")


# ---------------------------------------------------------------------------
# Platform: YouTube Shorts
# ---------------------------------------------------------------------------


def get_youtube_service():
    """Authenticate and return an authorized YouTube API service object."""
    flow = InstalledAppFlow.from_client_secrets_file(
        YOUTUBE_CLIENT_SECRETS_FILE, scopes=YOUTUBE_SCOPES
    )
    credentials = flow.run_local_server(port=0)
    return build("youtube", "v3", credentials=credentials)


def upload_youtube_short(
    video_path: Path, title: str, description: str = ""
) -> str:
    """Upload a local video as a YouTube Short using YouTube Data API v3."""
    youtube = get_youtube_service()

    # Ensure title contains #Shorts tag
    full_title = f"{title} #Shorts" if "#Shorts" not in title else title
    full_desc = f"{description}\n\n#Shorts"

    body = {
        "snippet": {
            "title": full_title,
            "description": full_desc,
            "categoryId": "22",  # People & Blogs category
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4"
    )

    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response.get("id", "")