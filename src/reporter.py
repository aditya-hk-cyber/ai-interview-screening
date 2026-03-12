"""Report generator for AI Interview Screening Tool."""

from datetime import datetime
import json
import os


def generate_json_report(transcript_data: dict, evaluation_data: dict, video_url: str = "") -> dict:
    """Combine transcript and evaluation into full report."""
    return {
        "generated_at": datetime.now().isoformat(),
        "video_url": video_url,
        "evaluation": evaluation_data,
        "transcript_stats": transcript_data.get("metadata", {}),
        "transcript": transcript_data.get("transcript", ""),
    }


def _score_bar(score: float, max_score: float = 10.0, width: int = 20) -> str:
    """Generate a unicode progress bar for a score."""
    filled = int((score / max_score) * width)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


def _star_rating(score: float, max_score: float = 10.0, stars: int = 5) -> str:
    """Generate a star visualization for a score."""
    filled = int((score / max_score) * stars)
    half = 1 if (score / max_score) * stars - filled >= 0.5 else 0
    empty = stars - filled - half
    return "\u2605" * filled + ("\u00bd" if half else "") + "\u2606" * empty


def generate_markdown_report(report_data: dict) -> str:
    """Generate human-readable markdown report."""
    eval_data = report_data.get("evaluation", {})
    stats = report_data.get("transcript_stats", {})
    transcript = report_data.get("transcript", "")

    weighted_score = eval_data.get("weighted_score", 0)
    recommendation = eval_data.get("recommendation", "N/A")
    strengths = eval_data.get("strengths", [])
    weaknesses = eval_data.get("weaknesses", [])

    rubrics = [
        ("Communication Quality", "communication_quality", "30%"),
        ("Coherence", "coherence", "30%"),
        ("Sports Knowledge", "sports_knowledge", "40%"),
    ]

    lines = []
    lines.append("# AI Interview Screening Report")
    lines.append("")
    lines.append(f"**Date:** {report_data.get('generated_at', 'N/A')}")
    if report_data.get("video_url"):
        lines.append(f"**Video:** {report_data['video_url']}")
    lines.append("")

    # Overall Score
    lines.append("---")
    lines.append("")
    lines.append("## Overall Score")
    lines.append("")
    lines.append(f"### {weighted_score:.1f} / 10.0  {_star_rating(weighted_score)}")
    lines.append("")
    lines.append(f"**Hiring Recommendation: {recommendation}**")
    lines.append("")

    # Per-rubric scores
    lines.append("---")
    lines.append("")
    lines.append("## Rubric Scores")
    lines.append("")

    for rubric_name, rubric_key, weight in rubrics:
        rubric = eval_data.get(rubric_key, {})
        score = rubric.get("score", 0)
        justification = rubric.get("justification", "N/A")
        evidence = rubric.get("evidence", [])

        lines.append(f"### {rubric_name} (Weight: {weight})")
        lines.append("")
        lines.append(f"**Score:** {score:.1f} / 10.0  {_score_bar(score)}")
        lines.append("")
        lines.append(f"**Justification:** {justification}")
        lines.append("")
        if evidence:
            lines.append("**Evidence:**")
            for e in evidence:
                lines.append(f'- "{e}"')
            lines.append("")

    # Strengths
    lines.append("---")
    lines.append("")
    lines.append("## Strengths")
    lines.append("")
    if strengths:
        for s in strengths:
            lines.append(f"- {s}")
    else:
        lines.append("- None identified")
    lines.append("")

    # Weaknesses
    lines.append("## Areas for Improvement")
    lines.append("")
    if weaknesses:
        for w in weaknesses:
            lines.append(f"- {w}")
    else:
        lines.append("- None identified")
    lines.append("")

    # Transcript Statistics
    lines.append("---")
    lines.append("")
    lines.append("## Transcript Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Duration | {stats.get('duration', 0):.1f}s |")
    lines.append(f"| Word Count | {stats.get('word_count', 0)} |")
    lines.append(f"| Words per Minute | {stats.get('words_per_minute', 0):.1f} |")
    lines.append(f"| Average Confidence | {stats.get('avg_confidence', 0):.2f} |")
    lines.append(f"| Filler Word Rate | {stats.get('filler_word_rate', 0):.3f} |")
    lines.append("")

    # Full Transcript
    lines.append("---")
    lines.append("")
    lines.append("## Full Transcript")
    lines.append("")
    lines.append("<details>")
    lines.append("<summary>Click to expand transcript</summary>")
    lines.append("")
    lines.append(transcript if transcript else "_No transcript available._")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    return "\n".join(lines)


def save_reports(report_data: dict, output_dir: str = ".", video_name: str = None) -> dict:
    """Save report.json and report.md. If video_name given, uses it as filename prefix.

    Returns {"json_path": str, "md_path": str}
    """
    from pathlib import Path

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if video_name:
        stem = Path(video_name).stem  # strip extension if present
        json_filename = f"{stem}_report.json"
        md_filename = f"{stem}_report.md"
    else:
        json_filename = "report.json"
        md_filename = "report.md"

    json_path = output_dir / json_filename
    md_path = output_dir / md_filename

    with open(json_path, "w") as f:
        json.dump(report_data, f, indent=2)

    md_content = generate_markdown_report(report_data)
    with open(md_path, "w") as f:
        f.write(md_content)

    return {"json_path": str(json_path), "md_path": str(md_path)}


def upload_reports_to_drive(local_json_path: str, local_md_path: str, folder_id: str, credentials_file: str = "ds-dream11-0eb59d82137f.json") -> dict:
    """Upload report files to a 'reports' subfolder in Drive. Returns {json_id, md_id, json_url, md_url}."""
    from src.drive_utils import get_drive_service, get_or_create_subfolder, upload_file_to_drive
    service = get_drive_service(credentials_file)
    reports_folder_id = get_or_create_subfolder(service, folder_id, "reports")

    json_id = upload_file_to_drive(service, local_json_path, reports_folder_id)
    md_id = upload_file_to_drive(service, local_md_path, reports_folder_id)

    return {
        "json_id": json_id,
        "md_id": md_id,
        "json_url": f"https://drive.google.com/file/d/{json_id}/view",
        "md_url": f"https://drive.google.com/file/d/{md_id}/view",
    }
