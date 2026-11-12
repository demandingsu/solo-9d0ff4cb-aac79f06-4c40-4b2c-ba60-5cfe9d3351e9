"""示例公告站：模拟公开招标公告网站。

页面结构（与采集端解析约定一致）：
- 列表页 /list.html?page=N
    - 公告链接：ul.notice-list a[href]
    - 分页导航：nav.pagination a[href]
- 详情页 /detail/<公告编号>.html
    - 容器 div.notice，data-notice-type = tender|correction|cancellation
    - #project-no 项目编号、#notice-no 公告编号、#publish-time 发布时间
    - #deadline 截标时间（如有）、#target-notice 更正/撤销所指公告编号（如有）

故障注入：GET /admin/fail?on=1 开启后，详情页 NT-2026-0004 返回 500，
用于演示采集端“任一页面失败则保留上一轮结果”的行为；on=0 关闭。
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from data import ANNOUNCEMENTS, PAGE_SIZE, TYPE_LABELS, get_by_notice_no, sorted_announcements

app = FastAPI(title="示例公告站")
templates = Jinja2Templates(directory="templates")

# 故障注入状态：开启后 FAIL_NOTICE 对应的详情页返回 500
FAIL_STATE = {"on": False}
FAIL_NOTICE = "NT-2026-0004"


@app.get("/", include_in_schema=False)
def index():
    return RedirectResponse("/list.html?page=1")


@app.get("/list.html", response_class=HTMLResponse)
def list_page(request: Request, page: int = 1):
    items_all = sorted_announcements()
    total_pages = max(1, (len(items_all) + PAGE_SIZE - 1) // PAGE_SIZE)
    if page < 1 or page > total_pages:
        return HTMLResponse("<h1>404 页码不存在</h1>", status_code=404)
    start = (page - 1) * PAGE_SIZE
    items = []
    for a in items_all[start : start + PAGE_SIZE]:
        items.append({**a, "type_label": TYPE_LABELS[a["type"]]})
    return templates.TemplateResponse(
        request,
        "list.html",
        {
            "items": items,
            "page": page,
            "total_pages": total_pages,
            "pages": list(range(1, total_pages + 1)),
            "fail_on": FAIL_STATE["on"],
            "fail_notice": FAIL_NOTICE,
        },
    )


@app.get("/detail/{notice_no}.html", response_class=HTMLResponse)
def detail_page(request: Request, notice_no: str):
    if FAIL_STATE["on"] and notice_no == FAIL_NOTICE:
        return HTMLResponse(
            f"<h1>500 Internal Server Error</h1><p>故障注入已开启：{notice_no} 暂时不可用。</p>",
            status_code=500,
        )
    a = get_by_notice_no(notice_no)
    if a is None:
        return HTMLResponse(f"<h1>404 公告不存在：{notice_no}</h1>", status_code=404)
    return templates.TemplateResponse(
        request,
        "detail.html",
        {"a": {**a, "type_label": TYPE_LABELS[a["type"]]}, "fail_on": FAIL_STATE["on"]},
    )


@app.get("/admin/fail", response_class=HTMLResponse)
def admin_fail(on: int = 0):
    FAIL_STATE["on"] = bool(on)
    state = "已开启" if FAIL_STATE["on"] else "已关闭"
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>故障注入</title></head>
<body>
<h1>故障注入{state}</h1>
<p>开启后，详情页 <code>/detail/{FAIL_NOTICE}.html</code> 将返回 500，用于验证采集端失败处理。</p>
<p><a href="/admin/fail?on=1">开启</a> · <a href="/admin/fail?on=0">关闭</a> · <a href="/list.html?page=1">返回列表</a></p>
</body></html>"""


@app.get("/admin/status")
def admin_status():
    return {"fail_on": FAIL_STATE["on"], "fail_notice": FAIL_NOTICE, "announcements": len(ANNOUNCEMENTS)}
