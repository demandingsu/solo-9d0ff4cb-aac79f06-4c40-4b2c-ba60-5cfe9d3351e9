"""轮次结果隔离测试：成功快照按目录键绑定，失败只回退同一目录。

复现场景：采购专员先核对甲站（成功），再核对乙站（翻页失败）。
修复前页面会展示甲站的成功结果，容易被当成乙站结论；
修复后乙站失败时只回退乙站自己的最近成功快照，没有快照则不显示结果。
"""

import pytest

import db
from catalog import normalize_catalog_url
from scraper import Announcement

CATALOG_A = "http://sample-site:8000/a/list.html?page=1"
CATALOG_B = "http://sample-site:8000/b/list.html?page=1"


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    return db


def ann(project, notice, url):
    return Announcement(
        project_no=project,
        notice_no=notice,
        notice_type="tender",
        publish_time="2026-11-01 09:00",
        deadline="2026-11-20 17:00",
        target_notice_no=None,
        title=notice,
        url=url,
    )


def scrape_ok(round_id, project, notice, url):
    db.finish_round_success(round_id, [ann(project, notice, url)], list_pages=1, detail_pages=1)


def test_failed_round_falls_back_only_within_same_catalog(temp_db):
    # 甲站抓取成功
    rid_a = db.create_round(CATALOG_A)
    scrape_ok(rid_a, "PRJ-A", "NT-A-1", "http://sample-site:8000/a/detail/NT-A-1.html")
    # 乙站抓取失败：不能回退到甲站结果
    rid_b = db.create_round(CATALOG_B)
    db.finish_round_failed(rid_b, "http://sample-site:8000/b/list.html?page=2", "HTTP 500")

    key_a = normalize_catalog_url(CATALOG_A)
    key_b = normalize_catalog_url(CATALOG_B)
    assert db.get_latest_success_round(key_a)["id"] == rid_a
    assert db.get_latest_success_round(key_b) is None  # 乙站无快照，页面不显示项目结果


def test_failed_round_falls_back_to_same_catalog_snapshot(temp_db):
    # 甲站成功
    rid_a = db.create_round(CATALOG_A)
    scrape_ok(rid_a, "PRJ-A", "NT-A-1", "http://sample-site:8000/a/detail/NT-A-1.html")
    # 乙站先成功一次，之后再次抓取失败：回退到乙站自己的快照而非甲站
    rid_b1 = db.create_round(CATALOG_B)
    scrape_ok(rid_b1, "PRJ-B", "NB-B-1", "http://sample-site:8000/b/detail/NB-B-1.html")
    rid_b2 = db.create_round(CATALOG_B)
    db.finish_round_failed(rid_b2, "http://sample-site:8000/b/list.html?page=2", "HTTP 500")

    fallback = db.get_latest_success_round(normalize_catalog_url(CATALOG_B))
    assert fallback["id"] == rid_b1
    projects = {a.project_no for a in db.get_announcements(fallback["id"])}
    assert projects == {"PRJ-B"}  # 只能是乙站数据，不能混入甲站


def test_catalog_key_normalized_on_create(temp_db):
    rid1 = db.create_round("http://sample-site:8000/a/list.html?page=1")
    rid2 = db.create_round("http://sample-site:8000/a/list.html?page=3")
    rounds = {r["id"]: r for r in db.get_rounds()}
    assert rounds[rid1]["catalog_key"] == "http://sample-site:8000/a/list.html"
    assert rounds[rid1]["catalog_key"] == rounds[rid2]["catalog_key"]


def test_success_round_replaces_same_catalog_snapshot(temp_db):
    rid1 = db.create_round(CATALOG_A)
    scrape_ok(rid1, "PRJ-OLD", "NT-OLD", "http://sample-site:8000/a/detail/NT-OLD.html")
    rid2 = db.create_round(CATALOG_A)
    scrape_ok(rid2, "PRJ-NEW", "NT-NEW", "http://sample-site:8000/a/detail/NT-NEW.html")

    latest = db.get_latest_success_round(normalize_catalog_url(CATALOG_A))
    assert latest["id"] == rid2
    projects = {a.project_no for a in db.get_announcements(latest["id"])}
    assert projects == {"PRJ-NEW"}  # 重抓不叠加


def test_old_schema_db_is_migrated(tmp_path, monkeypatch):
    """旧版 rounds 表（无 catalog_key 列）升级后按 start_url 回填目录键。"""
    import sqlite3

    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            start_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            list_pages INTEGER NOT NULL DEFAULT 0,
            detail_pages INTEGER NOT NULL DEFAULT 0,
            error_url TEXT,
            error_message TEXT
        );
        INSERT INTO rounds (started_at, finished_at, start_url, status)
        VALUES ('2026-11-10T09:00:00', '2026-11-10T09:00:05',
                'http://sample-site:8000/a/list.html?page=1', 'success');
        """
    )
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()

    row = db.get_latest_success_round("http://sample-site:8000/a/list.html")
    assert row is not None
    assert row["catalog_key"] == "http://sample-site:8000/a/list.html"
