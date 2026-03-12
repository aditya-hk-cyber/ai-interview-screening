

export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

**Step 2: Start a new `claude` session and paste this prompt:**
```
I want to build an AI Interview Screening tool that evaluates a 60–90 SECOND 
video from Google Drive and scores candidates. 

API Keys:
- Gemini API key: stored in a JSON file in this project folder — find it ds-dream11-0eb59d82137f.json
- Deepgram API key: stored in a file called "DeepGram" in this project folder — read it

Create an agent team with 3 teammates to build this in parallel:

## Teammate 1: Video & Transcription Pipeline
- Download video from Google Drive https://drive.google.com/drive/folders/1ZVNMIkdEJrbRTyusSL2aOjm-v7AmSy9S using gdown
- Extract audio using ffmpeg
- Transcribe audio using Deepgram API (Nova-2 model) — the API key is in 
  the file named "DeepGram" in this folder
- Deepgram should return: transcript text, word-level timestamps, 
  filler word detection (um/uh), confidence scores
- Output: clean transcript as JSON with timestamps + metadata

## Teammate 2: Gemini Evaluation Engine  
- Build Gemini API integration using google-generativeai SDK
- Find and read the Gemini API key from the JSON file in this project folder
- Design structured evaluation prompts for three scoring rubrics:

  1. **Communication Quality (30% weight)** — score out of 10
     - Vocabulary richness and sentence variety  
     - Filler word frequency (use Deepgram's filler word data)
     - Clarity and confidence (from Deepgram confidence scores)
     - Speaking pace (words per minute from timestamps)
  
  2. **Coherence (30% weight)** — score out of 10
     - Logical flow of the response
     - Does the candidate stay on topic?
     - Are ideas structured with clear beginning and conclusion?
  
  3. **Sports Knowledge (40% weight)** — score out of 10
     - Depth of domain knowledge (rules, teams, players, stats, trends)
     - Ability to reason about sports scenarios
     - Coverage of mainstream and niche sports topics

- Use Gemini 2.0 Flash for evaluation
- Pass BOTH the transcript AND Deepgram metadata (filler counts, 
  confidence, pace) to Gemini for richer evaluation
- Output: structured JSON with per-rubric scores + evidence quotes

## Teammate 3: Report Generator, CLI & Tests
- Build CLI: `python evaluate.py --video-url <gdrive_url>`
- Generate `report.json` — machine-readable scores + evidence
- Generate `report.md` — human-readable report with:
  - Overall weighted score out of 10
  - Per-rubric scores with justification and evidence quotes
  - Strengths and weaknesses
  - Hiring recommendation: Strong Yes / Yes / Maybe / No
  - Transcript stats (word count, duration, filler %, avg confidence)
- Add progress indicators for each pipeline step
- Write unit tests for each module
- Handle edge cases: private videos, API failures, empty transcript
- Write README.md with setup and usage instructions

## Coordination Rules
- Use Sonnet for all teammates
- Teammates must communicate interface contracts with each other 
  (e.g., Teammate 1 shares the Deepgram output schema with Teammate 2)
- Require plan approval before implementation begins
- Python 3.11+, clean modular project structure
- All API keys loaded from files in this folder — never hardcoded
- Install dependencies: gdown, deepgram-sdk, google-generativeai, ffmpeg-python