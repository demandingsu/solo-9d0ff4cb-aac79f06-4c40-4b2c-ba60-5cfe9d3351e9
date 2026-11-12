"""示例公告站的公告数据。

字段与采集端约定的页面结构一一对应：
- notice_no    公告编号
- project_no   项目编号
- type         公告类型：tender 招标公告 / correction 更正公告 / cancellation 撤销公告
- title        公告标题
- publish_time 发布时间（YYYY-MM-DD HH:MM）
- deadline     截标时间（撤销公告无）
- target       更正 / 撤销所指的公告编号（招标公告无）
- body         正文
"""

TYPE_LABELS = {
    "tender": "招标公告",
    "correction": "更正公告",
    "cancellation": "撤销公告",
}

ANNOUNCEMENTS = [
    {
        "notice_no": "NT-2026-0001",
        "project_no": "PRJ-2026-001",
        "type": "tender",
        "title": "市政道路改造工程施工招标",
        "publish_time": "2026-11-01 09:00",
        "deadline": "2026-11-20 17:00",
        "target": None,
        "body": "现就市政道路改造工程进行公开招标，欢迎符合条件的投标人参加投标。",
    },
    {
        "notice_no": "NT-2026-0003",
        "project_no": "PRJ-2026-002",
        "type": "tender",
        "title": "办公楼物业服务采购",
        "publish_time": "2026-11-02 09:00",
        "deadline": "2026-11-22 12:00",
        "target": None,
        "body": "现就办公楼物业服务进行公开招标，服务期一年。",
    },
    {
        "notice_no": "NT-2026-0005",
        "project_no": "PRJ-2026-003",
        "type": "tender",
        "title": "智慧园区网络设备采购",
        "publish_time": "2026-11-03 09:00",
        "deadline": "2026-11-24 17:00",
        "target": None,
        "body": "现就智慧园区网络设备采购进行公开招标。",
    },
    {
        "notice_no": "NT-2026-0008",
        "project_no": "PRJ-2026-004",
        "type": "tender",
        "title": "职工食堂食材配送服务",
        "publish_time": "2026-11-04 09:00",
        "deadline": "2026-11-21 17:00",
        "target": None,
        "body": "现就职工食堂食材配送服务进行公开招标。",
    },
    {
        "notice_no": "NT-2026-0002",
        "project_no": "PRJ-2026-001",
        "type": "correction",
        "title": "市政道路改造工程施工招标更正公告",
        "publish_time": "2026-11-05 10:00",
        "deadline": "2026-11-25 17:00",
        "target": "NT-2026-0001",
        "body": "因工程量清单调整，现将截标时间由 2026-11-20 17:00 更正为 2026-11-25 17:00，其余内容不变。",
    },
    {
        "notice_no": "NT-2026-0004",
        "project_no": "PRJ-2026-002",
        "type": "cancellation",
        "title": "办公楼物业服务采购撤销公告",
        "publish_time": "2026-11-06 14:00",
        "deadline": None,
        "target": "NT-2026-0003",
        "body": "因采购计划调整，现撤销办公楼物业服务采购招标公告，本项目停止办理。",
    },
    {
        "notice_no": "NT-2026-0006",
        "project_no": "PRJ-2026-003",
        "type": "correction",
        "title": "智慧园区网络设备采购更正公告（一）",
        "publish_time": "2026-11-07 09:30",
        "deadline": "2026-11-26 10:00",
        "target": "NT-2026-0005",
        "body": "现将截标时间由 2026-11-24 17:00 更正为 2026-11-26 10:00。",
    },
    {
        "notice_no": "NT-2026-0009",
        "project_no": "PRJ-2026-005",
        "type": "tender",
        "title": "医疗设备采购项目",
        "publish_time": "2026-11-08 09:00",
        "deadline": "2026-11-30 17:00",
        "target": None,
        "body": "现就医疗设备采购项目进行公开招标。",
    },
    {
        "notice_no": "NT-2026-0007",
        "project_no": "PRJ-2026-003",
        "type": "correction",
        "title": "智慧园区网络设备采购更正公告（二）",
        "publish_time": "2026-11-09 16:00",
        "deadline": "2026-11-28 10:00",
        "target": "NT-2026-0006",
        "body": "现将截标时间由 2026-11-26 10:00 更正为 2026-11-28 10:00。",
    },
    {
        "notice_no": "NT-2026-0010",
        "project_no": "PRJ-2026-005",
        "type": "correction",
        "title": "医疗设备采购项目更正公告",
        "publish_time": "2026-11-10 11:00",
        "deadline": "2026-12-02 17:00",
        "target": "NT-2026-0009",
        "body": "现将截标时间由 2026-11-30 17:00 更正为 2026-12-02 17:00。",
    },
    {
        "notice_no": "NT-2026-0011",
        "project_no": "PRJ-2026-005",
        "type": "cancellation",
        "title": "医疗设备采购项目撤销公告",
        "publish_time": "2026-11-11 09:00",
        "deadline": None,
        "target": "NT-2026-0009",
        "body": "因技术参数重大调整，现撤销医疗设备采购项目招标公告，本项目停止办理。",
    },
]

PAGE_SIZE = 5


def sorted_announcements():
    """列表页按发布时间倒序展示。"""
    return sorted(ANNOUNCEMENTS, key=lambda a: (a["publish_time"], a["notice_no"]), reverse=True)


def get_by_notice_no(notice_no):
    for a in ANNOUNCEMENTS:
        if a["notice_no"] == notice_no:
            return a
    return None
