"""Integration tests for the full pipeline with mocked dependencies."""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reporter import generate_json_report, generate_markdown_report, save_reports
from evaluate import prepare_evaluator_input


MOCK_TRANSCRIPT_DATA = {
    "transcript": "I believe cricket is one of the most strategic sports out there. The captain has to make real-time decisions about bowling changes and field placements. It requires deep knowledge of player strengths and match conditions.",
    "words": [
        {"word": "I", "start": 0.1, "end": 0.2, "confidence": 0.99},
        {"word": "believe", "start": 0.3, "end": 0.6, "confidence": 0.97},
        {"word": "cricket", "start": 0.7, "end": 1.0, "confidence": 0.98},
    ],
    "utterances": [
        {
            "transcript": "I believe cricket is one of the most strategic sports out there.",
            "start": 0.0,
            "end": 4.5,
        }
    ],
    "filler_words": {
        "count": 1,
        "instances": [{"word": "um", "start": 5.2, "end": 5.4}],
    },
    "metadata": {
        "duration": 65.0,
        "word_count": 42,
        "words_per_minute": 138.5,
        "avg_confidence": 0.96,
        "filler_word_rate": 0.024,
    },
}

MOCK_EVALUATION_DATA = {
    "communication_quality": {
        "score": 8.0,
        "justification": "Articulate with good vocabulary and minimal fillers.",
        "evidence": ["Uses strategic terminology naturally", "Clear sentence structure"],
    },
    "coherence": {
        "score": 8.5,
        "justification": "Well-structured argument with logical progression.",
        "evidence": ["Moves from thesis to supporting examples"],
    },
    "sports_knowledge": {
        "score": 9.0,
        "justification": "Deep cricket knowledge with tactical awareness.",
        "evidence": ["Mentions bowling changes and field placements", "References match conditions"],
    },
    "weighted_score": 8.55,
    "strengths": ["Strong domain knowledge", "Clear communication", "Logical flow"],
    "weaknesses": ["Minor filler word usage"],
    "recommendation": "Strong Yes",
}


class TestFullPipelineWithMocks:
    """Integration test: mock transcription and evaluation, verify full report output."""

    def test_full_pipeline_with_mocks(self):
        """Test the full pipeline from transcript data to saved reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Generate JSON report from mocked data
            report_data = generate_json_report(
                MOCK_TRANSCRIPT_DATA,
                MOCK_EVALUATION_DATA,
                video_url="https://drive.google.com/example",
            )

            # Verify report structure
            assert "generated_at" in report_data
            assert report_data["video_url"] == "https://drive.google.com/example"
            assert report_data["evaluation"]["weighted_score"] == 8.55
            assert report_data["transcript_stats"]["duration"] == 65.0

            # Step 2: Generate markdown
            md = generate_markdown_report(report_data)
            assert "AI Interview Screening Report" in md
            assert "8.5" in md  # weighted score
            assert "Strong Yes" in md
            assert "Communication Quality" in md
            assert "Coherence" in md
            assert "Sports Knowledge" in md
            assert "Strong domain knowledge" in md

            # Step 3: Save reports
            json_path, md_path = save_reports(report_data, tmpdir)

            # Verify files exist
            assert os.path.isfile(json_path)
            assert os.path.isfile(md_path)

            # Verify JSON content
            with open(json_path) as f:
                saved_json = json.load(f)
            assert saved_json["evaluation"]["recommendation"] == "Strong Yes"
            assert saved_json["transcript_stats"]["word_count"] == 42

            # Verify markdown content
            with open(md_path) as f:
                saved_md = f.read()
            assert len(saved_md) > 100
            assert "cricket" in saved_md

    def test_pipeline_with_empty_transcript(self):
        """Test pipeline handles a near-empty transcript gracefully."""
        empty_transcript = {
            "transcript": "Hello.",
            "words": [{"word": "Hello", "start": 0.0, "end": 0.5, "confidence": 0.8}],
            "utterances": [{"transcript": "Hello.", "start": 0.0, "end": 0.5}],
            "filler_words": {"count": 0, "instances": []},
            "metadata": {
                "duration": 2.0,
                "word_count": 1,
                "words_per_minute": 30.0,
                "avg_confidence": 0.8,
                "filler_word_rate": 0.0,
            },
        }
        low_eval = {
            "communication_quality": {"score": 1.0, "justification": "Barely any speech.", "evidence": []},
            "coherence": {"score": 1.0, "justification": "No structure.", "evidence": []},
            "sports_knowledge": {"score": 0.0, "justification": "No sports content.", "evidence": []},
            "weighted_score": 0.6,
            "strengths": [],
            "weaknesses": ["Extremely short response", "No sports content"],
            "recommendation": "No",
        }

        report_data = generate_json_report(empty_transcript, low_eval)
        md = generate_markdown_report(report_data)

        assert "0.6" in md
        assert "No" in md
        assert "None identified" in md  # no strengths

    def test_prepare_evaluator_input(self):
        """Test that transcriber output is correctly transformed for the evaluator."""
        result = prepare_evaluator_input(MOCK_TRANSCRIPT_DATA)

        assert result["transcript"] == MOCK_TRANSCRIPT_DATA["transcript"]
        assert result["word_count"] == 42
        assert result["duration_seconds"] == 65.0
        assert result["wpm"] == 138.5
        assert result["avg_confidence"] == 0.96
        assert result["filler_word_count"] == 1
        assert result["filler_word_rate"] == 0.024
        assert len(result["filler_words"]) == 1
        assert result["filler_words"][0]["word"] == "um"

    def test_pipeline_with_missing_metadata(self):
        """Test pipeline handles missing metadata keys gracefully."""
        minimal_transcript = {
            "transcript": "Some text here.",
            "metadata": {},
        }
        minimal_eval = {
            "communication_quality": {"score": 5.0, "justification": "Average.", "evidence": []},
            "coherence": {"score": 5.0, "justification": "Average.", "evidence": []},
            "sports_knowledge": {"score": 5.0, "justification": "Average.", "evidence": []},
            "weighted_score": 5.0,
            "strengths": ["Adequate"],
            "weaknesses": ["Nothing notable"],
            "recommendation": "Maybe",
        }

        report_data = generate_json_report(minimal_transcript, minimal_eval)
        md = generate_markdown_report(report_data)

        # Should not crash with missing metadata
        assert "5.0 / 10.0" in md
        assert "Maybe" in md
