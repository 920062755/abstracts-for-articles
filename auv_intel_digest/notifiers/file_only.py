from __future__ import annotations

from pathlib import Path

from auv_intel_digest.notifiers.base import Notifier


class FileOnlyNotifier(Notifier):
    name = "file_only"

    def send(
        self,
        *,
        title: str,
        markdown: str,
        markdown_path: Path,
        json_path: Path,
        html_path: Path | None = None,
    ) -> None:
        return None
