"""Unit tests for the report generator."""

import json
import os
import tempfile

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reporter import generate_json_report, generate_markdown_report, save_reports


@pytest.fixture
def sample_transcript_data():
    return {
        "transcript": "I love sports because they teach discipline and teamwork.",
        "words": [
            {"word": "I", "start": 0.1, "end": 0.2, "confidence": 0.99},
            {"word": "love", "start": 0.3, "end": 0.5, "confidence": 0.98},
        ],
        "utterances": [
            {"transcript": "I love sports because they teach discipline and teamwork.", "start": 0.0, "end": 3.5}
        ],
        "filler_words": {"count": 0, "instances": []},
        "metadata": {
            "duration": 75.0,
            "word_count": 10,
            "words_per_minute": 144.0,
            "avg_confidence": 0.95,
            "filler_word_rate": 0.0,
        },
    }


@pytest.fixture
def sample_evaluation_data():
    return {
        "communication_quality": {
            "score": 7.5,
            "justification": "Clear and confident delivery.",
            "evidence": ["Good vocabulary usage", "Minimal filler words"],
        },
        "coherence": {
            "score": 8.0,
            "justification": "Logical flow with clear structure.",
            "evidence": ["Well-organized response"],
        },
        "sports_knowledge": {
            "score": 6.5,
            "justification": "Decent understanding of sports concepts.",
            "evidence": ["Mentioned teamwork and discipline"],
        },
        "weighted_score": 7.25,
        "strengths": ["Clear articulation", "Good sports depth"],
        "weaknesses": ["Occasional filler words"],
        "recommendation": "Yes",
    }


class TestGenerateJsonReport:
    def test_generate_json_report(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data, video_url="https://example.com/video")

        assert "generated_at" in report
        assert report["video_url"] == "https://example.com/video"
        assert report["evaluation"] == sample_evaluation_data
        assert report["transcript_stats"] == sample_transcript_data["metadata"]
        assert report["transcript"] == sample_transcript_data["transcript"]

    def test_generate_json_report_no_url(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        assert report["video_url"] == ""

    def test_generate_json_report_empty_metadata(self, sample_evaluation_data):
        transcript_data = {"transcript": "Hello", "metadata": {}}
        report = generate_json_report(transcript_data, sample_evaluation_data)
        assert report["transcript_stats"] == {}
        assert report["transcript"] == "Hello"


class TestGenerateMarkdownReport:
    def test_has_title(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        md = generate_markdown_report(report)
        assert "# AI Interview Screening Report" in md

    def test_has_overall_score(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        md = generate_markdown_report(report)
        assert "7.2" in md  # weighted_score 7.25

    def test_has_recommendation(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        md = generate_markdown_report(report)
        assert "Hiring Recommendation: Yes" in md

    def test_has_rubric_sections(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        md = generate_markdown_report(report)
        assert "Communication Quality" in md
        assert "Coherence" in md
        assert "Sports Knowledge" in md

    def test_has_strengths_and_weaknesses(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        md = generate_markdown_report(report)
        assert "## Strengths" in md
        assert "Clear articulation" in md
        assert "## Areas for Improvement" in md
        assert "Occasional filler words" in md

    def test_has_transcript_stats(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        md = generate_markdown_report(report)
        assert "Transcript Statistics" in md
        assert "75.0s" in md
        assert "144.0" in md

    def test_has_full_transcript(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        md = generate_markdown_report(report)
        assert "Full Transcript" in md
        assert "I love sports" in md

    def test_markdown_with_zero_scores(self):
        transcript_data = {
            "transcript": "",
            "metadata": {
                "duration": 0.0,
                "word_count": 0,
                "words_per_minute": 0.0,
                "avg_confidence": 0.0,
                "filler_word_rate": 0.0,
            },
        }
        evaluation_data = {
            "communication_quality": {"score": 0.0, "justification": "No speech detected.", "evidence": []},
            "coherence": {"score": 0.0, "justification": "No content.", "evidence": []},
            "sports_knowledge": {"score": 0.0, "justification": "No content.", "evidence": []},
            "weighted_score": 0.0,
            "strengths": [],
            "weaknesses": [],
            "recommendation": "No",
        }
        report = generate_json_report(transcript_data, evaluation_data)
        md = generate_markdown_report(report)

        assert "0.0 / 10.0" in md
        assert "Recommendation: No" in md
        assert "None identified" in md
        assert "_No transcript available._" in md


class TestSaveReports:
    def test_save_reports_creates_files(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = save_reports(report, tmpdir)

            assert os.path.exists(json_path)
            assert os.path.exists(md_path)
            assert json_path.endswith("report.json")
            assert md_path.endswith("report.md")

            with open(json_path) as f:
                loaded = json.load(f)
            assert loaded["evaluation"]["weighted_score"] == 7.25

            with open(md_path) as f:
                content = f.read()
            assert "AI Interview Screening Report" in content

    def test_save_reports_creates_output_dir(self, sample_transcript_data, sample_evaluation_data):
        report = generate_json_report(sample_transcript_data, sample_evaluation_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "sub", "dir")
            json_path, md_path = save_reports(report, nested)
            assert os.path.exists(json_path)
            assert os.path.exists(md_path)
