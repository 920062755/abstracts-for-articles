from __future__ import annotations

import logging
from pathlib import Path

from auv_intel_digest.notifiers.base import Notifier

logger = logging.getLogger(__name__)


class CompositeNotifier(Notifier):
    name = "composite"

    def __init__(self, notifiers: list[Notifier], strict: bool = False) -> None:
        self.notifiers = notifiers
        self.strict = strict

    def send(
        self,
        *,
        title: str,
        markdown: str,
        markdown_path: Path,
        json_path: Path,
        html_path: Path | None = None,
    ) -> None:
        errors: list[Exception] = []
        for notifier in self.notifiers:
            try:
                notifier.send(
                    title=title,
                    markdown=markdown,
                    markdown_path=markdown_path,
                    json_path=json_path,
                    html_path=html_path,
                )
            except Exception as exc:
                logger.warning("Notifier %s failed: %s", notifier.name, exc)
                errors.append(exc)
        if self.strict and errors:
            raise RuntimeError(f"{len(errors)} notifier(s) failed") from errors[0]
