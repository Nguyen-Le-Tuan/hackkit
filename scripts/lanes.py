#!/usr/bin/env python3
"""Rebuild the "current workflow" block of docs/DAY_OF.md from docs/TASKS.md.

Run `make lanes` (or `python scripts/lanes.py`) after you edit docs/TASKS.md. To change a
status in one command: `make lanes SET="T1=merged T2=doing"`. It rewrites ONLY the text between the LANES markers in the guide, so the rest of the
guide (and any boxes you ticked) is left alone. Standard library only.

TASKS.md must contain two tables, and may contain a third:
  * Team  : columns Role | Person | Tool        (maps `claude`, `codex`, `human-A`... to people)
  * Tasks : columns ID | Task | Owner | Files it may touch | Depends on | Status
  * Milestones (optional): columns Milestone | Due (HH:MM) | Done (yes/no); late ones get a warning
`Depends on` lists task ids; an id ending in `~` is a SOFT dependency (the task may start now
but can only finish after that task is merged).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

START = "<!-- LANES:START -->"
END = "<!-- LANES:END -->"
DONE, ACTIVE = "merged", ("doing", "review")
ROLE_NOTES = {
    "human-a": "điều phối, review và merge PR",
    "human-b": "QA, chạy demo",
    "human-c": "pitch, UX, Devpost (từ phút 0)",
    "claude": "agent",
    "codex": "agent",
    "partner-qa": "hỏi đối tác",
    "researcher": "tìm dữ liệu công khai",
    "backup-integrator": "merge dự phòng",
}
STATE_VI = {
    "ready": "sẵn sàng",
    "waiting": "đang chờ",
    "doing": "đang làm",
    "review": "chờ merge",
    "blocked": "bị chặn",
    "done": "xong",
}


@dataclass
class Task:
    id: str
    title: str
    role: str
    files: list[str]
    hard: list[str]
    soft: list[str]
    status: str
    wave: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def is_review(self) -> bool:
        return self.id.upper().startswith("R")

    @property
    def branch(self) -> str:
        return f"task/{self.id.lower()}"


@dataclass
class Member:
    person: str
    tool: str

    @property
    def launcher(self) -> str:
        low = self.tool.lower()
        return "claude" if "claude" in low else "codex" if "codex" in low else ""


@dataclass
class Milestone:
    name: str
    due: str  # "HH:MM", or "" when the team has not set it yet
    done: bool


def parse_milestones(tables: list[list[list[str]]]) -> list[Milestone]:
    for table in tables:
        header = [c.lower() for c in table[0]]
        if header and ("milestone" in header[0] or "mốc" in header[0]):
            d, x = column(table[0], "due", "hạn"), column(table[0], "done", "xong")
            return [
                Milestone(
                    row[0].replace("`", "").strip(),
                    row[d].strip(),
                    row[x].strip().lower() in {"yes", "y", "x", "[x]", "done", "rồi", "xong", "✅"},
                )
                for row in table[1:]
                if row and row[0].strip() and len(row) > max(d, x)
            ]
    return []


def milestone_lines(milestones: list[Milestone], now: datetime) -> tuple[list[str], list[str]]:
    """(warnings for the top of the block, the milestone table)."""
    if not milestones:
        return [], []
    warnings, rows = [], ["### Mốc thời gian", "", "| Mốc | Hạn | Trạng thái |", "|---|---|---|"]
    for m in milestones:
        if m.done:
            status = "✅ xong"
        elif not re.fullmatch(r"\d{1,2}:\d{2}", m.due):
            status = "— chưa đặt giờ (điền HH:MM vào docs/TASKS.md)"
        else:
            hh, mm = (int(x) for x in m.due.split(":"))
            delta = (now.replace(hour=hh, minute=mm, second=0, microsecond=0) - now).total_seconds()
            minutes = int(abs(delta) // 60)
            if delta < 0:
                status = f"⚠ **TRỄ {minutes} phút**"
                warnings.append(
                    f"> ⚠ Trễ mốc **{m.name}** ({m.due}): cắt bớt phạm vi, đừng dời mốc."
                )
            else:
                status = f"⏳ còn {minutes} phút"
        rows.append(f"| {m.name} | {m.due or '—'} | {status} |")
    return warnings, [*rows, ""]


def parse_tables(text: str) -> list[list[list[str]]]:
    """Return every markdown table as a list of rows (each row a list of cell strings)."""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in [*text.splitlines(), ""]:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            current.append(cells)
        elif current:
            tables.append(current)
            current = []
    return tables


def column(header: list[str], *names: str) -> int:
    for i, cell in enumerate(header):
        if any(n in cell.lower() for n in names):
            return i
    raise ValueError(f"TASKS.md: no column matching {names} in header {header}")


def parse_team(tables: list[list[list[str]]]) -> dict[str, Member]:
    for table in tables:
        header = [c.lower() for c in table[0]]
        if header[:1] == ["role"] and any("person" in c for c in header):
            p, t = column(table[0], "person"), column(table[0], "tool")
            return {
                r[0].strip("` ").lower(): Member(r[p].strip("` "), r[t].strip("` "))
                for r in table[1:]
                if r and r[0].strip("` ")
            }
    raise ValueError("TASKS.md: Team table (Role | Person | Tool) not found")


def ids_in(cell: str) -> tuple[list[str], list[str]]:
    hard, soft = [], []
    for tok in re.findall(r"[A-Za-z]+\d+~?", cell):
        (soft if tok.endswith("~") else hard).append(tok.rstrip("~").upper())
    return hard, soft


def parse_tasks(tables: list[list[list[str]]]) -> list[Task]:
    for table in tables:
        header = [c.lower() for c in table[0]]
        if header[:1] == ["id"] and any("owner" in c for c in header):
            i, t, o = column(table[0], "id"), column(table[0], "task"), column(table[0], "owner")
            f, d, s = (column(table[0], n) for n in ("files", "depends", "status"))
            tasks = []
            for row in table[1:]:
                if len(row) <= max(i, t, o, f, d, s) or not row[i].strip():
                    continue
                hard, soft = ids_in(row[d])
                role = (row[o].replace("`", "").split() or [""])[0].strip(",").lower()
                status = (row[s].replace("`", "").split() or ["todo"])[0].lower()
                tasks.append(
                    Task(
                        id=row[i].strip("` ").upper(),
                        title=row[t].replace("`", "").strip(),
                        role=role,
                        files=re.findall(r"`([^`]+)`", row[f]),
                        hard=hard,
                        soft=soft,
                        status=status,
                    )
                )
            return tasks
    raise ValueError("TASKS.md: task table (ID | Task | Owner | ... ) not found")


def assign_waves(tasks: dict[str, Task]) -> None:
    """Wave = longest chain of HARD dependencies. Soft dependencies do not delay the start."""
    visiting: set[str] = set()

    def depth(tid: str) -> int:
        task = tasks[tid]
        if task.wave:
            return task.wave
        if tid in visiting:
            raise ValueError(f"TASKS.md: dependency cycle through {tid}")
        visiting.add(tid)
        known = [d for d in task.hard if d in tasks]
        for d in task.hard:
            if d not in tasks:
                task.notes.append(f"phụ thuộc vào {d} nhưng không có task đó")
        task.wave = 1 + max((depth(d) for d in known), default=0)
        visiting.discard(tid)
        return task.wave

    for tid in tasks:
        depth(tid)


def satisfied(task: Task, dep: Task) -> bool:
    """A review task may start once its target is pushed for review; others need a merge."""
    return dep.status == DONE or (task.is_review and dep.status == "review")


def state(task: Task, tasks: dict[str, Task]) -> str:
    if task.status == DONE:
        return "done"
    if task.status in ACTIVE or task.status == "blocked":
        return task.status
    waiting = [d for d in task.hard if d in tasks and not satisfied(task, tasks[d])]
    return "waiting" if waiting else "ready"


def overlaps(a: Task, b: Task) -> list[str]:
    hits = []
    for x in a.files:
        for y in b.files:
            xs, ys = x.rstrip("/"), y.rstrip("/")
            if xs == ys or xs.startswith(ys + "/") or ys.startswith(xs + "/"):
                hits.append(f"`{x}` ~ `{y}`")
    return hits


def repo_slug() -> tuple[str, str]:
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        ).stdout.strip()
        m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url)
        if m:
            return m.group(1), m.group(2)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return "<chu-repo>", Path.cwd().name


def build(tasks_md: str, now: datetime | None = None) -> str:
    tables = parse_tables(tasks_md)
    team = parse_team(tables)
    task_list = parse_tasks(tables)
    tasks = {t.id: t for t in task_list}
    assign_waves(tasks)
    owner, repo = repo_slug()
    now = now or datetime.now()

    def who(task: Task) -> Member:
        return team.get(task.role, Member(task.role or "(chưa giao)", ""))

    def label(task: Task) -> str:
        m = who(task)
        return f"{m.person} ({m.tool})" if m.tool else m.person

    out: list[str] = [
        f"> Tự sinh bởi `make lanes` lúc {now:%Y-%m-%d %H:%M} từ `docs/TASKS.md`. "
        "**Đừng sửa tay trong khối này**: sửa `docs/TASKS.md` (cột Status, Owner) rồi chạy lại.",
        "",
    ]
    for t in task_list:
        if t.role not in team:
            out.append(f"> ⚠ {t.id}: vai trò `{t.role or '(trống)'}` chưa có trong bảng Team.")
        out += [f"> ⚠ {t.id}: {n}" for n in t.notes]
    late, milestone_table = milestone_lines(parse_milestones(tables), now)
    out += late
    if milestone_table:
        out += ["", *milestone_table]

    # --- people ---
    out += [
        "### Đội hình và việc được giao",
        "",
        "| Người | Công cụ | Vai trò: việc |",
        "|---|---|---|",
    ]
    people: dict[str, list[str]] = {}
    for role, m in team.items():
        mine = [t.id for t in task_list if t.role == role]
        note = f" ({ROLE_NOTES[role]})" if role in ROLE_NOTES else ""
        people.setdefault(m.person, []).append(f"{role}{note}: {', '.join(mine) or '—'}")
    for person, parts in people.items():
        tools = sorted({m.tool for m in team.values() if m.person == person and m.tool})
        out.append(f"| {person} | {' / '.join(tools) or '—'} | {'; '.join(parts)} |")

    # --- right now ---
    groups: dict[str, list[str]] = {
        k: [] for k in ("ready", "doing", "review", "waiting", "blocked", "done")
    }
    for t in task_list:
        s = state(t, tasks)
        line = f"`{t.id}` {t.title} — {label(t)}"
        if s == "waiting":
            wait = [
                f"{d} ({label(tasks[d])})"
                for d in t.hard
                if d in tasks and not satisfied(t, tasks[d])
            ]
            line += f" — chờ {', '.join(wait)}"
        if s in ("ready", "doing") and any(tasks[d].status != DONE for d in t.soft if d in tasks):
            line += f" — làm được ngay, chỉ HOÀN TẤT sau khi {', '.join(t.soft)} merge"
        groups[s].append(line)
    titles = {
        "ready": "▶ SẴN SÀNG làm ngay (chạy song song được)",
        "doing": "🔄 ĐANG LÀM",
        "review": "👀 ĐÃ ĐẨY PR, CHỜ TÔI REVIEW/MERGE",
        "waiting": "⏳ ĐANG CHỜ",
        "blocked": "⛔ BỊ CHẶN (hỏi tôi)",
        "done": "✅ XONG",
    }
    out += ["", "### Ngay bây giờ", ""]
    for key, head in titles.items():
        if groups[key]:
            out += [f"**{head}**", *[f"- {line}" for line in groups[key]], ""]

    # --- waves ---
    out += ["### Các đợt (thứ tự tối ưu, tính từ phụ thuộc)", ""]
    for w in range(1, max((t.wave for t in task_list), default=0) + 1):
        wave = [t for t in task_list if t.wave == w]
        out.append(f"**Đợt {w}**" + (" (chạy song song)" if len(wave) > 1 else ""))
        out += [f"- `{t.id}` {t.title} — {label(t)}" for t in wave]
        for i, a in enumerate(wave):
            for b in wave[i + 1 :]:
                if hit := overlaps(a, b):
                    out.append(
                        f"- ⚠ **{a.id} và {b.id} trùng file** ({'; '.join(hit)}): không được chạy song song"
                    )
        out.append("")

    # --- detail table ---
    out += [
        "### Bảng chi tiết",
        "",
        "| ID | Việc | Người | Nhánh | Chờ | Trạng thái |",
        "|---|---|---|---|---|---|",
    ]
    for t in task_list:
        wait = [f"{d} ({who(tasks[d]).person})" for d in t.hard if d in tasks]
        wait += [f"{d}~ ({who(tasks[d]).person}, chỉ để hoàn tất)" for d in t.soft if d in tasks]
        branch = "(không cần, chỉ đọc)" if t.is_review else f"`{t.branch}`"
        out.append(
            f"| {t.id} | {t.title} | {who(t).person} | {branch} | {', '.join(wait) or '—'} | {t.status} |"
        )

    # --- group-chat message ---
    out += ["### Tin nhắn cho nhóm chat (copy)", "", "```text"]
    for key in ("ready", "waiting"):
        todo = [t for t in task_list if state(t, tasks) == key]
        if todo:
            out.append("LÀM NGAY:" if key == "ready" else "CHUẨN BỊ, CHỜ TÔI BÁO:")
            out += [f"@{who(t).person} -> {t.id}: {t.title}" for t in todo]
    out += ["```", ""]

    # --- commands per person ---
    out += ["### Lệnh cho từng người (copy–paste)", ""]
    for person in people:
        mine = [t for t in task_list if who(t).person == person and state(t, tasks) != "done"]
        if not mine:
            continue
        out += [f"#### {person}", ""]
        for t in mine:
            m = who(t)
            st = state(t, tasks)
            out += [f"**{t.id}: {t.title}** — _{STATE_VI[st]}_", ""]
            if st == "waiting":
                wait = ", ".join(d for d in t.hard if d in tasks and not satisfied(t, tasks[d]))
                out += [f"⏳ CHƯA chạy các lệnh dưới. Chờ {wait} xong, tôi sẽ báo.", ""]
            if t.is_review:
                target = next((d for d in t.hard if d in tasks), "T?").lower()
                out += [
                    "```bash",
                    "git fetch origin",
                    f"git diff origin/main...origin/task/{target} | less",
                    m.launcher or "# đọc diff và ghi nhận xét",
                    "```",
                    "Lời nhắc cho agent:",
                    "```text",
                    f"Review nhánh origin/task/{target} so với main (git diff origin/main...origin/task/{target}). "
                    "Đối chiếu với phần Contract trong docs/TASKS.md. Chỉ báo cáo lỗi và rủi ro theo mức độ, "
                    "không sửa file nào.",
                    "```",
                    "",
                ]
            elif m.launcher:
                files = ", ".join(t.files) or "các file được giao trong docs/TASKS.md"
                soft = (
                    f" Task này chỉ phụ thuộc mềm vào {', '.join(t.soft)}: bắt đầu ngay được, nhưng chỉ chạy eval "
                    f"và hoàn tất sau khi {', '.join(t.soft)} đã merge vào main (khi đó chạy "
                    "`git fetch origin && git merge origin/main`)."
                    if t.soft
                    else ""
                )
                out += [
                    "```bash",
                    f"cd {repo}   # thư mục repo bạn đã clone",
                    "git switch main && git pull origin main",
                    f"git switch -c {t.branch}",
                    m.launcher,
                    "```",
                    "Lời nhắc cho agent:",
                    "```text",
                    f"Đọc AGENTS.md, docs/spec.md và docs/TASKS.md. Chỉ làm task {t.id}: {t.title}. "
                    f"Chỉ sửa các file: {files}. Tuân thủ đúng phần Contract trong docs/TASKS.md."
                    f"{soft} Chạy pytest và ruff check . rồi commit nhỏ; xong thì dừng và báo kết quả. "
                    "Không merge, không push lên main. PR (nếu mở) luôn nhắm vào main, không nhắm vào nhánh khác.",
                    "```",
                    "Khi agent báo xong:",
                    "```bash",
                    "make test && make lint",
                    f"git push -u origin {t.branch}",
                    "gh pr create --base main --fill",
                    "```",
                    "Rồi nhắn cho tôi số PR.",
                    "",
                ]
            else:
                out += [
                    "```bash",
                    f"cd {repo}   # thư mục repo bạn đã clone",
                    "git switch main && git pull origin main",
                    "make test && make lint && make demo   # kiểm tra nhanh trước khi làm",
                    "```",
                    f"Việc thủ công: {t.title}. File được sửa: {', '.join(t.files) or '(không sửa file)'}.",
                    "Nếu việc này có sửa file, làm trên nhánh riêng rồi mở PR:",
                    "```bash",
                    f"git switch -c {t.branch}",
                    "# ...làm việc, có thể mở claude hoặc codex để hỗ trợ...",
                    f'git add -A && git commit -m "{t.id}: cập nhật" && git push -u origin {t.branch}',
                    "gh pr create --base main --fill",
                    "```",
                    "",
                ]

    # --- integrator ---
    out += [
        f"#### {team.get('human-a', Member('tôi', '')).person} (điều phối): mỗi khi có PR",
        "",
        "```bash",
        "gh pr list",
        "make verify PR=<số PR>              # gộp thử + guard + lint + test + smoke; cần 'MERGE OK'",
        "gh pr checks <số PR> --watch        # CI cũng phải xanh",
        "gh pr merge <số PR> --merge",
        "git switch main && git pull origin main",
        "```",
        "`make verify` báo PR không nhắm vào `main`? Sửa: `gh pr edit <số PR> --base main`.",
        f"PR bị lạc hậu so với main? `gh api -X PUT repos/{owner}/{repo}/pulls/<số PR>/update-branch`, "
        "hoặc người làm chạy `git fetch origin && git merge origin/main && git push`.",
        "",
        *(
            [
                f"Người merge dự phòng khi tôi bận: {team['backup-integrator'].person} "
                "(chỉ merge PR xanh, không merge PR của chính mình).",
                "",
            ]
            if "backup-integrator" in team
            else []
        ),
        "**Sau khi merge một task, báo ngay cho người đang chờ:**",
    ]
    for t in task_list:
        waiting = [u for u in task_list if t.id in u.hard + u.soft]
        if waiting:
            names = ", ".join(f"{who(u).person} ({u.id})" for u in waiting)
            out.append(
                f"- merge `{t.id}` → báo {names}: chạy `git fetch origin && git merge origin/main`"
            )
    out.append("")
    return "\n".join(out)


STATUSES = ("todo", "doing", "review", "merged", "blocked")


def set_statuses(tasks_md: str, updates: dict[str, str]) -> str:
    """Return tasks_md with the Status cell of the given task ids replaced."""
    lines = tasks_md.splitlines(keepends=True)
    status_col, done = -1, set()
    for n, line in enumerate(lines):
        if not line.strip().startswith("|"):
            status_col = -1
            continue
        cells = line.rstrip("\n").split("|")
        names = [c.strip().lower() for c in cells]
        if "id" in names and any("owner" in c for c in names):
            status_col = next(i for i, c in enumerate(names) if "status" in c)
        elif status_col > 0 and len(cells) > status_col:
            tid = cells[1].strip("` ").upper()
            if tid in updates:
                cells[status_col] = f" {updates[tid]} "
                lines[n] = "|".join(cells) + ("\n" if line.endswith("\n") else "")
                done.add(tid)
    missing = sorted(set(updates) - done)
    if missing:
        raise ValueError(f"no such task id in TASKS.md: {', '.join(missing)}")
    return "".join(lines)


def parse_updates(pairs: list[str]) -> dict[str, str]:
    updates = {}
    for pair in pairs:
        tid, _, status = pair.partition("=")
        if status not in STATUSES or not tid:
            raise ValueError(f"--set expects ID=status with status in {STATUSES}, got {pair!r}")
        updates[tid.strip().upper()] = status
    return updates


def splice(guide: str, block: str) -> str:
    if START not in guide or END not in guide:
        raise ValueError(f"guide is missing the {START} / {END} markers")
    head, rest = guide.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tasks", type=Path, default=Path("docs/TASKS.md"))
    ap.add_argument("--guide", type=Path, default=Path("docs/DAY_OF.md"))
    ap.add_argument("--print", action="store_true", help="print the block, do not write the guide")
    ap.add_argument("--set", nargs="+", metavar="ID=status", help="e.g. --set T1=merged T2=doing")
    args = ap.parse_args(argv)
    try:
        if args.set:
            updated = set_statuses(args.tasks.read_text(encoding="utf-8"), parse_updates(args.set))
            args.tasks.write_text(updated, encoding="utf-8")
            print(f"Updated Status in {args.tasks}: {' '.join(args.set)}")
        block = build(args.tasks.read_text(encoding="utf-8"))
        if args.print:
            print(block)
            return 0
        args.guide.write_text(
            splice(args.guide.read_text(encoding="utf-8"), block), encoding="utf-8"
        )
    except (OSError, ValueError) as err:
        print(f"lanes: {err}", file=sys.stderr)
        return 1
    print(f"Updated {args.guide} from {args.tasks}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
