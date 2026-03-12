import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from src.transcription import (
    _parse_deepgram_response,
    extract_audio,
    load_api_key,
    process_video,
    transcribe_audio,
)


class TestLoadApiKey(unittest.TestCase):
    @patch("src.transcription.Path.exists", return_value=True)
    @patch("src.transcription.Path.read_text", return_value="test_api_key_123\nextra line\n")
    def test_load_api_key(self, mock_read, mock_exists):
        import src.transcription as mod

        mod.DEEPGRAM_API_KEY = None
        key = load_api_key("DeepGram")
        self.assertEqual(key, "test_api_key_123")
        self.assertEqual(mod.DEEPGRAM_API_KEY, "test_api_key_123")

    @patch("src.transcription.Path.exists", return_value=False)
    def test_load_api_key_missing_file(self, mock_exists):
        with self.assertRaises(FileNotFoundError):
            load_api_key("nonexistent")


class TestExtractAudio(unittest.TestCase):
    @patch("src.transcription.subprocess.run")
    @patch("src.transcription.Path.exists", return_value=True)
    def test_extract_audio(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = extract_audio("/tmp/video.mp4")
        self.assertEqual(result, "/tmp/video.mp3")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-vn", cmd)
        self.assertIn("-acodec", cmd)

    @patch("src.transcription.subprocess.run")
    @patch("src.transcription.Path.exists", return_value=True)
    def test_extract_audio_ffmpeg_failure(self, mock_exists, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="codec error")
        with self.assertRaises(RuntimeError):
            extract_audio("/tmp/video.mp4")

    @patch("src.transcription.Path.exists", return_value=False)
    def test_extract_audio_missing_file(self, mock_exists):
        with self.assertRaises(FileNotFoundError):
            extract_audio("/tmp/missing.mp4")


SAMPLE_DEEPGRAM_RESPONSE = {
    "metadata": {"duration": 60.0},
    "results": {
        "channels": [
            {
                "alternatives": [
                    {
                        "transcript": "Hello um I am actually here to talk about the project.",
                        "words": [
                            {"word": "Hello", "start": 0.0, "end": 0.5, "confidence": 0.99},
                            {"word": "um", "start": 0.6, "end": 0.8, "confidence": 0.85},
                            {"word": "I", "start": 0.9, "end": 1.0, "confidence": 0.98},
                            {"word": "am", "start": 1.0, "end": 1.2, "confidence": 0.97},
                            {"word": "actually", "start": 1.3, "end": 1.8, "confidence": 0.90},
                            {"word": "here", "start": 1.9, "end": 2.1, "confidence": 0.96},
                            {"word": "to", "start": 2.2, "end": 2.3, "confidence": 0.99},
                            {"word": "talk", "start": 2.4, "end": 2.6, "confidence": 0.98},
                            {"word": "about", "start": 2.7, "end": 2.9, "confidence": 0.97},
                            {"word": "the", "start": 3.0, "end": 3.1, "confidence": 0.99},
                            {"word": "project.", "start": 3.2, "end": 3.5, "confidence": 0.95},
                        ],
                    }
                ]
            }
        ],
        "utterances": [
            {
                "transcript": "Hello um I am actually here to talk about the project.",
                "start": 0.0,
                "end": 3.5,
            }
        ],
    },
}


class TestTranscribeAudio(unittest.TestCase):
    @patch("src.transcription.load_api_key", return_value="fake_key")
    @patch("builtins.open", mock_open(read_data=b"fake audio data"))
    @patch("src.transcription.requests.post")
    def test_transcribe_audio(self, mock_post, mock_load_key):
        import src.transcription as mod

        mod.DEEPGRAM_API_KEY = "fake_key"

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_DEEPGRAM_RESPONSE
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = transcribe_audio("/tmp/audio.mp3")

        # Verify structure
        self.assertIn("transcript", result)
        self.assertIn("words", result)
        self.assertIn("utterances", result)
        self.assertIn("filler_words", result)
        self.assertIn("metadata", result)

        # Verify transcript content
        self.assertIn("Hello", result["transcript"])

        # Verify word count
        self.assertEqual(result["metadata"]["word_count"], 11)

        # Verify filler words detected (um, actually)
        self.assertEqual(result["filler_words"]["count"], 2)
        filler_word_texts = [f["word"] for f in result["filler_words"]["instances"]]
        self.assertIn("um", filler_word_texts)
        self.assertIn("actually", filler_word_texts)

        # Verify metadata
        self.assertEqual(result["metadata"]["duration"], 60.0)
        self.assertGreater(result["metadata"]["words_per_minute"], 0)
        self.assertGreater(result["metadata"]["avg_confidence"], 0)

        # Verify API was called correctly
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        self.assertIn("Token", call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))["Authorization"])


class TestProcessVideo(unittest.TestCase):
    @patch("src.transcription.transcribe_audio")
    @patch("src.transcription.extract_audio")
    def test_process_video_local(self, mock_extract, mock_transcribe):
        mock_extract.return_value = "/tmp/video.mp3"
        mock_transcribe.return_value = {
            "transcript": "test transcript",
            "words": [],
            "utterances": [],
            "filler_words": {"count": 0, "instances": []},
            "metadata": {
                "duration": 10.0,
                "word_count": 2,
                "words_per_minute": 12.0,
                "avg_confidence": 0.95,
                "filler_word_rate": 0.0,
            },
        }

        result = process_video("/tmp/video.mp4")

        mock_extract.assert_called_once_with("/tmp/video.mp4")
        mock_transcribe.assert_called_once_with("/tmp/video.mp3")
        self.assertEqual(result["transcript"], "test transcript")

    @patch("src.transcription.transcribe_audio")
    @patch("src.transcription.extract_audio")
    @patch("src.transcription.download_video")
    def test_process_video_url(self, mock_download, mock_extract, mock_transcribe):
        mock_download.return_value = ["/tmp/dl/video.mp4"]
        mock_extract.return_value = "/tmp/dl/video.mp3"
        mock_transcribe.return_value = {"transcript": "from url", "words": [], "utterances": [], "filler_words": {"count": 0, "instances": []}, "metadata": {"duration": 5.0, "word_count": 2, "words_per_minute": 24.0, "avg_confidence": 0.9, "filler_word_rate": 0.0}}

        result = process_video("https://drive.google.com/file/d/abc123")

        mock_download.assert_called_once()
        self.assertEqual(result["transcript"], "from url")


class TestParseDeepgramResponse(unittest.TestCase):
    def test_parse_response(self):
        result = _parse_deepgram_response(SAMPLE_DEEPGRAM_RESPONSE)
        self.assertEqual(len(result["words"]), 11)
        self.assertEqual(len(result["utterances"]), 1)
        self.assertEqual(result["filler_words"]["count"], 2)
        self.assertAlmostEqual(result["metadata"]["duration"], 60.0)

    def test_parse_empty_response(self):
        result = _parse_deepgram_response({"results": {}, "metadata": {}})
        self.assertEqual(result["transcript"], "")
        self.assertEqual(result["words"], [])
        self.assertEqual(result["metadata"]["word_count"], 0)


if __name__ == "__main__":
    unittest.main()
