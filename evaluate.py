#!/usr/bin/env python3
"""AI Interview Screening Tool - CLI entry point."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))

from src.transcription import process_video, load_api_key
from src.evaluator import evaluate_candidate
from src.reporter import generate_json_report, generate_markdown_report, save_reports

console = Console()


def prepare_evaluator_input(transcript_data: dict) -> dict:
    """Transform transcriber output into the flat format the evaluator expects."""
    metadata = transcript_data.get("metadata", {})
    filler_info = transcript_data.get("filler_words", {})
    return {
        "transcript": transcript_data.get("transcript", ""),
        "word_count": metadata.get("word_count", 0),
        "duration_seconds": metadata.get("duration", 0.0),
        "wpm": metadata.get("words_per_minute", 0.0),
        "avg_confidence": metadata.get("avg_confidence", 0.0),
        "filler_word_count": filler_info.get("count", 0),
        "filler_word_rate": metadata.get("filler_word_rate", 0.0),
        "filler_words": filler_info.get("instances", []),
    }


@click.command()
@click.option("--video-url", help="Google Drive URL of the video")
@click.option("--video-path", type=click.Path(exists=True), help="Local path to video file")
@click.option("--output-dir", default=".", help="Directory to save reports")
def main(video_url, video_path, output_dir):
    """AI Interview Screening Tool - evaluates candidate videos and scores them."""
    if not video_url and not video_path:
        console.print("[red]Error: Provide --video-url or --video-path[/red]")
        sys.exit(1)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Process video (download/locate, extract audio, transcribe)
            task = progress.add_task("Processing video and transcribing audio...", total=None)
            source = video_url if video_url else video_path
            transcript_data = process_video(source)
            progress.update(task, description="[green]Transcription complete!")

            # Check for empty transcript
            word_count = transcript_data.get("metadata", {}).get("word_count", 0)
            if word_count < 10:
                console.print(
                    f"[yellow]Warning: Transcript has only {word_count} words. "
                    "Results may be unreliable.[/yellow]"
                )

            # Step 2: Evaluate candidate
            progress.update(task, description="Evaluating candidate with Gemini AI...")
            evaluator_input = prepare_evaluator_input(transcript_data)
            evaluation_data = evaluate_candidate(evaluator_input)
            progress.update(task, description="[green]Evaluation complete!")

            # Step 3: Generate reports
            progress.update(task, description="Generating reports...")
            report_data = generate_json_report(
                transcript_data, evaluation_data, video_url=video_url or video_path or ""
            )
            json_path, md_path = save_reports(report_data, output_dir)
            progress.update(task, description="[green]Reports generated!")

        # Print summary
        console.print()
        console.print("[bold green]Evaluation Complete![/bold green]")
        console.print()

        weighted_score = evaluation_data.get("weighted_score", 0)
        recommendation = evaluation_data.get("recommendation", "N/A")
        console.print(f"  [bold]Overall Score:[/bold] {weighted_score:.1f} / 10.0")
        console.print(f"  [bold]Recommendation:[/bold] {recommendation}")
        console.print()
        console.print(f"  Reports saved to:")
        console.print(f"    JSON: {json_path}")
        console.print(f"    Markdown: {md_path}")

    except FileNotFoundError as e:
        console.print(f"[red]File not found: {e}[/red]")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Invalid input: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
