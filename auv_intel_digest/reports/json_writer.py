from __future__ import annotations

import json
from pathlib import Path

from auv_intel_digest.models import DailyDigest


def digest_to_json_dict(digest: DailyDigest) -> dict:
    return {
        "date": digest.report_date.isoformat(),
        "generated_at": digest.generated_at,
        "timezone": digest.timezone,
        "summary": {
            "total_candidates": len(digest.items),
            "unique_or_update": sum(
                1 for item in digest.items if str(item.duplicate_status) in {"unique", "update"}
            ),
        },
        "source_status": [
            {
                "source": status.source,
                "status": status.status,
                "items": status.items,
                "error": status.error,
            }
            for status in digest.source_status
        ],
        "items": [item.to_json_dict() for item in digest.items],
    }


def write_json(path: Path, digest: DailyDigest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(digest_to_json_dict(digest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
