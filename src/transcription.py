import os
import json
import subprocess
import tempfile
from pathlib import Path

import gdown
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

DEEPGRAM_API_KEY = None  # loaded from file at runtime

FILLER_WORDS = {"um", "uh", "hmm", "like", "you know", "so", "actually"}

DEEPGRAM_API_URL = "https://api.deepgram.com/v1/listen"


def load_api_key(key_file="DeepGram"):
    """Load Deepgram API key from file (first line)."""
    global DEEPGRAM_API_KEY
    key_path = Path(key_file)
    if not key_path.exists():
        raise FileNotFoundError(f"API key file not found: {key_file}")
    DEEPGRAM_API_KEY = key_path.read_text().strip().splitlines()[0].strip()
    return DEEPGRAM_API_KEY


def _get_drive_service(credentials_file: str = "ds-dream11-0eb59d82137f.json"):
    """Build an authenticated Google Drive API service using service account."""
    creds = service_account.Credentials.from_service_account_file(
        credentials_file,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    return build("drive", "v3", credentials=creds)


def _extract_folder_id(drive_url: str) -> str:
    """Extract folder/file ID from a Google Drive URL."""
    # Handle formats like /folders/<id> or /file/d/<id> or ?id=<id>
    if "/folders/" in drive_url:
        return drive_url.split("/folders/")[1].split("?")[0].split("/")[0]
    elif "/file/d/" in drive_url:
        return drive_url.split("/file/d/")[1].split("/")[0].split("?")[0]
    elif "id=" in drive_url:
        return drive_url.split("id=")[1].split("&")[0]
    raise ValueError(f"Cannot extract ID from URL: {drive_url}")


def _download_file_from_drive(service, file_id: str, dest_path: Path) -> str:
    """Download a single file from Google Drive by file ID."""
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return str(dest_path)


def download_video(drive_url: str, output_dir: str = ".") -> list[str]:
    """Download video(s) from Google Drive URL.

    Uses service account credentials for authenticated access.
    Falls back to gdown for public folders.
    Returns list of downloaded file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    VIDEO_MIME_TYPES = {
        "video/mp4", "video/quicktime", "video/x-msvideo",
        "video/x-matroska", "video/webm", "video/mpeg",
    }

    try:
        service = _get_drive_service()
        if "folders" in drive_url:
            folder_id = _extract_folder_id(drive_url)
            query = f"'{folder_id}' in parents and trashed=false"
            results = service.files().list(
                q=query,
                fields="files(id, name, mimeType)",
                pageSize=50,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            files = results.get("files", [])
            if not files:
                raise RuntimeError(f"No files found in folder: {folder_id}")
            # Filter to video files only
            video_files = [f for f in files if f.get("mimeType", "") in VIDEO_MIME_TYPES]
            if not video_files:
                # Fall back to all files if no video MIME types detected
                video_files = files
            downloaded = []
            for f in video_files:
                dest = output_dir / f["name"]
                print(f"  Downloading: {f['name']}")
                _download_file_from_drive(service, f["id"], dest)
                downloaded.append(str(dest))
            return downloaded
        else:
            file_id = _extract_folder_id(drive_url)
            meta = service.files().get(fileId=file_id, fields="name").execute()
            dest = output_dir / meta["name"]
            _download_file_from_drive(service, file_id, dest)
            return [str(dest)]
    except Exception as e:
        print(f"  Service account download failed ({e}), trying gdown...")
        if "folders" in drive_url:
            files = gdown.download_folder(url=drive_url, output=str(output_dir), quiet=False)
            if files is None:
                raise RuntimeError(f"Failed to download folder from {drive_url}")
            return [str(f) for f in files]
        else:
            output_path = str(output_dir / "video_download")
            result = gdown.download(url=drive_url, output=output_path, quiet=False, fuzzy=True)
            if result is None:
                raise RuntimeError(f"Failed to download file from {drive_url}")
            return [result]


def extract_audio(video_path: str, output_dir: str = None) -> str:
    """Extract audio from video using ffmpeg. Returns path to MP3 file."""
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if output_dir is None:
        output_dir = video_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    audio_path = output_dir / (video_path.stem + ".mp3")

    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-vn", "-acodec", "mp3", "-ar", "16000",
        "-y",  # overwrite if exists
        str(audio_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return str(audio_path)


def transcribe_audio(audio_path: str) -> dict:
    """Transcribe audio using Deepgram Nova-2 API.

    Returns structured transcript dict matching TRANSCRIPT_SCHEMA.
    """
    if DEEPGRAM_API_KEY is None:
        load_api_key()

    params = {
        "model": "nova-2",
        "smart_format": "true",
        "utterances": "true",
        "punctuate": "true",
        "filler_words": "true",
    }
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/mpeg",
    }

    with open(audio_path, "rb") as f:
        response = requests.post(
            DEEPGRAM_API_URL,
            headers=headers,
            params=params,
            data=f,
        )
    response.raise_for_status()
    data = response.json()

    return _parse_deepgram_response(data)


def _parse_deepgram_response(data: dict) -> dict:
    """Parse raw Deepgram API response into TRANSCRIPT_SCHEMA format."""
    result = data.get("results", {})
    channels = result.get("channels", [{}])
    alt = channels[0].get("alternatives", [{}])[0] if channels else {}

    transcript_text = alt.get("transcript", "")
    words_raw = alt.get("words", [])

    # Build word list
    words = [
        {
            "word": w["word"],
            "start": w["start"],
            "end": w["end"],
            "confidence": w["confidence"],
        }
        for w in words_raw
    ]

    # Build utterances from Deepgram utterances
    utterances_raw = result.get("utterances", [])
    utterances = [
        {
            "transcript": u["transcript"],
            "start": u["start"],
            "end": u["end"],
        }
        for u in utterances_raw
    ]

    # Detect filler words
    filler_instances = [
        {"word": w["word"], "start": w["start"], "end": w["end"]}
        for w in words_raw
        if w["word"].lower() in FILLER_WORDS
    ]

    # Metadata
    duration = data.get("metadata", {}).get("duration", 0.0)
    word_count = len(words)
    words_per_minute = (word_count / duration * 60) if duration > 0 else 0.0
    confidences = [w["confidence"] for w in words_raw]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    filler_rate = len(filler_instances) / word_count if word_count > 0 else 0.0

    return {
        "transcript": transcript_text,
        "words": words,
        "utterances": utterances,
        "filler_words": {
            "count": len(filler_instances),
            "instances": filler_instances,
        },
        "metadata": {
            "duration": duration,
            "word_count": word_count,
            "words_per_minute": round(words_per_minute, 2),
            "avg_confidence": round(avg_confidence, 4),
            "filler_word_rate": round(filler_rate, 4),
        },
    }


def download_video_by_id(service, file_id: str, filename: str, output_dir: str) -> str:
    """Download a specific video file from Drive by file ID."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    dest = output_path / filename
    _download_file_from_drive(service, file_id, dest)
    return str(dest)


def process_video(video_path_or_url: str) -> dict:
    """Full pipeline: download (if URL) or use local file, extract audio, transcribe.

    Returns structured transcript dict matching TRANSCRIPT_SCHEMA.
    """
    if video_path_or_url.startswith("http"):
        with tempfile.TemporaryDirectory() as tmp_dir:
            downloaded = download_video(video_path_or_url, output_dir=tmp_dir)
            results = []
            for video_path in downloaded:
                audio_path = extract_audio(video_path, output_dir=tmp_dir)
                transcript = transcribe_audio(audio_path)
                results.append(transcript)
            return results[0] if len(results) == 1 else results
    else:
        audio_path = extract_audio(video_path_or_url)
        return transcribe_audio(audio_path)
