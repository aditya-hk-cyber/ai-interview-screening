"""Tests for src/url_utils.py"""

import pytest
from src.url_utils import classify_url, extract_drive_id


class TestClassifyUrl:
    def test_youtube_long(self):
        assert classify_url("https://www.youtube.com/watch?v=abc123") == "youtube"

    def test_youtube_short(self):
        assert classify_url("https://youtu.be/abc123") == "youtube"

    def test_drive_folder(self):
        url = "https://drive.google.com/drive/folders/1ABCxyz123"
        assert classify_url(url) == "drive_folder"

    def test_drive_file(self):
        url = "https://drive.google.com/file/d/1ABCxyz123/view"
        assert classify_url(url) == "drive_file"

    def test_drive_file_open(self):
        url = "https://drive.google.com/open?id=1ABCxyz123"
        assert classify_url(url) == "drive_file"

    def test_unknown(self):
        assert classify_url("https://example.com/video.mp4") == "unknown"

    def test_empty(self):
        assert classify_url("") == "unknown"


class TestExtractDriveId:
    def test_folder_url(self):
        url = "https://drive.google.com/drive/folders/1ABCxyz123?usp=sharing"
        assert extract_drive_id(url) == "1ABCxyz123"

    def test_file_url(self):
        url = "https://drive.google.com/file/d/1XYZabc456/view?usp=sharing"
        assert extract_drive_id(url) == "1XYZabc456"

    def test_id_param(self):
        url = "https://drive.google.com/open?id=1DEFghi789"
        assert extract_drive_id(url) == "1DEFghi789"

    def test_invalid_url(self):
        with pytest.raises(ValueError, match="Cannot extract ID"):
            extract_drive_id("https://example.com/notadrive")
