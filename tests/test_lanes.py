import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "lanes", Path(__file__).resolve().parents[1] / "scripts" / "lanes.py"
)
lanes = importlib.util.module_from_spec(_SPEC)
sys.modules["lanes"] = lanes
_SPEC.loader.exec_module(lanes)


def tasks_md(statuses=None, extra_rows="", t3_files="`evals/`, `data/`"):
    s = {"T1": "todo", "T2": "todo", "T3": "todo", "R1": "todo", **(statuses or {})}
    return f"""# Tasks

## Team
| Role | Person | Tool |
|------|--------|------|
| claude | Anh-08 | Claude Code |
| codex | NguyenQBao | Codex |
| human-A | Nguyen-Le-Tuan | |

## Tasks
| ID | Task | Owner | Files it may touch | Depends on | Status |
|----|------|-------|--------------------|------------|--------|
| T1 | Skeleton | claude | `src/features/x/` | - | {s["T1"]} |
| T2 | Rules | claude (worktree) | `src/features/x/__init__.py`, `tests/x.py` | T1 | {s["T2"]} |
| T3 | Data and evals | codex | {t3_files} | T1~ | {s["T3"]} |
| R1 | Review T2 | codex | | T2 | {s["R1"]} |
{extra_rows}
## Requests
- none
"""


def parsed(md):
    tables = lanes.parse_tables(md)
    tasks = {t.id: t for t in lanes.parse_tasks(tables)}
    lanes.assign_waves(tasks)
    return tasks


def test_waves_follow_hard_dependencies_only():
    tasks = parsed(tasks_md())
    assert [tasks[i].wave for i in ("T1", "T3", "T2", "R1")] == [1, 1, 2, 3]


def test_soft_dependency_can_start_now_but_is_noted():
    tasks = parsed(tasks_md())
    assert tasks["T3"].soft == ["T1"] and tasks["T3"].hard == []
    block = lanes.build(tasks_md())
    assert "chỉ HOÀN TẤT sau khi T1 merge" in block


def test_ready_and_waiting_follow_status():
    tasks = parsed(tasks_md())
    assert lanes.state(tasks["T1"], tasks) == "ready"
    assert lanes.state(tasks["T3"], tasks) == "ready"
    assert lanes.state(tasks["T2"], tasks) == "waiting"
    tasks = parsed(tasks_md({"T1": "merged"}))
    assert lanes.state(tasks["T2"], tasks) == "ready"


def test_review_task_needs_only_a_pushed_pr():
    tasks = parsed(tasks_md({"T2": "review"}))
    assert lanes.state(tasks["R1"], tasks) == "ready"
    tasks = parsed(tasks_md({"T2": "doing"}))
    assert lanes.state(tasks["R1"], tasks) == "waiting"


def test_block_names_people_and_commands():
    block = lanes.build(tasks_md())
    assert "@Anh-08 -> T1" in block and "@NguyenQBao -> T3" in block
    assert "git switch -c task/t1" in block and "claude" in block and "codex" in block
    assert "git diff origin/main...origin/task/t2" in block  # review task is read-only
    assert "gh pr merge <số PR> --merge" in block
    assert "merge `T1` → báo" in block


def test_same_wave_file_overlap_is_flagged():
    clash = tasks_md(t3_files="`src/features/x/helpers.py`")
    assert "trùng file" in lanes.build(clash)
    assert "trùng file" not in lanes.build(tasks_md())


def test_unknown_role_is_reported():
    row = "| T9 | Mystery | nobody | `docs/` | - | todo |\n"
    assert "chưa có trong bảng Team" in lanes.build(tasks_md(extra_rows=row))


def test_dependency_cycle_is_rejected():
    rows = "| A1 | a | claude | `a/` | B1 | todo |\n| B1 | b | claude | `b/` | A1 | todo |\n"
    with pytest.raises(ValueError, match="cycle"):
        lanes.build(tasks_md(extra_rows=rows))


def test_splice_replaces_only_the_marked_block():
    guide = f"intro\n{lanes.START}\nold\n{lanes.END}\noutro\n- [x] ticked\n"
    result = lanes.splice(guide, "NEW")
    assert result == f"intro\n{lanes.START}\nNEW\n{lanes.END}\noutro\n- [x] ticked\n"
    with pytest.raises(ValueError, match="markers"):
        lanes.splice("no markers here", "NEW")


def test_cli_writes_the_guide_and_fails_cleanly(tmp_path):
    tasks = tmp_path / "TASKS.md"
    guide = tmp_path / "DAY_OF.md"
    tasks.write_text(tasks_md(), encoding="utf-8")
    guide.write_text(f"head\n{lanes.START}\n{lanes.END}\ntail\n", encoding="utf-8")
    assert lanes.main(["--tasks", str(tasks), "--guide", str(guide)]) == 0
    text = guide.read_text(encoding="utf-8")
    assert text.startswith("head\n") and text.endswith("tail\n") and "@Anh-08 -> T1" in text
    guide.write_text("no markers", encoding="utf-8")
    assert lanes.main(["--tasks", str(tasks), "--guide", str(guide)]) == 1


def test_set_statuses_edits_only_the_status_cell():
    md = tasks_md()
    new = lanes.set_statuses(md, {"T1": "merged", "R1": "doing"})
    tasks = parsed(new)
    assert tasks["T1"].status == "merged" and tasks["R1"].status == "doing"
    assert tasks["T2"].status == "todo" and tasks["T2"].files == parsed(md)["T2"].files
    assert new.count("\n") == md.count("\n")
    with pytest.raises(ValueError, match="no such task"):
        lanes.set_statuses(md, {"T99": "merged"})


def test_set_option_rejects_unknown_status_and_updates_files(tmp_path):
    with pytest.raises(ValueError, match="status"):
        lanes.parse_updates(["T1=finished"])
    tasks, guide = tmp_path / "TASKS.md", tmp_path / "DAY_OF.md"
    tasks.write_text(tasks_md(), encoding="utf-8")
    guide.write_text(f"{lanes.START}\n{lanes.END}\n", encoding="utf-8")
    args = ["--tasks", str(tasks), "--guide", str(guide), "--set", "T1=merged", "T2=doing"]
    assert lanes.main(args) == 0
    assert parsed(tasks.read_text(encoding="utf-8"))["T1"].status == "merged"
    assert "ĐANG LÀM" in guide.read_text(encoding="utf-8")


def test_backup_integrator_and_partner_qa_are_shown_when_in_the_team_table():
    md = tasks_md().replace(
        "| human-A | Nguyen-Le-Tuan | |",
        "| human-A | Nguyen-Le-Tuan | |\n| partner-qa | NguyenQBao | |\n"
        "| backup-integrator | Anh-08 | |",
    )
    block = lanes.build(md)
    assert "partner-qa (hỏi đối tác)" in block
    assert "Người merge dự phòng khi tôi bận: Anh-08" in block
    assert "Người merge dự phòng" not in lanes.build(tasks_md())
