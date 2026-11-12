"""列表页 / 详情页抓取与解析。

解析约定（与示例公告站页面结构一致）：
- 列表页：公告链接 ul.notice-list a[href]；分页导航 nav.pagination a[href]
- 详情页：div.notice[data-notice-type]，字段 #project-no / #notice-no /
  #publish-time / #deadline / #target-notice

只跟随与起始列表网址同源的链接；任何一页抓取或解析失败都抛出
ScrapeError（携带出错网址），由上层决定保留上一轮结果。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_LIST_PAGES = 50
MAX_DETAIL_PAGES = 500
USER_AGENT = "bid-deadline-checker/1.0"

TYPE_LABELS = {
    "tender": "招标公告",
    "correction": "更正公告",
    "cancellation": "撤销公告",
}

_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y-%m-%d")


class ScrapeError(Exception):
    """单页抓取或解析失败。url 为出错的页面网址。"""

    def __init__(self, url: str, message: str):
        self.url = url
        self.message = message
        super().__init__(f"{url}：{message}")


@dataclass
class Announcement:
    project_no: str
    notice_no: str
    notice_type: str  # tender / correction / cancellation
    publish_time: str  # 归一化为 YYYY-MM-DD HH:MM
    deadline: str | None
    target_notice_no: str | None
    title: str
    url: str

    @property
    def type_label(self) -> str:
        return TYPE_LABELS.get(self.notice_type, self.notice_type)


@dataclass
class ScrapeResult:
    announcements: list[Announcement] = field(default_factory=list)
    list_pages: list[str] = field(default_factory=list)
    detail_pages: list[str] = field(default_factory=list)


def _default_port(scheme: str) -> int | None:
    return {"http": 80, "https": 443}.get(scheme)


def same_origin(url: str, origin_url: str) -> bool:
    p, o = urlparse(url), urlparse(origin_url)
    return (p.scheme, p.hostname, _default_port(p.scheme) if p.port is None else p.port) == (
        o.scheme,
        o.hostname,
        _default_port(o.scheme) if o.port is None else o.port,
    )


def _normalize(href: str, base: str) -> str:
    url, _frag = urldefrag(urljoin(base, href))
    return url


def _fetch_soup(client: httpx.Client, url: str) -> BeautifulSoup:
    try:
        resp = client.get(url)
    except httpx.HTTPError as exc:
        raise ScrapeError(url, f"请求失败：{exc}") from exc
    if resp.status_code >= 400:
        raise ScrapeError(url, f"HTTP {resp.status_code}")
    return BeautifulSoup(resp.text, "html.parser")


def _norm_time(raw: str, url: str, field_name: str) -> str:
    raw = raw.strip()
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    raise ScrapeError(url, f"{field_name}格式无法识别：{raw!r}")


def _text(node, selector: str) -> str | None:
    el = node.select_one(selector)
    return el.get_text(strip=True) if el else None


def parse_detail(html: str, url: str) -> Announcement:
    """解析单个详情页 HTML（独立出来便于测试）。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("div.notice")
    if root is None:
        raise ScrapeError(url, "页面结构不符：未找到 div.notice 容器")
    notice_type = (root.get("data-notice-type") or "").strip()
    if notice_type not in TYPE_LABELS:
        raise ScrapeError(url, f"未知公告类型：{notice_type!r}")

    project_no = _text(root, "#project-no")
    notice_no = _text(root, "#notice-no")
    publish_raw = _text(root, "#publish-time")
    missing = [
        name
        for name, val in (("项目编号", project_no), ("公告编号", notice_no), ("发布时间", publish_raw))
        if not val
    ]
    if missing:
        raise ScrapeError(url, "缺少必要字段：" + "、".join(missing))

    deadline_raw = _text(root, "#deadline")
    target = _text(root, "#target-notice")
    if notice_type in ("correction", "cancellation") and not target:
        raise ScrapeError(url, "更正/撤销公告缺少所指公告编号")

    title_el = root.select_one("h2")
    return Announcement(
        project_no=project_no,
        notice_no=notice_no,
        notice_type=notice_type,
        publish_time=_norm_time(publish_raw, url, "发布时间"),
        deadline=_norm_time(deadline_raw, url, "截标时间") if deadline_raw else None,
        target_notice_no=target,
        title=title_el.get_text(strip=True) if title_el else notice_no,
        url=url,
    )


def scrape(start_url: str) -> ScrapeResult:
    """从列表网址出发，抓完同源分页与全部详情页。任一页面失败即抛 ScrapeError。"""
    parsed = urlparse(start_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ScrapeError(start_url, "起始网址必须是 http(s) 网址")

    result = ScrapeResult()
    visited_lists: set[str] = set()
    queue = [start_url]
    detail_urls: list[str] = []
    seen_details: set[str] = set()

    with httpx.Client(
        timeout=httpx.Timeout(10.0),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        # 1) 遍历同源分页，收集详情页链接
        while queue:
            url = queue.pop(0)
            if url in visited_lists:
                continue
            if len(visited_lists) >= MAX_LIST_PAGES:
                raise ScrapeError(url, f"分页数量超过上限 {MAX_LIST_PAGES}")
            soup = _fetch_soup(client, url)

            items = soup.select("ul.notice-list a[href]")
            nav_links = soup.select("nav.pagination a[href]")
            if not items and not nav_links:
                raise ScrapeError(url, "页面结构不符：未找到公告列表（ul.notice-list）或分页导航（nav.pagination）")

            for a in items:
                href = _normalize(a["href"], url)
                if not same_origin(href, start_url):
                    continue  # 跨源链接不跟随
                if href not in seen_details:
                    seen_details.add(href)
                    detail_urls.append(href)

            visited_lists.add(url)
            result.list_pages.append(url)
            for a in nav_links:
                href = _normalize(a["href"], url)
                if same_origin(href, start_url) and href not in visited_lists and href not in queue:
                    queue.append(href)

        # 2) 逐个抓取详情页
        for durl in detail_urls:
            if len(result.announcements) >= MAX_DETAIL_PAGES:
                raise ScrapeError(durl, f"详情页数量超过上限 {MAX_DETAIL_PAGES}")
            soup = _fetch_soup(client, durl)
            result.announcements.append(parse_detail(str(soup), durl))
            result.detail_pages.append(durl)

    return result
