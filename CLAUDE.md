# AI Interview Screening Tool — Codebase Guide

## Project Overview

An automated pipeline that evaluates 60–90 second video recordings of job candidates. Each video is transcribed and scored on three rubrics by an LLM, producing structured JSON and human-readable Markdown reports. The system runs on a schedule (twice daily via macOS launchd) and processes new videos from a Google Drive folder incrementally.

**Tech stack:** Python 3.12, Deepgram Nova-2, Gemini 2.0 Flash (Vertex AI), Google Drive API, ffmpeg, Rich, Click

---

## Architecture & Module Map

```
evaluate.py                  ← CLI entry point (Click)
│
├── src/transcription.py     ← Download video → extract audio → Deepgram transcription
├── src/evaluator.py         ← Build prompt → call Gemini 2.0 Flash → parse scores
├── src/reporter.py          ← Combine data → write JSON + Markdown → upload to Drive
├── src/drive_utils.py       ← Drive API auth, folder listing, upload, tracking state
└── src/schemas.py           ← Documents the TRANSCRIPT_SCHEMA data structure
```

---

## Data Flow

```
User (CLI / launchd)
        │
        ▼
[evaluate.py] detects mode:
  ├─ local file path   → extract audio → transcribe → evaluate → report
  ├─ Drive file URL    → download → extract audio → transcribe → evaluate → report → upload
  └─ Drive folder URL  → load tracking → filter new videos → for each: full pipeline
                                                                        ↓
                                                        update evaluated_videos.json
```

### Detailed pipeline per video:
1. `transcription.process_video()` → downloads (Drive service account or gdown fallback), runs `ffmpeg` to MP3, calls Deepgram
2. `evaluate.prepare_evaluator_input()` → maps transcript schema to evaluator format
3. `evaluator.evaluate_candidate()` → builds 149-line prompt, calls `gemini-2.0-flash-001` via Vertex AI (temp=0.2, JSON mode)
4. `reporter.generate_json_report()` + `generate_markdown_report()` → writes `{name}_report.json` + `{name}_report.md`
5. `reporter.upload_reports_to_drive()` → upserts files to `reports/` subfolder in Drive
6. `drive_utils.mark_video_evaluated()` + `save_tracking_file()` → persists tracking state

---

## Scoring System

| Rubric | Weight | Key signals |
|--------|--------|-------------|
| Communication Quality | **30%** | Filler word rate (<2% excellent, >5% poor), confidence (>0.95 excellent, <0.85 poor), pace (120–160 WPM ideal) |
| Coherence | **30%** | Logical flow, topic focus, beginning/middle/end structure |
| Sports Knowledge | **40%** | Domain depth, reasoning, breadth of knowledge |

**Weighted score** = `0.3×comm + 0.3×coherence + 0.4×sports` (rounded to 2 dp)

**Recommendation thresholds:**
- ≥8.0 → `Strong Yes`
- ≥6.5 → `Yes`
- ≥5.0 → `Maybe`
- <5.0 → `No`

---

## Key Functions Reference

### evaluate.py
| Function | Purpose |
|----------|---------|
| `main()` | Click CLI — `--video-url`, `--video-path`, `--output-dir`, `--no-upload` |
| `_process_single_video()` | Single file pipeline |
| `_process_folder_url()` | Batch pipeline with incremental tracking |
| `prepare_evaluator_input()` | Transform TRANSCRIPT_SCHEMA → evaluator format |
| `_print_evaluation_summary()` | Rich table of all evaluated videos |

### src/transcription.py
| Function | Purpose |
|----------|---------|
| `process_video(url, local_path)` | Full pipeline — returns TRANSCRIPT_SCHEMA |
| `download_video(url)` | Drive service account download, fallback to gdown |
| `download_video_by_id(file_id)` | Download by Drive file ID |
| `extract_audio(video_path)` | ffmpeg → MP3 temp file |
| `transcribe_audio(audio_path)` | POST to `api.deepgram.com/v1/listen` with Nova-2 |
| `_parse_deepgram_response(resp)` | Build TRANSCRIPT_SCHEMA from API response |

### src/evaluator.py
| Function | Purpose |
|----------|---------|
| `evaluate_candidate(transcript_data)` | Main entry — returns EVALUATION_RESULT dict |
| `build_evaluation_prompt(data)` | 149-line structured prompt with rubric definitions |
| `compute_weighted_score(rubrics)` | 30/30/40 weighted average |
| `get_recommendation(score)` | Threshold lookup |
| `load_credentials()` | Service account → Vertex AI credentials |

