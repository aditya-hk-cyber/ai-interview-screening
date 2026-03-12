#!/usr/bin/env python3
"""AI Interview Screening Tool - CLI entry point."""

import sys
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

sys.path.insert(0, str(Path(__file__).parent))

from src.transcription import (
    process_video,
    load_api_key,
    download_video_by_id,
    extract_audio,
    transcribe_audio,
    _extract_folder_id,
)
from src.evaluator import evaluate_candidate
from src.reporter import (
    generate_json_report,
    generate_markdown_report,
    save_reports,
    upload_reports_to_drive,
)
from src.drive_utils import (
    get_drive_service,
    load_tracking_file,
    save_tracking_file,
    get_unevaluated_videos,
    mark_video_evaluated,
)

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


def _print_evaluation_summary(tracking_data: dict):
    """Print a table of all evaluated videos."""
    evaluated = tracking_data.get("evaluated", {})
    if not evaluated:
        return
    console.print("\n[bold]Evaluation History:[/bold]")
    for file_id, info in evaluated.items():
        score = info.get("overall_score", "?")
        rec = info.get("recommendation", "?")
        name = info.get("filename", file_id)
        date = info.get("evaluated_at", "")[:10]
        console.print(f"  [dim]{date}[/dim]  {name:<40} Score: [bold]{score}[/bold]  → {rec}")


def _process_folder_url(video_url: str, output_dir: str, no_upload: bool):
    """Process a Google Drive folder URL with incremental tracking."""
    folder_id = _extract_folder_id(video_url)
    service = get_drive_service()

    # Load tracking data from Drive
    console.print("[dim]Loading evaluation history from Drive...[/dim]")
    tracking_data = load_tracking_file(service, folder_id)
    already_evaluated = len(tracking_data.get("evaluated", {}))

    # Get unevaluated videos
    new_videos = get_unevaluated_videos(service, folder_id, tracking_data)

    if not new_videos:
        console.print(
            f"[green]All videos already evaluated ({already_evaluated} total). Nothing to do.[/green]"
        )
        _print_evaluation_summary(tracking_data)
        return

    console.print(
        f"[cyan]Found {len(new_videos)} new video(s) to evaluate "
        f"({already_evaluated} already done)[/cyan]"
    )

    # Process each new video
    for i, video_info in enumerate(new_videos, 1):
        video_name = video_info["name"]
        video_id = video_info["id"]

        console.print(f"\n[bold]Video {i}/{len(new_videos)}: {video_name}[/bold]")

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    # Download this specific video by file ID
                    task = progress.add_task(
                        f"Downloading {video_name}...", total=None
                    )
                    video_path = download_video_by_id(
                        service, video_id, video_name, tmp_dir
                    )
                    progress.update(task, description="[green]Downloaded!")

                    # Extract audio and transcribe
                    progress.update(
                        task, description="Extracting audio and transcribing..."
                    )
                    audio_path = extract_audio(video_path, output_dir=tmp_dir)
                    transcript_data = transcribe_audio(audio_path)
                    progress.update(
                        task, description="[green]Transcription complete!"
                    )

                    # Check for empty transcript
                    word_count = transcript_data.get("metadata", {}).get(
                        "word_count", 0
                    )
                    if word_count < 10:
                        console.print(
                            f"[yellow]Warning: Transcript has only {word_count} words. "
                            "Results may be unreliable.[/yellow]"
                        )

                    # Evaluate candidate
                    progress.update(
                        task, description="Evaluating candidate with Gemini AI..."
                    )
                    evaluator_input = prepare_evaluator_input(transcript_data)
                    evaluation_data = evaluate_candidate(evaluator_input)
                    progress.update(
                        task, description="[green]Evaluation complete!"
                    )

                    # Generate reports (named after video)
                    progress.update(task, description="Generating reports...")
                    report_data = generate_json_report(
                        transcript_data, evaluation_data, video_url=video_url
                    )
                    paths = save_reports(
                        report_data, output_dir, video_name=video_name
                    )
                    json_path = paths["json_path"]
                    md_path = paths["md_path"]
                    progress.update(
                        task, description="[green]Reports generated!"
                    )

                    # Upload reports to Drive
                    report_json_id = None
                    report_md_id = None
                    if not no_upload:
                        progress.update(
                            task,
                            description="Uploading reports to Google Drive...",
                        )
                        try:
                            drive_urls = upload_reports_to_drive(
                                json_path, md_path, folder_id
                            )
                            report_json_id = drive_urls.get("json_id")
                            report_md_id = drive_urls.get("md_id")
                            progress.update(
                                task,
                                description="[green]Reports uploaded to Drive!",
                            )
                        except Exception:
                            progress.update(
                                task,
                                description="[yellow]Drive upload skipped (use a Shared Drive to enable uploads)",
                            )

            # Mark as evaluated and save tracking data after each video
            weighted_score = evaluation_data.get("weighted_score", 0)
            recommendation = evaluation_data.get("recommendation", "N/A")

            tracking_data = mark_video_evaluated(
                tracking_data,
                video_id,
                video_name,
                report_json_id,
                report_md_id,
                weighted_score,
                recommendation,
            )
            save_tracking_file(service, tracking_data, folder_id)

            # Print per-video summary
            console.print(f"  [bold]Score:[/bold] {weighted_score:.1f} / 10.0")
            console.print(f"  [bold]Recommendation:[/bold] {recommendation}")
            console.print(f"  Reports: {json_path}, {md_path}")

        except Exception as e:
            console.print(f"[red]Error processing {video_name}: {e}[/red]")
            continue

    # Final summary
    console.print("\n[bold green]All new videos processed![/bold green]")
    _print_evaluation_summary(tracking_data)


