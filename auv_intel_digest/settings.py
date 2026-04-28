from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    contact_email: str = ""
    timezone: str = "Asia/Shanghai"
    daily_run_time: str = "08:00"
    output_dir: Path = Path("reports")
    state_db_path: Path = Path("data/state.sqlite")
    log_level: str = "INFO"
    max_items_per_topic: int = 5
    dedup_window_days: int = 90
    report_language: str = "zh_with_original_en"
    save_html: bool = False
    notifier_mode: str = "file_only"
    strict_notify: bool = False
    qq_onebot_endpoint: str = ""
    qq_onebot_access_token: str = ""
    qq_target_type: str = "private"
    qq_target_id: str = ""
    qq_push_mode: str = "summary"
    qq_push_max_chars: int = 3500
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_parse_mode: str = ""
    telegram_max_chars: int = 3800
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    email_from: str = ""
    email_to: str = "920062755@qq.com"
    email_use_ssl: bool = True
    enable_github_actions: bool = False
    enable_auto_commit_reports: bool = False
    github_token: str = ""

    @classmethod
    def load(cls, env_path: str | Path | None = ".env") -> "Settings":
        if load_dotenv and env_path:
            load_dotenv(env_path)

        return cls(
            contact_email=os.getenv("CONTACT_EMAIL", ""),
            timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
            daily_run_time=os.getenv("DAILY_RUN_TIME", "08:00"),
            output_dir=Path(os.getenv("OUTPUT_DIR", "reports")),
            state_db_path=Path(os.getenv("STATE_DB_PATH", "data/state.sqlite")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            max_items_per_topic=_int_env("MAX_ITEMS_PER_TOPIC", 5),
            dedup_window_days=_int_env("DEDUP_WINDOW_DAYS", 90),
            report_language=os.getenv("REPORT_LANGUAGE", "zh_with_original_en"),
            save_html=_bool_env("SAVE_HTML", False),
            notifier_mode=os.getenv("NOTIFIER_MODE", "file_only"),
            strict_notify=_bool_env("STRICT_NOTIFY", False),
            qq_onebot_endpoint=os.getenv("QQ_ONEBOT_ENDPOINT", ""),
            qq_onebot_access_token=os.getenv("QQ_ONEBOT_ACCESS_TOKEN", ""),
            qq_target_type=os.getenv("QQ_TARGET_TYPE", "private"),
            qq_target_id=os.getenv("QQ_TARGET_ID", ""),
            qq_push_mode=os.getenv("QQ_PUSH_MODE", "summary"),
            qq_push_max_chars=_int_env("QQ_PUSH_MAX_CHARS", 3500),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            telegram_parse_mode=os.getenv("TELEGRAM_PARSE_MODE", ""),
            telegram_max_chars=_int_env("TELEGRAM_MAX_CHARS", 3800),
            email_enabled=_bool_env("EMAIL_ENABLED", False),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=_int_env("SMTP_PORT", 465),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            email_from=os.getenv("EMAIL_FROM", ""),
            email_to=os.getenv("EMAIL_TO", "920062755@qq.com"),
            email_use_ssl=_bool_env("EMAIL_USE_SSL", True),
            enable_github_actions=_bool_env("ENABLE_GITHUB_ACTIONS", False),
            enable_auto_commit_reports=_bool_env("ENABLE_AUTO_COMMIT_REPORTS", False),
            github_token=os.getenv("GITHUB_TOKEN", ""),
        )
