"""示例公告站：模拟公开招标公告网站，内置甲、乙两个公告目录。

页面结构（与采集端解析约定一致）：
- 列表页 /{catalog}/list.html?page=N（catalog 为 a 或 b）
    - 公告链接：ul.notice-list a[href]
    - 分页导航：nav.pagination a[href]
- 详情页 /{catalog}/detail/<公告编号>.html
    - 容器 div.notice，data-notice-type = tender|correction|cancellation
    - #project-no 项目编号、#notice-no 公告编号、#publish-time 发布时间
    - #deadline 截标时间（如有）、#target-notice 更正/撤销所指公告编号（如有）

故障注入：GET /admin/fail?on=1 开启后，乙站（/b/）列表页第 2 页起返回 500，
模拟“采购专员核对完甲站、切换到乙站时翻页失败”的场景，用于验证采集端
“失败轮次只回退到同一目录的最近成功快照”；on=0 关闭。
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from data import CATALOGS, TYPE_LABELS, get_by_notice_no, sorted_announcements

app = FastAPI(title="示例公告站")
templates = Jinja2Templates(directory="templates")

# 故障注入状态：开启后乙站列表页第 2 页起返回 500（翻页失败）
FAIL_STATE = {"on": False}
FAIL_CATALOG = "b"


def _catalog_or_404(catalog: str):
    if catalog not in CATALOGS:
        return None
    return CATALOGS[catalog]


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/a/list.html?page=1")


@app.get("/{catalog}/list.html", response_class=HTMLResponse)
def list_page(request: Request, catalog: str, page: int = 1):
    cat = _catalog_or_404(catalog)
    if cat is None:
        return HTMLResponse(f"<h1>404 目录不存在：{catalog}</h1>", status_code=404)
    # 故障注入：乙站翻页（第 2 页起）返回 500
    if FAIL_STATE["on"] and catalog == FAIL_CATALOG and page >= 2:
        return HTMLResponse(
            f"<h1>500 Internal Server Error</h1><p>故障注入已开启：{cat['name']} 第 {page} 页暂时不可用。</p>",
            status_code=500,
        )
    items_all = sorted_announcements(catalog)
    page_size = cat["page_size"]
    total_pages = max(1, (len(items_all) + page_size - 1) // page_size)
    if page < 1 or page > total_pages:
        return HTMLResponse("<h1>404 页码不存在</h1>", status_code=404)
    start = (page - 1) * page_size
    items = []
    for a in items_all[start : start + page_size]:
        items.append({**a, "type_label": TYPE_LABELS[a["type"]]})
    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "catalog": catalog,
            "catalog_name": cat["name"],
            "catalogs": CATALOGS,
            "items": items,
            "page": page,
            "total_pages": total_pages,
            "pages": list(range(1, total_pages + 1)),
            "fail_on": FAIL_STATE["on"],
            "fail_catalog": FAIL_CATALOG,
        },
    )


@app.get("/{catalog}/detail/{notice_no}.html", response_class=HTMLResponse)
def detail_page(request: Request, catalog: str, notice_no: str):
    cat = _catalog_or_404(catalog)
    if cat is None:
        return HTMLResponse(f"<h1>404 目录不存在：{catalog}</h1>", status_code=404)
    a = get_by_notice_no(catalog, notice_no)
    if a is None:
        return HTMLResponse(f"<h1>404 公告不存在：{notice_no}</h1>", status_code=404)
    return templates.TemplateResponse(
        request,
        "detail.html",
        {
            "a": {**a, "type_label": TYPE_LABELS[a["type"]]},
            "catalog": catalog,
            "catalog_name": cat["name"],
            "fail_on": FAIL_STATE["on"],
        },
    )


@app.get("/admin/fail", response_class=HTMLResponse)
def admin_fail(on: int = 0):
    FAIL_STATE["on"] = bool(on)
    state = "已开启" if FAIL_STATE["on"] else "已关闭"
    cat_name = CATALOGS[FAIL_CATALOG]["name"]
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>故障注入</title></head>
<body>
<h1>故障注入{state}</h1>
<p>开启后，{cat_name}（<code>/{FAIL_CATALOG}/list.html</code>）第 2 页起将返回 500，
模拟“切换到乙站后翻页失败”，用于验证采集端失败轮次的结果隔离。</p>
<p><a href="/admin/fail?on=1">开启</a> · <a href="/admin/fail?on=0">关闭</a> ·
<a href="/a/list.html?page=1">甲站列表</a> · <a href="/b/list.html?page=1">乙站列表</a></p>
</body></html>"""


@app.get("/admin/status")
def admin_status():
    return {
        "fail_on": FAIL_STATE["on"],
        "fail_catalog": FAIL_CATALOG,
        "catalogs": {key: len(cat["announcements"]) for key, cat in CATALOGS.items()},
    }
