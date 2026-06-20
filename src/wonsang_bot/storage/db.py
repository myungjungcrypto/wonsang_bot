"""SQLite 저장소 (표준 라이브러리 sqlite3).

- seen_announcements: 이미 처리한 공지(중복 알림 방지)
- listings: 감지된 상장 이벤트 기록(과거 케이스 DB의 씨앗)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading

from ..core.events import Announcement, ListingDetected


class Storage:
    def __init__(self, path: str) -> None:
        self.path = path
        if path != ":memory:":
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS seen_announcements (
                    source TEXT NOT NULL,
                    id TEXT NOT NULL,
                    title TEXT,
                    seen_at TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (source, id)
                );
                CREATE TABLE IF NOT EXISTS listings (
                    source TEXT NOT NULL,
                    announcement_id TEXT NOT NULL,
                    title TEXT,
                    symbols TEXT,
                    markets TEXT,
                    is_krw INTEGER,
                    confidence REAL,
                    detected_at TEXT,
                    payload TEXT,
                    PRIMARY KEY (source, announcement_id)
                );
                """
            )

    # --- seen ---
    def is_seen(self, source: str, ann_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM seen_announcements WHERE source=? AND id=?",
                (source, ann_id),
            )
            return cur.fetchone() is not None

    def seen_keys(self) -> set[str]:
        with self._lock:
            cur = self._conn.execute("SELECT source, id FROM seen_announcements")
            return {f"{r['source']}:{r['id']}" for r in cur.fetchall()}

    def count_seen(self, source: str | None = None) -> int:
        with self._lock:
            if source is None:
                cur = self._conn.execute("SELECT COUNT(*) AS c FROM seen_announcements")
            else:
                cur = self._conn.execute(
                    "SELECT COUNT(*) AS c FROM seen_announcements WHERE source=?",
                    (source,),
                )
            return int(cur.fetchone()["c"])

    def mark_seen(self, ann: Announcement) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO seen_announcements (source, id, title) VALUES (?,?,?)",
                (ann.source, ann.id, ann.title),
            )

    def mark_seen_many(self, anns: list[Announcement]) -> None:
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT OR IGNORE INTO seen_announcements (source, id, title) VALUES (?,?,?)",
                [(a.source, a.id, a.title) for a in anns],
            )

    # --- listings ---
    def save_listing(self, ev: ListingDetected) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO listings
                (source, announcement_id, title, symbols, markets, is_krw,
                 confidence, detected_at, payload)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    ev.source,
                    ev.announcement_id,
                    ev.title,
                    json.dumps(ev.symbols, ensure_ascii=False),
                    json.dumps(ev.markets, ensure_ascii=False),
                    1 if ev.is_krw else 0,
                    ev.confidence,
                    ev.detected_at,
                    json.dumps(ev.to_dict(), ensure_ascii=False),
                ),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
