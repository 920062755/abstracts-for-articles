from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from auv_intel_digest.models import Topic


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_topics(path: str | Path = "config/topics.yaml") -> list[Topic]:
    data = load_yaml(path)
    topics = []
    for key, value in data.get("topics", {}).items():
        topics.append(
            Topic(
                key=key,
                name_zh=value["name_zh"],
                name_en=value["name_en"],
                enabled=bool(value.get("enabled", True)),
                weight=float(value.get("weight", 1.0)),
                keywords=value.get("keywords", {}),
                tags=list(value.get("tags", [])),
            )
        )
    return topics


def load_sources_config(path: str | Path = "config/sources.yaml") -> dict[str, Any]:
    return load_yaml(path)
