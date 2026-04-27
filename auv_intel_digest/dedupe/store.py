from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from auv_intel_digest.models import IntelItem


class SeenStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS seen_items (
                    key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    first_seen_date TEXT NOT NULL,
                    last_seen_date TEXT NOT NULL,
                    duplicate_status TEXT NOT NULL,
                    score REAL NOT NULL,
                    topic TEXT
                )
                """
            )

    def get(self, key: str) -> dict | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM seen_items WHERE key = ?", (key,)).fetchone()
            return dict(row) if row else None

    def upsert_many(self, rows: Iterable[tuple[str, IntelItem]]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO seen_items
                    (key, title, url, first_seen_date, last_seen_date, duplicate_status, score, topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    title = excluded.title,
                    url = excluded.url,
                    last_seen_date = excluded.last_seen_date,
                    duplicate_status = excluded.duplicate_status,
                    score = excluded.score,
                    topic = excluded.topic
                """,
                [
                    (
                        key,
                        item.title,
                        item.url,
                        item.first_seen_date or "",
                        item.last_seen_date or "",
                        str(item.duplicate_status),
                        item.score,
                        item.topic,
                    )
                    for key, item in rows
                ],
            )
