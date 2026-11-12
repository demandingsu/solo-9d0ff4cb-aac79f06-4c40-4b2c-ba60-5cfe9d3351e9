"""页面级结果隔离测试：甲站成功后乙站失败，页面不得展示甲站结果。

通过 FastAPI TestClient 走完整请求链路（含模板渲染），验证轮次状态、
来源链接与提示一致：失败轮次只回退同一目录的最近成功快照。
"""

import os

import pytest
from fastapi.testclient import TestClient

import db
import main
import scraper

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app"))

CATALOG_A = "http://sample-site:8000/a/list.html?page=1"
CATALOG_B = "http://sample-site:8000/b/list.html?page=1"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    monkeypatch.chdir(APP_DIR)  # 模板目录为相对路径
    return TestClient(main.app)


def ann(project, notice, catalog):
    return scraper.Announcement(
        project_no=project,
        notice_no=notice,
        notice_type="tender",
        publish_time="2026-11-01 09:00",
        deadline="2026-11-20 17:00",
        target_notice_no=None,
        title=notice,
        url=f"http://sample-site:8000/{catalog}/detail/{notice}.html",
    )


def seed_success(catalog_url, project, notice, catalog):
    rid = db.create_round(catalog_url)
    db.finish_round_success(rid, [ann(project, notice, catalog)], list_pages=1, detail_pages=1)
    return rid


def fail_next_scrape(monkeypatch):
    def boom(url):
        raise scraper.ScrapeError("http://sample-site:8000/b/list.html?page=2", "HTTP 500")

    monkeypatch.setattr(main.scraper, "scrape", boom)


def test_other_catalog_failure_hides_projects(client, monkeypatch):
    """甲站成功后乙站翻页失败：页面不显示任何项目结果，并明确提示无快照。"""
    seed_success(CATALOG_A, "PRJ-A-ONLY", "NT-A-1", "a")
    fail_next_scrape(monkeypatch)

    resp = client.post("/scrape", data={"start_url": CATALOG_B}, follow_redirects=True)

    assert resp.status_code == 200
    assert "PRJ-A-ONLY" not in resp.text  # 甲站结果不得出现在乙站失败页面上
    assert "没有可回退的成功快照" in resp.text
    assert "不显示项目结果" in resp.text
    assert "b/list.html?page=2" in resp.text  # 失败网址指向乙站翻页


def test_failure_falls_back_to_same_catalog_snapshot(client, monkeypatch):
    """乙站有自己的成功快照时，失败只回退到乙站快照，不混入甲站。"""
    seed_success(CATALOG_A, "PRJ-A-ONLY", "NT-A-1", "a")
    rid_b = seed_success(CATALOG_B, "PRJ-B-ONLY", "NB-B-1", "b")
    fail_next_scrape(monkeypatch)

    resp = client.post("/scrape", data={"start_url": CATALOG_B}, follow_redirects=True)

    assert resp.status_code == 200
    assert "PRJ-B-ONLY" in resp.text  # 回退展示乙站自己的快照
    assert "PRJ-A-ONLY" not in resp.text  # 不混入甲站数据
    assert f"已回退到同一目录第 {rid_b} 轮" in resp.text
    assert "b/list.html" in resp.text  # 来源链接指向乙站目录


def test_successful_scrape_shows_current_round(client, monkeypatch):
    """成功轮次直接展示本轮结果。"""
    seed_success(CATALOG_A, "PRJ-A-ONLY", "NT-A-1", "a")

    def fake_scrape(url):
        return scraper.ScrapeResult(
            announcements=[ann("PRJ-B-ONLY", "NB-B-1", "b")],
            list_pages=[url],
            detail_pages=["http://sample-site:8000/b/detail/NB-B-1.html"],
        )

    monkeypatch.setattr(main.scraper, "scrape", fake_scrape)
    resp = client.post("/scrape", data={"start_url": CATALOG_B}, follow_redirects=True)

    assert resp.status_code == 200
    assert "抓取成功" in resp.text
    assert "PRJ-B-ONLY" in resp.text
    assert "PRJ-A-ONLY" not in resp.text


def test_index_without_rounds_shows_empty_hint(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "尚无成功采集结果" in resp.text
