from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import typer

from auv_intel_digest.pipeline import run_digest
from auv_intel_digest.scheduled_digest import run_scheduled_digest
from auv_intel_digest.settings import Settings

app = typer.Typer(help="Daily AUV/UUV research intelligence digest.")


@app.command()
def run(
    report_date: Optional[str] = typer.Option(
        None, "--date", help="Report date in YYYY-MM-DD. Defaults to today in TIMEZONE."
    ),
) -> None:
    settings = Settings.load()
    parsed_date = date.fromisoformat(report_date) if report_date else None
    paths = run_digest(settings, parsed_date)
    for kind, path in paths.items():
        typer.echo(f"{kind}: {path}")


@app.command("test-notifier")
def test_notifier() -> None:
    settings = Settings.load()
    typer.echo(f"NOTIFIER_MODE={settings.notifier_mode}")
    typer.echo("file_only notifier is available.")


def _run_collect_command(
    *,
    sources: Path,
    output: Path,
    limit: int,
    include_seen: bool,
    state: Path,
    language: str,
    summarizer: str,
    llm_model: Optional[str],
) -> None:
    result = run_scheduled_digest(
        sources_path=sources,
        output_path=output,
        limit=limit,
        include_seen=include_seen,
        state_path=state,
        language=language,
        summarizer_name=summarizer,
        llm_model=llm_model,
    )
    typer.echo(f"Sources checked: {result.sources_checked}")
    typer.echo(f"Successful: {result.successful}")
    typer.echo(f"Failed: {result.failed}")
    typer.echo(f"New items: {result.new_items}")
    typer.echo(f"Language: {result.language}")
    typer.echo(f"Summarizer: {result.summarizer_name}")
    typer.echo(f"Output: {result.output_path}")


@app.command("collect")
def collect(
    sources: Path = typer.Option(
        Path("examples/sources.example.json"),
        "--sources",
        help="JSON file containing RSS/Atom sources.",
    ),
    output: Path = typer.Option(
        Path("digests/latest.md"),
        "--output",
        help="Markdown digest output path.",
    ),
    limit: int = typer.Option(30, "--limit", min=1, help="Maximum items to write."),
    include_seen: bool = typer.Option(
        False,
        "--include-seen",
        help="Include items already recorded in the local state file.",
    ),
    state: Path = typer.Option(
        Path(".auv_intel_digest/state.json"),
        "--state",
        help="Local JSON state file used to avoid repeated items.",
    ),
    language: str = typer.Option("en", "--language", help="Digest language: en or zh."),
    summarizer: str = typer.Option("noop", "--summarizer", help="Summarizer: noop or openai."),
    llm_model: Optional[str] = typer.Option(
        None,
        "--llm-model",
        help="Optional LLM model name. Defaults to AUV_INTEL_LLM_MODEL for OpenAI.",
    ),
) -> None:
    _run_collect_command(
        sources=sources,
        output=output,
        limit=limit,
        include_seen=include_seen,
        state=state,
        language=language,
        summarizer=summarizer,
        llm_model=llm_model,
    )


@app.command("scheduled-digest")
def scheduled_digest(
    sources: Path = typer.Option(
        Path("examples/sources.example.json"),
        "--sources",
        help="JSON file containing RSS/Atom sources.",
    ),
    output: Path = typer.Option(
        Path("digests/latest.md"),
        "--output",
        help="Markdown digest output path.",
    ),
    limit: int = typer.Option(30, "--limit", min=1, help="Maximum items to write."),
    include_seen: bool = typer.Option(
        False,
        "--include-seen",
        help="Include items already recorded in the local state file.",
    ),
    state: Path = typer.Option(
        Path(".auv_intel_digest/state.json"),
        "--state",
        help="Local JSON state file used to avoid repeated items.",
    ),
    language: str = typer.Option("en", "--language", help="Digest language: en or zh."),
    summarizer: str = typer.Option("noop", "--summarizer", help="Summarizer: noop or openai."),
    llm_model: Optional[str] = typer.Option(
        None,
        "--llm-model",
        help="Optional LLM model name. Defaults to AUV_INTEL_LLM_MODEL for OpenAI.",
    ),
) -> None:
    _run_collect_command(
        sources=sources,
        output=output,
        limit=limit,
        include_seen=include_seen,
        state=state,
        language=language,
        summarizer=summarizer,
        llm_model=llm_model,
    )
