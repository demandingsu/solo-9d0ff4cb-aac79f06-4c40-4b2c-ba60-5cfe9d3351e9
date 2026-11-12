"""SQLite 持久化：采集轮次与公告快照。

设计要点：
- 每一轮采集对应 rounds 表一行，公告挂在 round_id 下，轮次之间互不影响；
- 公告只在整轮抓取全部成功后，于同一事务内写入并标记轮次成功，
  因此失败轮次不会留下半截数据，也不会污染上一轮结果（重抓不叠加）；
- 页面始终展示最近一次 status='success' 的轮次结果。
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Iterable

from scraper import Announcement

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    start_url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',   -- running / success / failed
    list_pages INTEGER NOT NULL DEFAULT 0,
    detail_pages INTEGER NOT NULL DEFAULT 0,
    error_url TEXT,
    error_message TEXT
);
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id INTEGER NOT NULL REFERENCES rounds(id),
    project_no TEXT NOT NULL,
    notice_no TEXT NOT NULL,
    notice_type TEXT NOT NULL,
    publish_time TEXT NOT NULL,
    deadline TEXT,
    target_notice_no TEXT,
    title TEXT,
    url TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_announcements_round ON announcements(round_id);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
        # 上次进程退出可能留下 running 状态的轮次，统一标记为失败
        conn.execute(
            "UPDATE rounds SET status='failed', finished_at=?, error_message='进程中断，轮次未完成' "
            "WHERE status='running'",
            (_now(),),
        )


def create_round(start_url: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO rounds (started_at, start_url, status) VALUES (?, ?, 'running')",
            (_now(), start_url),
        )
        return cur.lastrowid


def finish_round_success(round_id: int, announcements: Iterable[Announcement], list_pages: int, detail_pages: int) -> None:
    """整轮成功后一次性写入公告并更新轮次状态（单事务，失败则整体回滚）。"""
    rows = [
        (
            round_id,
            a.project_no,
            a.notice_no,
            a.notice_type,
            a.publish_time,
            a.deadline,
            a.target_notice_no,
            a.title,
            a.url,
        )
        for a in announcements
    ]
    with _connect() as conn:
        with conn:  # 事务：要么全部写入，要么全部回滚
            conn.executemany(
                "INSERT INTO announcements (round_id, project_no, notice_no, notice_type, publish_time, "
                "deadline, target_notice_no, title, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            conn.execute(
                "UPDATE rounds SET status='success', finished_at=?, list_pages=?, detail_pages=? WHERE id=?",
                (_now(), list_pages, detail_pages, round_id),
            )


def finish_round_failed(round_id: int, error_url: str, error_message: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE rounds SET status='failed', finished_at=?, error_url=?, error_message=? WHERE id=?",
            (_now(), error_url, error_message, round_id),
        )


def get_latest_success_round() -> sqlite3.Row | None:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM rounds WHERE status='success' ORDER BY id DESC LIMIT 1"
        ).fetchone()


def get_rounds(limit: int = 20) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute("SELECT * FROM rounds ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def get_announcements(round_id: int) -> list[Announcement]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM announcements WHERE round_id=? ORDER BY publish_time, notice_no",
            (round_id,),
        ).fetchall()
    return [
        Announcement(
            project_no=r["project_no"],
            notice_no=r["notice_no"],
            notice_type=r["notice_type"],
            publish_time=r["publish_time"],
            deadline=r["deadline"],
            target_notice_no=r["target_notice_no"],
            title=r["title"] or r["notice_no"],
            url=r["url"],
        )
        for r in rows
    ]
