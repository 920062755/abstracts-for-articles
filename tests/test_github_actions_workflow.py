from pathlib import Path


WORKFLOW_PATH = Path(".github/workflows/daily-digest.yml")


def _workflow_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_daily_digest_workflow_exists_and_has_triggers():
    text = _workflow_text()

    assert WORKFLOW_PATH.exists()
    assert "workflow_dispatch:" in text
    assert "schedule:" in text
    assert 'cron: "0 0 * * *"' in text


def test_daily_digest_workflow_runs_checks_and_collect():
    text = _workflow_text()

    assert "python -m compileall auv_intel_digest tests" in text
    assert "python -m pytest -q -p no:cacheprovider" in text
    assert "python -m auv_intel_digest deployment-check" in text
    assert "python -m auv_intel_digest check-sources" in text
    assert "python -m auv_intel_digest collect" in text
    assert "--language zh" in text
    assert "--fail-on-all-source-errors" in text


def test_daily_digest_workflow_uploads_artifact_and_uses_state_cache():
    text = _workflow_text()

    assert "actions/cache@v4" in text
    assert "path: .auv_intel_digest" in text
    assert "actions/upload-artifact@v4" in text
    assert "auv-intel-digest-${{ github.run_id }}" in text
    assert "digests/latest.zh.md" in text
    assert ".auv_intel_digest/state.json" in text


def test_daily_digest_workflow_sends_email_and_captures_exit_code():
    text = _workflow_text()

    assert "Send email digest" in text
    assert "python -m auv_intel_digest send-email" in text
    assert "python -m auv_intel_digest send-telegram" not in text
    assert "set +e" in text
    assert "COLLECT_EXIT_CODE=" in text
    assert "GITHUB_ENV" in text
    assert 'exit "${COLLECT_EXIT_CODE}"' in text


def test_daily_digest_workflow_uses_siliconflow_and_email_secrets_without_values():
    text = _workflow_text()

    assert "AUV_INTEL_LLM_API_KEY: ${{ secrets.AUV_INTEL_LLM_API_KEY }}" in text
    assert "AUV_INTEL_LLM_BASE_URL" in text
    assert "SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}" in text
    assert "EMAIL_TO: ${{ vars.EMAIL_TO || '920062755@qq.com' }}" in text
    assert "secret-auth-code" not in text
    assert "your_api_key" not in text