def _process_single_video(video_url, video_path, output_dir, no_upload):
    """Process a single video (local file or single Drive file URL)."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Step 1: Process video
        task = progress.add_task(
            "Processing video and transcribing audio...", total=None
        )
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
        video_source = video_path or video_url or ""
        video_filename = Path(video_source).name if video_source else None
        paths = save_reports(report_data, output_dir, video_name=video_filename)
        json_path = paths["json_path"]
        md_path = paths["md_path"]
        progress.update(task, description="[green]Reports generated!")

        # Step 4: Upload reports to Drive
        drive_urls = None
        if video_url and not no_upload:
            progress.update(task, description="Uploading reports to Google Drive...")
            try:
                folder_id = _extract_folder_id(video_url)
                drive_urls = upload_reports_to_drive(json_path, md_path, folder_id)
                progress.update(
                    task, description="[green]Reports uploaded to Drive!"
                )
            except Exception:
                progress.update(
                    task,
                    description="[yellow]Drive upload skipped (use a Shared Drive to enable uploads)",
                )

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

    if drive_urls:
        console.print()
        console.print("[green]Reports uploaded to Drive:[/green]")
        console.print(f"    JSON: {drive_urls['json_url']}")
        console.print(f"    Markdown: {drive_urls['md_url']}")


@click.command()
@click.option("--video-url", help="Google Drive URL of the video or folder")
@click.option(
    "--video-path", type=click.Path(exists=True), help="Local path to video file"
)
@click.option("--output-dir", default=".", help="Directory to save reports")
@click.option(
    "--no-upload", is_flag=True, help="Skip uploading reports to Google Drive"
)
def main(video_url, video_path, output_dir, no_upload):
    """AI Interview Screening Tool - evaluates candidate videos and scores them."""
    if not video_url and not video_path:
        console.print("[red]Error: Provide --video-url or --video-path[/red]")
        sys.exit(1)

    try:
        # Folder URL -> incremental processing with tracking
        if video_url and "/folders/" in video_url:
            _process_folder_url(video_url, output_dir, no_upload)
        else:
            _process_single_video(video_url, video_path, output_dir, no_upload)

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
