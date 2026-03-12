"""Tests for the Gemini evaluation engine."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.evaluator import (
    build_evaluation_prompt,
    compute_weighted_score,
    evaluate_candidate,
    get_recommendation,
    load_credentials,
    prepare_transcript_data,
)

SAMPLE_TRANSCRIPT_DATA = {
    "transcript": "I love cricket and have been following IPL since 2008. "
    "The strategic aspects of T20 cricket, especially the powerplay "
    "and death overs, fascinate me. I also follow football and NBA.",
    "word_count": 150,
    "duration_seconds": 75.0,
    "wpm": 120.0,
    "avg_confidence": 0.95,
    "filler_word_count": 3,
    "filler_word_rate": 0.02,
    "filler_words": [
        {"word": "um", "start": 5.2, "end": 5.5},
        {"word": "uh", "start": 20.1, "end": 20.3},
        {"word": "um", "start": 45.0, "end": 45.2},
    ],
}

MOCK_GEMINI_RESPONSE = {
    "communication_quality": {
        "score": 7.5,
        "justification": "Good vocabulary with minimal filler words.",
        "evidence": ["I love cricket and have been following IPL since 2008"],
    },
    "coherence": {
        "score": 8.0,
        "justification": "Well-structured response with logical flow.",
        "evidence": ["The strategic aspects of T20 cricket"],
    },
    "sports_knowledge": {
        "score": 8.5,
        "justification": "Strong domain knowledge across multiple sports.",
        "evidence": [
            "strategic aspects of T20 cricket, especially the powerplay and death overs",
            "I also follow football and NBA",
        ],
    },
    "strengths": ["Deep cricket knowledge", "Multi-sport awareness"],
    "weaknesses": ["Could elaborate more on football and NBA"],
}


class TestLoadCredentials:
    @patch("src.evaluator.service_account.Credentials.from_service_account_file")
    def test_load_credentials_default_path(self, mock_from_file):
        mock_creds = MagicMock()
        mock_from_file.return_value = mock_creds

        result = load_credentials()

        mock_from_file.assert_called_once()
        assert result == mock_creds

    @patch("src.evaluator.service_account.Credentials.from_service_account_file")
    def test_load_credentials_custom_path(self, mock_from_file):
        mock_creds = MagicMock()
        mock_from_file.return_value = mock_creds

        result = load_credentials("/custom/path.json")

        mock_from_file.assert_called_once_with(
            "/custom/path.json",
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        assert result == mock_creds


class TestBuildEvaluationPrompt:
    def test_includes_transcript(self):
        prompt = build_evaluation_prompt(SAMPLE_TRANSCRIPT_DATA)
        assert "I love cricket" in prompt
        assert "following IPL since 2008" in prompt

    def test_includes_word_count(self):
        prompt = build_evaluation_prompt(SAMPLE_TRANSCRIPT_DATA)
        assert "Word count: 150" in prompt

    def test_includes_wpm(self):
        prompt = build_evaluation_prompt(SAMPLE_TRANSCRIPT_DATA)
        assert "120.0" in prompt

    def test_includes_confidence(self):
        prompt = build_evaluation_prompt(SAMPLE_TRANSCRIPT_DATA)
        assert "0.950" in prompt

    def test_includes_filler_word_rate(self):
        prompt = build_evaluation_prompt(SAMPLE_TRANSCRIPT_DATA)
        assert "0.0200" in prompt
        assert "2.00%" in prompt

    def test_includes_filler_word_count(self):
        prompt = build_evaluation_prompt(SAMPLE_TRANSCRIPT_DATA)
        assert "Filler word count: 3" in prompt

    def test_includes_scoring_rubrics(self):
        prompt = build_evaluation_prompt(SAMPLE_TRANSCRIPT_DATA)
        assert "Communication Quality" in prompt
        assert "Coherence" in prompt
        assert "Sports Knowledge" in prompt

    def test_handles_empty_transcript(self):
        data = {
            "transcript": "",
            "word_count": 0,
            "duration_seconds": 0,
            "wpm": 0,
            "avg_confidence": 0,
            "filler_word_count": 0,
            "filler_word_rate": 0,
            "filler_words": [],
        }
        prompt = build_evaluation_prompt(data)
        assert "Word count: 0" in prompt


class TestWeightedScoreCalculation:
    def test_basic_weighted_score(self):
        scores = {
            "communication_quality": 7.5,
            "coherence": 8.0,
            "sports_knowledge": 8.5,
        }
        # 7.5*0.3 + 8.0*0.3 + 8.5*0.4 = 2.25 + 2.4 + 3.4 = 8.05
        assert compute_weighted_score(scores) == 8.05

    def test_all_tens(self):
        scores = {
            "communication_quality": 10.0,
            "coherence": 10.0,
            "sports_knowledge": 10.0,
        }
        assert compute_weighted_score(scores) == 10.0

    def test_all_zeros(self):
        scores = {
            "communication_quality": 0,
            "coherence": 0,
            "sports_knowledge": 0,
        }
        assert compute_weighted_score(scores) == 0.0

    def test_weights_sum_to_one(self):
        from src.evaluator import WEIGHTS

        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


class TestGetRecommendation:
    def test_strong_yes(self):
        assert get_recommendation(8.0) == "Strong Yes"
        assert get_recommendation(9.5) == "Strong Yes"

    def test_yes(self):
        assert get_recommendation(6.5) == "Yes"
        assert get_recommendation(7.9) == "Yes"

    def test_maybe(self):
        assert get_recommendation(5.0) == "Maybe"
        assert get_recommendation(6.4) == "Maybe"

    def test_no(self):
        assert get_recommendation(4.9) == "No"
        assert get_recommendation(0) == "No"


class TestEvaluateCandidate:
    @patch("src.evaluator.vertexai.init")
    @patch("src.evaluator.GenerativeModel")
    @patch("src.evaluator.load_credentials")
    def test_evaluate_candidate_success(
        self, mock_load_creds, mock_model_cls, mock_vertexai_init
    ):
        mock_load_creds.return_value = MagicMock()

        mock_response = MagicMock()
        mock_response.text = json.dumps(MOCK_GEMINI_RESPONSE)
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_model_cls.return_value = mock_model

        result = evaluate_candidate(SAMPLE_TRANSCRIPT_DATA)

        # Verify Vertex AI was initialized
        mock_vertexai_init.assert_called_once()

        # Verify model was created
        mock_model_cls.assert_called_once_with("gemini-2.0-flash-001")

        # Verify generate_content was called
        mock_model.generate_content.assert_called_once()

        # Check output structure
        assert "communication_quality" in result
        assert "coherence" in result
        assert "sports_knowledge" in result
        assert "weighted_score" in result
        assert "recommendation" in result
        assert "strengths" in result
        assert "weaknesses" in result

        # Check computed values
        # 7.5*0.3 + 8.0*0.3 + 8.5*0.4 = 8.05
        assert result["weighted_score"] == 8.05
        assert result["recommendation"] == "Strong Yes"

    @patch("src.evaluator.vertexai.init")
    @patch("src.evaluator.GenerativeModel")
    @patch("src.evaluator.load_credentials")
    def test_evaluate_candidate_low_scores(
        self, mock_load_creds, mock_model_cls, mock_vertexai_init
    ):
        mock_load_creds.return_value = MagicMock()

        low_score_response = {
            "communication_quality": {
                "score": 3.0,
                "justification": "Poor communication.",
                "evidence": [],
            },
            "coherence": {
                "score": 4.0,
                "justification": "Incoherent.",
                "evidence": [],
            },
            "sports_knowledge": {
                "score": 2.0,
                "justification": "No sports knowledge.",
                "evidence": [],
            },
            "strengths": [],
            "weaknesses": ["Everything"],
        }
        mock_response = MagicMock()
        mock_response.text = json.dumps(low_score_response)
        mock_model = MagicMock()
        mock_model.generate_content.return_value = mock_response
        mock_model_cls.return_value = mock_model

        result = evaluate_candidate(SAMPLE_TRANSCRIPT_DATA)

        # 3.0*0.3 + 4.0*0.3 + 2.0*0.4 = 0.9 + 1.2 + 0.8 = 2.9
        assert result["weighted_score"] == 2.9
        assert result["recommendation"] == "No"


class TestPrepareTranscriptData:
    """Test that raw transcription pipeline output is correctly mapped."""

    RAW_TRANSCRIPTION = {
        "transcript": "I love cricket and fantasy sports.",
        "words": [
            {"word": "I", "start": 0.0, "end": 0.1, "confidence": 0.99},
            {"word": "love", "start": 0.2, "end": 0.4, "confidence": 0.98},
        ],
        "utterances": [
            {"transcript": "I love cricket and fantasy sports.", "start": 0.0, "end": 3.5},
        ],
        "filler_words": {
            "count": 2,
            "instances": [
                {"word": "um", "start": 0.6, "end": 0.8},
                {"word": "uh", "start": 2.1, "end": 2.3},
            ],
        },
        "metadata": {
            "duration": 60.0,
            "word_count": 11,
            "words_per_minute": 11.0,
            "avg_confidence": 0.9573,
            "filler_word_rate": 0.1818,
        },
    }

    def test_maps_transcript(self):
        result = prepare_transcript_data(self.RAW_TRANSCRIPTION)
        assert result["transcript"] == "I love cricket and fantasy sports."

    def test_maps_metadata_fields(self):
        result = prepare_transcript_data(self.RAW_TRANSCRIPTION)
        assert result["word_count"] == 11
        assert result["duration_seconds"] == 60.0
        assert result["wpm"] == 11.0
        assert result["avg_confidence"] == 0.9573

    def test_maps_filler_words(self):
        result = prepare_transcript_data(self.RAW_TRANSCRIPTION)
        assert result["filler_word_count"] == 2
        assert result["filler_word_rate"] == 0.1818
        assert len(result["filler_words"]) == 2
        assert result["filler_words"][0]["word"] == "um"

    def test_handles_missing_metadata(self):
        raw = {"transcript": "Hello"}
        result = prepare_transcript_data(raw)
        assert result["transcript"] == "Hello"
        assert result["word_count"] == 0
        assert result["filler_word_count"] == 0
        assert result["filler_words"] == []

    def test_output_compatible_with_build_prompt(self):
        result = prepare_transcript_data(self.RAW_TRANSCRIPTION)
        prompt = build_evaluation_prompt(result)
        assert "I love cricket" in prompt
        assert "Word count: 11" in prompt
        assert "11.0" in prompt