### src/drive_utils.py
| Function | Purpose |
|----------|---------|
| `get_drive_service()` | Build Drive API client from service account |
| `get_unevaluated_videos(folder_id, tracking)` | List videos not in tracking |
| `load_tracking_file()` | Read `evaluated_videos.json` (local first, Drive fallback) |
| `save_tracking_file(data)` | Write `evaluated_videos.json` locally |
| `mark_video_evaluated(tracking, file_id, ...)` | Add entry to tracking dict |
| `upload_file_to_drive(path, folder_id, name)` | Upsert file to Drive |
| `get_or_create_subfolder(parent_id, name)` | Get/create `reports/` subfolder |

### src/reporter.py
| Function | Purpose |
|----------|---------|
| `generate_json_report(transcript, eval, url)` | Combines all data → report dict |
| `generate_markdown_report(report)` | Renders human-readable MD with score bars |
| `save_reports(transcript, eval, output_dir, url)` | Writes both files, returns paths |
| `upload_reports_to_drive(json_path, md_path, folder_id)` | Uploads to `reports/` subfolder |

---

## Data Schemas

### TRANSCRIPT_SCHEMA (output of transcription.py)
```json
{
  "transcript": "full text string",
  "words": [{"word": "str", "start": 0.0, "end": 0.5, "confidence": 0.99}],
  "utterances": [{"transcript": "str", "start": 0.0, "end": 3.5}],
  "filler_words": {
    "count": 2,
    "instances": [{"word": "um", "start": 5.2, "end": 5.5}]
  },
  "metadata": {
    "duration": 60.0,
    "word_count": 150,
    "words_per_minute": 150.0,
    "avg_confidence": 0.95,
    "filler_word_rate": 0.013
  }
}
```

### EVALUATION_RESULT (output of evaluator.py)
```json
{
  "communication_quality": {"score": 7.5, "justification": "str", "evidence": ["str"]},
  "coherence":             {"score": 8.0, "justification": "str", "evidence": ["str"]},
  "sports_knowledge":      {"score": 8.5, "justification": "str", "evidence": ["str"]},
  "strengths": ["str"],
  "weaknesses": ["str"],
  "weighted_score": 8.05,
  "recommendation": "Strong Yes"
}
```

### evaluated_videos.json (tracking state)
```json
{
  "evaluated": {
    "<drive_file_id>": {
      "filename": "video.mp4",
      "evaluated_at": "2026-03-13T23:50:23.853516",
      "report_json_id": "<drive_file_id or null>",
      "report_md_id":  "<drive_file_id or null>",
      "overall_score": 7.05,
      "recommendation": "Yes"
    }
  }
}
```

---

## Credentials & Config

| Secret | File | Used by |
|--------|------|---------|
| Deepgram API key | `DeepGram` (plain text, line 1) | transcription.py → `Authorization: Token {key}` |
| Google Service Account | `ds-dream11-0eb59d82137f.json` | evaluator.py (Vertex AI) + drive_utils.py (Drive API) |

- **GCP Project:** `ds-dream11`
- **Vertex AI Location:** `us-central1`
- **Gemini model:** `gemini-2.0-flash-001`
- **Deepgram model:** `nova-2`
- No `.env` file — keys loaded directly from files above

Both credential files are in `.gitignore`.

---

## Scheduled Execution

Two launchd agents run `run_screening.sh` automatically:

| Job | Schedule | Log |
|-----|----------|-----|
| `com.aditya.ai-screening-morning` | Daily 9:00 AM | `logs/launchd-morning.log` |
| `com.aditya.ai-screening-evening` | Daily 6:00 PM | `logs/launchd-evening.log` |

`run_screening.sh` calls:
```bash
python evaluate.py --video-url "https://drive.google.com/drive/folders/1ZVNMIkdEJrbRTyusSL2aOjm-v7AmSy9S"
```
Uses Python at: `/Users/adityakumaraswamy/.pyenv/versions/3.12.5/bin/python`

Sends macOS notification (via `osascript`) on success or failure.

---

## Tests

```
tests/
├── test_transcription.py   # Deepgram API mocking, ffmpeg extraction, parsing
├── test_evaluator.py       # Gemini API mocking, score weighting, recommendations
├── test_reporter.py        # JSON/MD generation, file writing, edge cases
└── test_integration.py     # Full pipeline with all deps mocked
```

Run: `pytest tests/ -v`

---

## Supported Video Formats

`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.mpeg`, `.mpg`

---

## Sample Real Results (from evaluated_videos.json)

| Video | Score | Recommendation | Duration | WPM |
|-------|-------|----------------|----------|-----|
| PXL_20260312_152020439 | 3.9 | No | 25.4s | 132 |
| WhatsApp Video 2026-03-13 17:15 | 7.05 | Yes | 53.5s | 151 |
| WhatsApp Video 2026-03-13 16:53 | 5.7 | Maybe | — | — |

---

## Common Issues

- **launchd exit code 126** (current): Script not executable — run `chmod +x run_screening.sh`
- **Drive download fails**: Service account falls back to `gdown`; ensure video is publicly accessible or service account has access
- **<10 words in transcript**: Logged as warning, evaluation proceeds but may be unreliable
