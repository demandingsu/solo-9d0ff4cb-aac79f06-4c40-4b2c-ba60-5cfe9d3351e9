"""详情页解析与同源判断测试。"""

import pytest

from scraper import ScrapeError, parse_detail, same_origin

DETAIL_HTML = """<!DOCTYPE html>
<html><body>
<div class="notice" data-notice-type="correction">
  <h1>更正公告</h1>
  <h2>某项目更正公告</h2>
  <dl class="notice-fields">
    <dt>项目编号</dt><dd id="project-no">PRJ-2026-001</dd>
    <dt>公告编号</dt><dd id="notice-no">NT-2026-0002</dd>
    <dt>发布时间</dt><dd id="publish-time">2026-11-05 10:00</dd>
    <dt>截标时间</dt><dd id="deadline">2026-11-25 17:00</dd>
    <dt>所指公告</dt><dd id="target-notice"><a href="/detail/NT-2026-0001.html">NT-2026-0001</a></dd>
  </dl>
</div>
</body></html>"""

URL = "http://example.com/detail/NT-2026-0002.html"


def test_parse_detail_full_fields():
    a = parse_detail(DETAIL_HTML, URL)
    assert a.project_no == "PRJ-2026-001"
    assert a.notice_no == "NT-2026-0002"
    assert a.notice_type == "correction"
    assert a.publish_time == "2026-11-05 10:00"
    assert a.deadline == "2026-11-25 17:00"
    assert a.target_notice_no == "NT-2026-0001"
    assert a.title == "某项目更正公告"
    assert a.url == URL


def test_parse_detail_missing_required_field():
    html = DETAIL_HTML.replace('<dd id="project-no">PRJ-2026-001</dd>', '<dd id="project-no"></dd>')
    with pytest.raises(ScrapeError) as exc:
        parse_detail(html, URL)
    assert exc.value.url == URL
    assert "项目编号" in exc.value.message


def test_parse_detail_correction_requires_target():
    html = DETAIL_HTML.replace(
        '<dt>所指公告</dt><dd id="target-notice"><a href="/detail/NT-2026-0001.html">NT-2026-0001</a></dd>', ""
    )
    with pytest.raises(ScrapeError, match="所指公告"):
        parse_detail(html, URL)


def test_parse_detail_bad_time_format():
    html = DETAIL_HTML.replace("2026-11-05 10:00", "11月5日上午")
    with pytest.raises(ScrapeError, match="发布时间"):
        parse_detail(html, URL)


def test_parse_detail_unknown_type():
    html = DETAIL_HTML.replace('data-notice-type="correction"', 'data-notice-type="unknown"')
    with pytest.raises(ScrapeError, match="未知公告类型"):
        parse_detail(html, URL)


def test_parse_detail_normalizes_time_format():
    html = DETAIL_HTML.replace("2026-11-05 10:00", "2026/11/05 10:00:00")
    a = parse_detail(html, URL)
    assert a.publish_time == "2026-11-05 10:00"


def test_same_origin():
    assert same_origin("http://example.com/a", "http://example.com/b")
    assert same_origin("http://example.com:80/a", "http://example.com/b")
    assert not same_origin("http://other.com/a", "http://example.com/b")
    assert not same_origin("https://example.com/a", "http://example.com/b")
    assert not same_origin("http://example.com:8080/a", "http://example.com/b")
