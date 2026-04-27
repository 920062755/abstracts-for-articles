from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/daily-digest.yml")


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_daily_digest_workflow_exists_and_has_manual_and_scheduled_triggers():
    text = _workflow_text()

    assert WORKFLOW_PATH.exists()
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "0 0 * * *"' in text


def test_daily_digest_workflow_runs_verification_and_collect_commands():
    text = _workflow_text()

    assert "python -m compileall auv_intel_digest tests" in text
    assert "python -m pytest -q -p no:cacheprovider" in text
    assert "python -m auv_intel_digest check-sources" in text
    assert "python -m auv_intel_digest collect" in text
    assert "--language zh" in text
    assert "--fail-on-all-source-errors" in text


def test_daily_digest_workflow_uploads_artifact_and_sends_telegram_after_collect():
    text = _workflow_text()

    assert "actions/upload-artifact@v4" in text
    assert "if: always()" in text
    assert "auv-intel-digest-${{ github.run_id }}" in text
    assert "python -m auv_intel_digest send-telegram" in text
    assert "continue-on-error: true" in text


def test_daily_digest_workflow_captures_collect_exit_code_and_fails_last():
    text = _workflow_text()

    assert "set +e" in text
    assert "COLLECT_EXIT_CODE=" in text
    assert "GITHUB_ENV" in text
    assert "Fail workflow when all sources failed" in text
    assert 'exit "${COLLECT_EXIT_CODE}"' in text


def test_daily_digest_workflow_uses_cache_for_state_without_committing_state():
    text = _workflow_text()

    assert "actions/cache@v4" in text
    assert "path: .auv_intel_digest" in text
    assert "restore-keys:" in text
    assert ".auv_intel_digest/state.json" in text


def test_daily_digest_workflow_does_not_hardcode_secret_values():
    text = _workflow_text()

    assert "TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}" in text
    assert "TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}" in text
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "your_bot_token" not in text
    assert "secret-token" not in text
