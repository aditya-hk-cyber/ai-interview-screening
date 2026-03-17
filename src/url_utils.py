"""URL classification and ID extraction utilities."""


def classify_url(url: str) -> str:
    """Classify a URL as 'youtube', 'drive_file', 'drive_folder', or 'unknown'."""
    if not url:
        return "unknown"
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    if "drive.google.com" in url_lower:
        if "/folders/" in url_lower:
            return "drive_folder"
        return "drive_file"
    return "unknown"


def extract_drive_id(drive_url: str) -> str:
    """Extract folder/file ID from a Google Drive URL."""
    if "/folders/" in drive_url:
        return drive_url.split("/folders/")[1].split("?")[0].split("/")[0]
    elif "/file/d/" in drive_url:
        return drive_url.split("/file/d/")[1].split("/")[0].split("?")[0]
    elif "id=" in drive_url:
        return drive_url.split("id=")[1].split("&")[0]
    raise ValueError(f"Cannot extract ID from URL: {drive_url}")
