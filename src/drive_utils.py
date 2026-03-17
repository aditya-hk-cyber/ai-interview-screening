import json
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service(credentials_file="ds-dream11-0eb59d82137f.json"):
    """Build authenticated Drive API service."""
    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def get_or_create_subfolder(service, parent_folder_id: str, subfolder_name: str) -> str:
    """Get existing subfolder or create it. Returns folder_id."""
    # Search for existing folder
    q = f"name='{subfolder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=q, fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    # Create it
    meta = {
        "name": subfolder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_folder_id],
    }
    folder = service.files().create(body=meta, fields="id", supportsAllDrives=True).execute()
    return folder["id"]

def upload_file_to_drive(service, local_path: str, folder_id: str, filename: str = None) -> str:
    """Upload or update a file in Drive. Returns file_id."""
    local_path = Path(local_path)
    filename = filename or local_path.name

    # Determine MIME type
    suffix = local_path.suffix.lower()
    mime_map = {".json": "application/json", ".md": "text/markdown", ".txt": "text/plain"}
    mime_type = mime_map.get(suffix, "application/octet-stream")

    # Check if file already exists in folder
    q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=q, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    existing = results.get("files", [])

    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)

    if existing:
        # Update existing file
        file_id = existing[0]["id"]
        service.files().update(fileId=file_id, media_body=media, supportsAllDrives=True).execute()
    else:
        # Create new file
        meta = {"name": filename, "parents": [folder_id]}
        result = service.files().create(body=meta, media_body=media, fields="id", supportsAllDrives=True).execute()
        file_id = result["id"]

    return file_id

LOCAL_TRACKING_FILE = Path(__file__).parent.parent / "evaluated_videos.json"


def load_tracking_file(service, folder_id: str) -> dict:
    """Load tracking data. Uses local file as primary, Drive as fallback."""
    if LOCAL_TRACKING_FILE.exists():
        try:
            content = LOCAL_TRACKING_FILE.read_text().strip()
            if content:
                return json.loads(content)
        except (json.JSONDecodeError, Exception):
            pass
    # Try loading from Drive as fallback (read-only, no write quota needed)
    try:
        q = f"name='evaluated_videos.json' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=q, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = results.get("files", [])
        if files:
            request = service.files().get_media(fileId=files[0]["id"])
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            buf.seek(0)
            return json.loads(buf.read().decode("utf-8"))
    except Exception:
        pass
    return {"evaluated": {}}


def save_tracking_file(_service, tracking_data: dict, _folder_id: str):
    """Save tracking data locally (primary). Silently skips Drive upload (no quota for service accounts on personal drives)."""
    LOCAL_TRACKING_FILE.write_text(json.dumps(tracking_data, indent=2))

def get_unevaluated_videos(service, folder_id: str, tracking_data: dict) -> list:
    """Return list of {id, name} dicts for videos not yet evaluated.

    Raises HttpError if the folder is inaccessible (403/404).
    """
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg"}
    VIDEO_MIMES = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm", "video/mpeg"}

    q = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(q=q, fields="files(id, name, mimeType)", supportsAllDrives=True, includeItemsFromAllDrives=True, pageSize=100).execute()
    all_files = results.get("files", [])

    evaluated_ids = set(tracking_data.get("evaluated", {}).keys())

    unevaluated = []
    for f in all_files:
        if f["id"] in evaluated_ids:
            continue
        ext = Path(f["name"]).suffix.lower()
        if f.get("mimeType", "") in VIDEO_MIMES or ext in VIDEO_EXTENSIONS:
            unevaluated.append({"id": f["id"], "name": f["name"]})

    return unevaluated

def mark_video_evaluated(tracking_data: dict, file_id: str, filename: str,
                          report_json_id: str, report_md_id: str,
                          score: float, recommendation: str) -> dict:
    """Add a video entry to tracking data."""
    from datetime import datetime
    tracking_data["evaluated"][file_id] = {
        "filename": filename,
        "evaluated_at": datetime.now().isoformat(),
        "report_json_id": report_json_id,
        "report_md_id": report_md_id,
        "overall_score": score,
        "recommendation": recommendation,
    }
    return tracking_data
