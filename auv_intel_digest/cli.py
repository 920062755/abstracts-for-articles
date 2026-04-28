from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import typer

from auv_intel_digest.notifiers.email import send_markdown_file_via_email
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
    sources: Path = typer.Option(Path("examples/sources.example.json"), "--sources"),
    output: Path = typer.Option(Path("digests/latest.md"), "--output"),
    limit: int = typer.Option(30, "--limit", min=1),
    include_seen: bool = typer.Option(False, "--include-seen"),
    state: Path = typer.Option(Path(".auv_intel_digest/state.json"), "--state"),
    language: str = typer.Option("en", "--language"),
    summarizer: str = typer.Option("noop", "--summarizer"),
    llm_model: Optional[str] = typer.Option(None, "--llm-model"),
    fail_on_all_source_errors: bool = typer.Option(False, "--fail-on-all-source-errors"),
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
    sources: Path = typer.Option(Path("examples/sources.example.json"), "--sources"),
    output: Path = typer.Option(Path("digests/latest.md"), "--output"),
    limit: int = typer.Option(30, "--limit", min=1),
    include_seen: bool = typer.Option(False, "--include-seen"),
    state: Path = typer.Option(Path(".auv_intel_digest/state.json"), "--state"),
    language: str = typer.Option("en", "--language"),
    summarizer: str = typer.Option("noop", "--summarizer"),
    llm_model: Optional[str] = typer.Option(None, "--llm-model"),
    fail_on_all_source_errors: bool = typer.Option(False, "--fail-on-all-source-errors"),
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
    sources: Path = typer.Option(Path("examples/sources.example.json"), "--sources"),
    timeout: float = typer.Option(20.0, "--timeout"),
) -> None:
    diagnostics = check_feed_sources(load_feed_sources(sources), timeout=timeout)
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


@app.command("send-email")
def send_email(
    markdown: Path = typer.Option(Path("digests/latest.zh.md"), "--markdown"),
    title: str = typer.Option("AUV 情报摘要", "--title"),
    json_path: Optional[Path] = typer.Option(None, "--json"),
    html_path: Optional[Path] = typer.Option(None, "--html"),
) -> None:
    sent = send_markdown_file_via_email(
        markdown_path=markdown,
        title=title,
        json_path=json_path,
        html_path=html_path,
    )
    if not sent:
        typer.echo("Email: skipped because SMTP settings are incomplete.")
        return
    typer.echo("Email: sent")


@app.command("send-telegram")
def send_telegram(
    markdown: Path = typer.Option(Path("digests/latest.zh.md"), "--markdown"),
    title: str = typer.Option("AUV 情报摘要", "--title"),
    json_path: Optional[Path] = typer.Option(None, "--json"),
    html_path: Optional[Path] = typer.Option(None, "--html"),
    max_chars: Optional[int] = typer.Option(None, "--max-chars"),
) -> None:
    chunks = send_markdown_file_via_telegram(
        markdown_path=markdown,
        title=title,
        json_path=json_path,
        html_path=html_path,
        max_chars=max_chars,
    )
    if chunks == 0:
        typer.echo("Telegram: skipped because TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.")
        return
    typer.echo(f"Telegram: sent {chunks} message chunk(s)")


@app.command("deployment-check")
def deployment_check(
    sources: Path = typer.Option(Path("examples/sources.example.json"), "--sources"),
    state_dir: Path = typer.Option(Path(".auv_intel_digest"), "--state-dir"),
    output_dir: Path = typer.Option(Path("digests"), "--output-dir"),
) -> None:
    _run_deployment_check(sources=sources, state_dir=state_dir, output_dir=output_dir)


@app.command("doctor")
def doctor(
    sources: Path = typer.Option(Path("examples/sources.example.json"), "--sources"),
    state_dir: Path = typer.Option(Path(".auv_intel_digest"), "--state-dir"),
    output_dir: Path = typer.Option(Path("digests"), "--output-dir"),
) -> None:
    _run_deployment_check(sources=sources, state_dir=state_dir, output_dir=output_dir)


def _run_deployment_check(*, sources: Path, state_dir: Path, output_dir: Path) -> None:
    checks = [
        ("python_version", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
        ("package_import", "ok"),
        ("sources_file", "present" if sources.exists() else "missing"),
        ("state_dir_writable", "yes" if _ensure_writable_dir(state_dir) else "no"),
        ("output_dir_writable", "yes" if _ensure_writable_dir(output_dir) else "no"),
        ("openai_api_key", "present" if os.getenv("OPENAI_API_KEY") else "missing"),
        ("auv_intel_llm_api_key", "present" if os.getenv("AUV_INTEL_LLM_API_KEY") else "missing"),
        ("auv_intel_llm_base_url", os.getenv("AUV_INTEL_LLM_BASE_URL", "https://api.openai.com/v1")),
        ("auv_intel_llm_model", os.getenv("AUV_INTEL_LLM_MODEL", "gpt-4o-mini")),
        ("auv_intel_llm_fallback_models", os.getenv("AUV_INTEL_LLM_FALLBACK_MODELS", "")),
        ("auv_intel_llm_timeout", os.getenv("AUV_INTEL_LLM_TIMEOUT", "60")),
        ("auv_intel_llm_max_items", os.getenv("AUV_INTEL_LLM_MAX_ITEMS", "0")),
        ("smtp_host", "present" if os.getenv("SMTP_HOST") else "missing"),
        ("smtp_username", "present" if os.getenv("SMTP_USERNAME") else "missing"),
        ("smtp_password", "present" if os.getenv("SMTP_PASSWORD") else "missing"),
        ("email_to", os.getenv("EMAIL_TO", "920062755@qq.com")),
        ("telegram_bot_token", "present" if os.getenv("TELEGRAM_BOT_TOKEN") else "missing"),
        ("telegram_chat_id", "present" if os.getenv("TELEGRAM_CHAT_ID") else "missing"),
    ]
    for name, value in checks:
        typer.echo(f"{name}: {value}")
    typer.echo("next_steps:")
    if not sources.exists():
        typer.echo("- Create or fix the sources JSON file before running collect.")
    if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_USERNAME") or not os.getenv("SMTP_PASSWORD"):
        typer.echo("- Configure SMTP secrets to enable email delivery; artifact generation still works.")
    if not os.getenv("AUV_INTEL_LLM_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        typer.echo("- LLM API key is missing; use noop summarizer or configure SiliconFlow/OpenAI-compatible credentials.")
    typer.echo("- Run check-sources, then collect, then send-email or GitHub Actions workflow_dispatch.")


def _ensure_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False
