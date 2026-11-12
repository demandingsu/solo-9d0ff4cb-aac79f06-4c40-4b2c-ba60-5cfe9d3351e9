"""公告链分析：把同一项目的公告按发布时间串起来，推导最终状态。

规则：
- 招标公告：确立（或重新确立）项目的截标时间，状态置为“进行中”；
- 更正公告：若带截标时间，则更新项目当前截标时间；
- 撤销公告：项目标记为“停办”。
每条公告都作为依据保留在链上，页面可点击查看来源链接。
"""

from __future__ import annotations

from typing import Iterable

from scraper import TYPE_LABELS, Announcement

STATUS_ACTIVE = "进行中"
STATUS_CANCELLED = "停办"


def build_projects(announcements: Iterable[Announcement]) -> list[dict]:
    by_project: dict[str, list[Announcement]] = {}
    for a in announcements:
        by_project.setdefault(a.project_no, []).append(a)

    projects = []
    for project_no, items in by_project.items():
        # 按发布时间串链，时间相同按公告编号稳定排序
        items.sort(key=lambda a: (a.publish_time, a.notice_no))
        status = STATUS_ACTIVE
        deadline = None
        chain = []
        for a in items:
            if a.notice_type == "tender":
                status = STATUS_ACTIVE
                deadline = a.deadline
                note = f"发布招标，截标时间 {a.deadline or '未注明'}"
            elif a.notice_type == "correction":
                if a.deadline:
                    note = f"更正 {a.target_notice_no}：截标时间 {deadline or '未定'} → {a.deadline}"
                    deadline = a.deadline
                else:
                    note = f"更正 {a.target_notice_no}（未涉及截标时间）"
            elif a.notice_type == "cancellation":
                status = STATUS_CANCELLED
                note = f"撤销 {a.target_notice_no}：项目停止办理"
            else:
                note = "未知类型公告"
            chain.append(
                {
                    "notice_no": a.notice_no,
                    "type_label": TYPE_LABELS.get(a.notice_type, a.notice_type),
                    "publish_time": a.publish_time,
                    "note": note,
                    "url": a.url,
                }
            )
        projects.append(
            {
                "project_no": project_no,
                "status": status,
                "deadline": deadline,
                "chain": chain,
            }
        )

    projects.sort(key=lambda p: p["project_no"])
    return projects
