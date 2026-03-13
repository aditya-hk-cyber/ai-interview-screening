#!/bin/bash

PROJECT_DIR="/Users/adityakumaraswamy/Downloads/AI interviewer Screening"
PYTHON="/Users/adityakumaraswamy/.pyenv/versions/3.12.5/bin/python"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/screening.log"
DRIVE_URL="https://drive.google.com/drive/folders/1ZVNMIkdEJrbRTyusSL2aOjm-v7AmSy9S"

mkdir -p "$LOG_DIR"

echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "Run started: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"
"$PYTHON" evaluate.py --video-url "$DRIVE_URL" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Run completed successfully: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    osascript -e 'display notification "Check the latest report in the project folder." with title "AI Screening Done ✅"'
else
    echo "Run FAILED with exit code $EXIT_CODE: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    osascript -e 'display notification "Check logs/screening.log for details." with title "AI Screening Failed ❌"'
fi
