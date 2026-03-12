# Transcript output schema produced by the transcription module.
# This serves as documentation for consumers of transcribe_audio() output.

TRANSCRIPT_SCHEMA = {
    "transcript": "str - full transcript text",
    "words": "list of {word, start, end, confidence}",
    "utterances": "list of {transcript, start, end}",
    "filler_words": {
        "count": "int",
        "instances": "list of {word, start, end}",
    },
    "metadata": {
        "duration": "float - seconds",
        "word_count": "int",
        "words_per_minute": "float",
        "avg_confidence": "float 0-1",
        "filler_word_rate": "float - fillers/total_words",
    },
}
