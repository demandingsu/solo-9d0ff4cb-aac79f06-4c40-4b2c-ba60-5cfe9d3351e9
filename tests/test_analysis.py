"""公告链分析逻辑测试。"""

from analysis import STATUS_ACTIVE, STATUS_CANCELLED, build_projects
from scraper import Announcement


def ann(project, notice, ntype, pub, deadline=None, target=None):
    return Announcement(
        project_no=project,
        notice_no=notice,
        notice_type=ntype,
        publish_time=pub,
        deadline=deadline,
        target_notice_no=target,
        title=notice,
        url=f"http://example.com/detail/{notice}.html",
    )


def test_correction_updates_deadline():
    anns = [
        ann("P1", "N1", "tender", "2026-11-01 09:00", deadline="2026-11-20 17:00"),
        ann("P1", "N2", "correction", "2026-11-05 10:00", deadline="2026-11-25 17:00", target="N1"),
    ]
    (p,) = build_projects(anns)
    assert p["status"] == STATUS_ACTIVE
    assert p["deadline"] == "2026-11-25 17:00"
    assert len(p["chain"]) == 2


def test_cancellation_marks_stopped():
    anns = [
        ann("P1", "N1", "tender", "2026-11-01 09:00", deadline="2026-11-20 17:00"),
        ann("P1", "N2", "cancellation", "2026-11-06 14:00", target="N1"),
    ]
    (p,) = build_projects(anns)
    assert p["status"] == STATUS_CANCELLED


def test_chain_sorted_by_publish_time_not_input_order():
    anns = [
        ann("P1", "N3", "correction", "2026-11-09 16:00", deadline="2026-11-28 10:00", target="N2"),
        ann("P1", "N1", "tender", "2026-11-01 09:00", deadline="2026-11-20 17:00"),
        ann("P1", "N2", "correction", "2026-11-05 10:00", deadline="2026-11-25 17:00", target="N1"),
    ]
    (p,) = build_projects(anns)
    assert [c["notice_no"] for c in p["chain"]] == ["N1", "N2", "N3"]
    assert p["deadline"] == "2026-11-28 10:00"


def test_correction_then_cancellation():
    anns = [
        ann("P1", "N1", "tender", "2026-11-08 09:00", deadline="2026-11-30 17:00"),
        ann("P1", "N2", "correction", "2026-11-10 11:00", deadline="2026-12-02 17:00", target="N1"),
        ann("P1", "N3", "cancellation", "2026-11-11 09:00", target="N1"),
    ]
    (p,) = build_projects(anns)
    assert p["status"] == STATUS_CANCELLED
    assert p["deadline"] == "2026-12-02 17:00"  # 保留最后一次更正后的截标时间供参考


def test_projects_grouped_independently():
    anns = [
        ann("P1", "N1", "tender", "2026-11-01 09:00", deadline="2026-11-20 17:00"),
        ann("P2", "N2", "tender", "2026-11-02 09:00", deadline="2026-11-22 12:00"),
        ann("P2", "N3", "cancellation", "2026-11-06 14:00", target="N2"),
    ]
    projects = {p["project_no"]: p for p in build_projects(anns)}
    assert projects["P1"]["status"] == STATUS_ACTIVE
    assert projects["P1"]["deadline"] == "2026-11-20 17:00"
    assert projects["P2"]["status"] == STATUS_CANCELLED
