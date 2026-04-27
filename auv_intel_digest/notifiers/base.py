from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class Notifier(ABC):
    name: str

    @abstractmethod
    def send(
        self,
        *,
        title: str,
        markdown: str,
        markdown_path: Path,
        json_path: Path,
        html_path: Path | None = None,
    ) -> None:
        raise NotImplementedError
