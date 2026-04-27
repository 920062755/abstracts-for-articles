from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import typer

from auv_intel_digest.notifiers.telegram import send_markdown_file_via_telegram
from auv_intel_digest.pipeline import run_digest
from auv_intel_digest.scheduled_digest import (
    all_sources_failed,
    check_feed_sources,
    load_feed_sources,
    run_scheduled_digest,
    run_status_zh,
)
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
    fail_on_all_source_errors: bool,
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
        fail_on_all_source_errors=fail_on_all_source_errors,
    )
    typer.echo(f"Sources checked: {result.sources_checked}")
    typer.echo(f"Successful: {result.successful}")
    typer.echo(f"Failed: {result.failed}")
    typer.echo(f"New items: {result.new_items}")
    typer.echo(f"Language: {result.language}")
    typer.echo(f"Summarizer: {result.summarizer_name}")
    typer.echo(f"All sources failed: {str(all_sources_failed(result)).lower()}")
    typer.echo(f"Run status: {run_status_zh(result)}")
    typer.echo(f"Output: {result.output_path}")
    if fail_on_all_source_errors and all_sources_failed(result):
        raise typer.Exit(code=2)


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
    fail_on_all_source_errors: bool = typer.Option(
        False,
        "--fail-on-all-source-errors",
        help="Exit with code 2 when every enabled source fails. Digest is still written.",
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
        fail_on_all_source_errors=fail_on_all_source_errors,
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
    fail_on_all_source_errors: bool = typer.Option(
        False,
        "--fail-on-all-source-errors",
        help="Exit with code 2 when every enabled source fails. Digest is still written.",
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
        fail_on_all_source_errors=fail_on_all_source_errors,
    )


@app.command("check-sources")
def check_sources(
    sources: Path = typer.Option(
        Path("examples/sources.example.json"),
        "--sources",
        help="JSON file containing RSS/Atom sources.",
    ),
    timeout: float = typer.Option(20.0, "--timeout", help="HTTP timeout in seconds."),
) -> None:
    diagnostics = check_feed_sources(
        load_feed_sources(sources),
        timeout=timeout,
        user_agent="auv_intel_digest/0.4 check-sources",
    )
    for diagnostic in diagnostics:
        typer.echo(f"Name: {diagnostic.name}")
        typer.echo(f"URL: {diagnostic.url}")
        typer.echo(f"Enabled: {str(diagnostic.enabled).lower()}")
        typer.echo(f"Category: {diagnostic.category or ''}")
        typer.echo(f"HTTP status: {diagnostic.http_status or ''}")
        typer.echo(f"Content-Type: {diagnostic.content_type or ''}")
        typer.echo(f"Bytes: {diagnostic.byte_count}")
        typer.echo(f"Parseable RSS/Atom: {str(diagnostic.parseable).lower()}")
        typer.echo(f"Item count: {diagnostic.item_count}")
        typer.echo(f"Error type: {diagnostic.error_type or ''}")
        typer.echo(f"Error message: {diagnostic.error_message or ''}")
        typer.echo(f"Diagnostic: {diagnostic.diagnostic or ''}")
        typer.echo("")

    successful = sum(1 for item in diagnostics if item.enabled and item.parseable)
    failed = sum(1 for item in diagnostics if item.enabled and item.error_type)
    typer.echo(f"Checked: {len(diagnostics)}")
    typer.echo(f"Successful: {successful}")
    typer.echo(f"Failed: {failed}")


@app.command("send-telegram")
def send_telegram(
    markdown: Path = typer.Option(
        Path("digests/latest.zh.md"),
        "--markdown",
        help="Markdown digest file to send.",
    ),
    title: str = typer.Option("AUV 情报摘要", "--title", help="Telegram message title."),
    json_path: Optional[Path] = typer.Option(
        None,
        "--json",
        help="Optional JSON digest path shown in the Telegram message.",
    ),
    html_path: Optional[Path] = typer.Option(
        None,
        "--html",
        help="Optional HTML digest path shown in the Telegram message.",
    ),
    max_chars: Optional[int] = typer.Option(
        None,
        "--max-chars",
        help="Maximum characters per Telegram message chunk. Defaults to TELEGRAM_MAX_CHARS.",
    ),
) -> None:
    chunks = send_markdown_file_via_telegram(
        markdown_path=markdown,
        title=title,
        json_path=json_path,
        html_path=html_path,
        max_chars=max_chars,
    )
    typer.echo(f"Telegram: sent {chunks} message chunk(s)")
