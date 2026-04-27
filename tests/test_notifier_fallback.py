from pathlib import Path

import pytest

from auv_intel_digest.notifiers.base import Notifier
from auv_intel_digest.notifiers.composite import CompositeNotifier
from auv_intel_digest.notifiers.file_only import FileOnlyNotifier


class FailingNotifier(Notifier):
    name = "failing"

    def send(
        self,
        *,
        title: str,
        markdown: str,
        markdown_path: Path,
        json_path: Path,
        html_path: Path | None = None,
    ) -> None:
        raise RuntimeError("boom")


def test_notifier_fallback_does_not_fail_when_not_strict():
    notifier = CompositeNotifier([FileOnlyNotifier(), FailingNotifier()], strict=False)

    notifier.send(
        title="title",
        markdown="body",
        markdown_path=Path("tests/.tmp/x.md"),
        json_path=Path("tests/.tmp/x.json"),
    )


def test_notifier_fallback_fails_when_strict():
    notifier = CompositeNotifier([FileOnlyNotifier(), FailingNotifier()], strict=True)

    with pytest.raises(RuntimeError):
        notifier.send(
            title="title",
            markdown="body",
            markdown_path=Path("tests/.tmp/x.md"),
            json_path=Path("tests/.tmp/x.json"),
        )
