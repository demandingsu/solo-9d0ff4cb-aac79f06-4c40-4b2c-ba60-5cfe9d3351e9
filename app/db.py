"""SQLite 持久化：采集轮次与公告快照。

设计要点：
- 每一轮采集对应 rounds 表一行，公告挂在 round_id 下，轮次之间互不影响；
- 每轮按“规范化的起始目录网址”（catalog.catalog_key）归档：同一目录的
  list.html、list.html?page=1、list.html?page=2 归并为同一目录键；
- 公告只在整轮抓取全部成功后，于同一事务内写入并标记轮次成功，
  因此失败轮次不会留下半截数据，也不会污染上一轮结果（重抓不叠加）；
- 结果隔离：页面以最近一轮的目录键为准，失败轮次只回退到**同一目录**的
  最近成功快照；该目录没有成功快照时不显示任何项目结果，
  避免把别的公告站数据当成当前目录的结论。
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Iterable

from catalog import normalize_catalog_url
from scraper import Announcement

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    start_url TEXT NOT NULL,
    catalog_key TEXT NOT NULL DEFAULT '',   -- 规范化的起始目录网址（结果隔离的分组键）
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
"""

# 索引依赖迁移后的列结构，须在 _migrate 之后创建
SCHEMA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_announcements_round ON announcements(round_id);
CREATE INDEX IF NOT EXISTS idx_rounds_catalog ON rounds(catalog_key, status, id);
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
        _migrate(conn)
        conn.executescript(SCHEMA_INDEXES)
        # 上次进程退出可能留下 running 状态的轮次，统一标记为失败
        conn.execute(
            "UPDATE rounds SET status='failed', finished_at=?, error_message='进程中断，轮次未完成' "
            "WHERE status='running'",
            (_now(),),
        )


def _migrate(conn: sqlite3.Connection) -> None:
    """兼容旧库：rounds 表补 catalog_key 列并按 start_url 回填。"""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(rounds)")}
    if "catalog_key" not in cols:
        conn.execute("ALTER TABLE rounds ADD COLUMN catalog_key TEXT NOT NULL DEFAULT ''")
    rows = conn.execute("SELECT id, start_url FROM rounds WHERE catalog_key=''").fetchall()
    for row in rows:
        conn.execute(
            "UPDATE rounds SET catalog_key=? WHERE id=?",
            (normalize_catalog_url(row["start_url"]), row["id"]),
        )


def create_round(start_url: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO rounds (started_at, start_url, catalog_key, status) VALUES (?, ?, ?, 'running')",
            (_now(), start_url, normalize_catalog_url(start_url)),
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


def get_latest_success_round(catalog_key: str) -> sqlite3.Row | None:
    """同一目录键下最近一次成功轮次；该目录没有成功快照时返回 None。"""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM rounds WHERE status='success' AND catalog_key=? ORDER BY id DESC LIMIT 1",
            (catalog_key,),
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
