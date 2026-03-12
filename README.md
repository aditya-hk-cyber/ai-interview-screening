# AI Interview Screening Tool

Evaluates 60-90 second interview videos and scores candidates on Communication, Coherence, and Sports Knowledge.

## Prerequisites

- Python 3.11+
- ffmpeg: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)
- Google Cloud project with Vertex AI API enabled
- Deepgram account

## Setup

1. Clone/download this project
2. Place API key files in the project directory:
   - `DeepGram`: Deepgram API key (first line)
   - `ds-dream11-0eb59d82137f.json`: Google Service Account JSON
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Evaluate from Google Drive URL:
```bash
python evaluate.py --video-url "https://drive.google.com/drive/folders/YOUR_FOLDER_ID"
```

Evaluate a local video:
```bash
python evaluate.py --video-path /path/to/video.mp4
```

Specify output directory:
```bash
python evaluate.py --video-url "https://..." --output-dir ./results
```

## Output

- `report.json`: Machine-readable full report with scores, evidence, and transcript
- `report.md`: Human-readable report with visual score bars, justifications, and recommendation

## Scoring Rubrics

| Rubric | Weight | Criteria |
|--------|--------|----------|
| Communication Quality | 30% | Vocabulary, filler words, confidence, pace |
| Coherence | 30% | Logical flow, topic focus, structure |
| Sports Knowledge | 40% | Domain depth, reasoning, breadth |

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
.
├── evaluate.py              # CLI entry point
├── src/
│   ├── __init__.py
│   ├── transcription.py     # Video download + audio extraction + Deepgram transcription
│   ├── evaluator.py         # Gemini-based candidate evaluation
│   └── reporter.py          # Report generation (JSON + Markdown)
├── tests/
│   ├── __init__.py
│   ├── test_reporter.py     # Unit tests for reporter
│   └── test_integration.py  # Integration tests with mocked pipeline
├── requirements.txt
└── README.md
```
