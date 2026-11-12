"""起始目录网址规范化：把同一公告目录的不同写法归并为同一个目录键。

成功快照按目录键绑定，失败轮次只回退到同一目录键的最近成功快照。
同一目录下 `list.html`、`list.html?page=1`、`list.html?page=2` 视为同一目录；
主机名大小写、默认端口、网址片段（#...）不影响目录身份；
其余查询参数（如栏目筛选条件）排序后保留，用于区分不同目录。
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urldefrag, urlparse, urlunparse

_DEFAULT_PORTS = {"http": 80, "https": 443}
# 翻页参数：同一目录的不同页码不改变目录身份
_PAGE_PARAMS = {"page"}


def normalize_catalog_url(url: str) -> str:
    """把起始列表网址规范化为目录键；无法解析为 http(s) 网址时原样返回（去片段）。"""
    url, _frag = urldefrag((url or "").strip())
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if not scheme or not host:
        return url
    try:
        port = parsed.port
    except ValueError:
        return url
    if port is None or port == _DEFAULT_PORTS.get(scheme):
        netloc = host
    else:
        netloc = f"{host}:{port}"
    path = parsed.path or "/"
    params = sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in _PAGE_PARAMS
    )
    return urlunparse((scheme, netloc, path, "", urlencode(params), ""))
