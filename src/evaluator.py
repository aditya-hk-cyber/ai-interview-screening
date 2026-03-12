"""Gemini Evaluation Engine for AI Interview Screening.

Uses Gemini 2.0 Flash via Vertex AI to evaluate candidate interview transcripts
on communication quality, coherence, and sports knowledge.
"""

import json
import os

import vertexai
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel, GenerationConfig

# Path to service account credentials relative to project root
DEFAULT_CREDENTIALS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ds-dream11-0eb59d82137f.json",
)

VERTEX_PROJECT = "ds-dream11"
VERTEX_LOCATION = "us-central1"
MODEL_NAME = "gemini-2.0-flash-001"

# Scoring weights
WEIGHTS = {
    "communication_quality": 0.3,
    "coherence": 0.3,
    "sports_knowledge": 0.4,
}

# Recommendation thresholds
RECOMMENDATION_THRESHOLDS = [
    (8.0, "Strong Yes"),
    (6.5, "Yes"),
    (5.0, "Maybe"),
]
DEFAULT_RECOMMENDATION = "No"


def load_credentials(json_file=None):
    """Load Google service account credentials for Vertex AI."""
    path = json_file or DEFAULT_CREDENTIALS_PATH
    credentials = service_account.Credentials.from_service_account_file(
        path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return credentials


def prepare_transcript_data(raw_transcription: dict) -> dict:
    """Map the transcription pipeline output to the format expected by the evaluator.

    The transcription pipeline (src/transcription.py) returns a dict with nested
    'metadata' and 'filler_words' keys. This function flattens it into the format
    that build_evaluation_prompt expects.

    Args:
        raw_transcription: Dict from transcribe_audio() with keys: transcript,
            words, utterances, filler_words, metadata.

    Returns:
        Flattened dict with keys: transcript, word_count, duration_seconds,
        wpm, avg_confidence, filler_word_count, filler_word_rate, filler_words.
    """
    metadata = raw_transcription.get("metadata", {})
    filler_data = raw_transcription.get("filler_words", {})
    return {
        "transcript": raw_transcription.get("transcript", ""),
        "word_count": metadata.get("word_count", 0),
        "duration_seconds": metadata.get("duration", 0),
        "wpm": metadata.get("words_per_minute", 0),
        "avg_confidence": metadata.get("avg_confidence", 0),
        "filler_word_count": filler_data.get("count", 0),
        "filler_word_rate": metadata.get("filler_word_rate", 0),
        "filler_words": filler_data.get("instances", []),
    }


def build_evaluation_prompt(transcript_data: dict) -> str:
    """Build the evaluation prompt including transcript text and metadata.

    Args:
        transcript_data: Dict with keys like 'transcript', 'word_count',
            'duration_seconds', 'wpm', 'avg_confidence', 'filler_word_count',
            'filler_word_rate', 'filler_words'.
    """
    transcript = transcript_data.get("transcript", "")
    word_count = transcript_data.get("word_count", 0)
    duration = transcript_data.get("duration_seconds", 0)
    wpm = transcript_data.get("wpm", 0)
    avg_confidence = transcript_data.get("avg_confidence", 0)
    filler_word_count = transcript_data.get("filler_word_count", 0)
    filler_word_rate = transcript_data.get("filler_word_rate", 0)
    filler_words = transcript_data.get("filler_words", [])

    prompt = f"""You are an expert interview evaluator for a sports analytics company (Dream11).
Evaluate the following candidate interview transcript and metadata.

## Transcript
{transcript}

## Speech Metadata
- Word count: {word_count}
- Duration: {duration:.1f} seconds
- Words per minute (WPM): {wpm:.1f}
- Average speech confidence: {avg_confidence:.3f}
- Filler word count: {filler_word_count}
- Filler word rate: {filler_word_rate:.4f} ({filler_word_rate * 100:.2f}%)
- Filler words detected: {json.dumps(filler_words)}

## Scoring Rubrics

### 1. Communication Quality (30% weight) — score 0-10
- Vocabulary richness and sentence variety
- Filler word frequency: >5% rate is poor, <2% is excellent
- Clarity and confidence: avg_confidence > 0.95 is excellent, < 0.85 is poor
- Speaking pace: 120-160 WPM is ideal; too slow (<100) or too fast (>180) loses points

### 2. Coherence (30% weight) — score 0-10
- Logical flow of the response
- Does the candidate stay on topic?
- Are ideas structured with a clear beginning, middle, and conclusion?

### 3. Sports Knowledge (40% weight) — score 0-10
- Depth of domain knowledge (rules, teams, players, stats, trends)
- Ability to reason about sports scenarios
- Coverage of mainstream and niche sports topics

## Output Format
Return ONLY valid JSON with this exact structure (no markdown, no code fences):
{{
  "communication_quality": {{
    "score": <0-10 float>,
    "justification": "<explanation>",
    "evidence": ["<quote from transcript>", ...]
  }},
  "coherence": {{
    "score": <0-10 float>,
    "justification": "<explanation>",
    "evidence": ["<quote from transcript>", ...]
  }},
  "sports_knowledge": {{
    "score": <0-10 float>,
    "justification": "<explanation>",
    "evidence": ["<quote from transcript>", ...]
  }},
  "strengths": ["<strength>", ...],
  "weaknesses": ["<weakness>", ...]
}}"""
    return prompt


def compute_weighted_score(scores: dict) -> float:
    """Compute the weighted score from individual rubric scores."""
    return round(
        scores.get("communication_quality", 0) * WEIGHTS["communication_quality"]
        + scores.get("coherence", 0) * WEIGHTS["coherence"]
        + scores.get("sports_knowledge", 0) * WEIGHTS["sports_knowledge"],
        2,
    )


def get_recommendation(weighted_score: float) -> str:
    """Return a recommendation string based on weighted score."""
    for threshold, label in RECOMMENDATION_THRESHOLDS:
        if weighted_score >= threshold:
            return label
    return DEFAULT_RECOMMENDATION


def evaluate_candidate(transcript_data: dict, credentials_path: str = None) -> dict:
    """Evaluate a candidate using Gemini 2.0 Flash via Vertex AI.

    Args:
        transcript_data: Dict containing transcript text and Deepgram metadata.
        credentials_path: Optional path to service account JSON.

    Returns:
        Evaluation dict with per-rubric scores, weighted score, strengths,
        weaknesses, and recommendation.
    """
    credentials = load_credentials(credentials_path)
    vertexai.init(
        project=VERTEX_PROJECT,
        location=VERTEX_LOCATION,
        credentials=credentials,
    )

    model = GenerativeModel(MODEL_NAME)
    prompt = build_evaluation_prompt(transcript_data)

    generation_config = GenerationConfig(
        response_mime_type="application/json",
        temperature=0.2,
    )

    response = model.generate_content(prompt, generation_config=generation_config)
    raw_text = response.text.strip()

    evaluation = json.loads(raw_text)

    # Extract scores and compute weighted score + recommendation
    scores = {
        "communication_quality": float(evaluation["communication_quality"]["score"]),
        "coherence": float(evaluation["coherence"]["score"]),
        "sports_knowledge": float(evaluation["sports_knowledge"]["score"]),
    }
    weighted = compute_weighted_score(scores)
    recommendation = get_recommendation(weighted)

    evaluation["weighted_score"] = weighted
    evaluation["recommendation"] = recommendation

    return evaluation
