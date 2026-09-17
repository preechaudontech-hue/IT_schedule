"""Daily work-schedule announcement to a LINE group.

Reads a Google Sheet, keeps rows dated today (Asia/Bangkok) or later, formats
a Thai message grouped by date and pushes it to a LINE group via the
Messaging API.

Env vars:
  LINE_CHANNEL_ACCESS_TOKEN  LINE Messaging API channel access token
  LINE_GROUP_ID              target group id (Cxxxxxxxx...)
  GOOGLE_SA_JSON             service-account key JSON (raw string)
  SHEET_ID                   spreadsheet id
  SHEET_WORKSHEET            worksheet/tab name (default: schedule)
  TODO_WORKSHEET             undated "อย่าลืม" items worksheet/tab (default: todos)
  SEND_WHEN_EMPTY            "1" to still send a message when nothing scheduled (default: 1)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime, timezone, timedelta
from typing import Any, Iterable

AFTERNOON_CUTOFF_HOUR = 12

BKK_TZ = timezone(timedelta(hours=7))

_TH_MONTHS = [
    "", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]
_TH_WEEKDAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]

# Accepted header names -> canonical key
_COLS = {
    "date": ["วันที่", "date"],
    "name": ["ชื่อ-สกุล", "ชื่อ", "name", "ผู้ปฏิบัติงาน"],
    "task": ["รายการ/ภารกิจ", "รายการ", "ภารกิจ", "task", "งาน"],
    "time": ["เวลา", "time"],
    "place": ["สถานที่", "place", "location"],
    "note": ["หมายเหตุ", "note", "remark"],
}

# Same idea for the undated "อย่าลืม" (todo) sheet tab
_TODO_COLS = {
    "task": ["รายการ", "ภารกิจ", "task"],
    "name": ["ผู้รับผิดชอบ", "ชื่อ-สกุล", "ชื่อ", "name"],
    "done": ["เสร็จสิ้น", "done", "สถานะ"],
    "note": ["หมายเหตุ", "note"],
}


def thai_date(d: date) -> str:
    yy = (d.year + 543) % 100  # 2-digit Buddhist year, e.g. 2026 -> 69
    return f"วัน{_TH_WEEKDAYS[d.weekday()]}ที่ {d.day} {_TH_MONTHS[d.month]} {yy:02d}"


def _lookup_raw(row: dict[str, Any], key: str, cols: dict[str, list[str]]) -> Any:
    for header in cols[key]:
        for k, v in row.items():
            if str(k).strip().lower() == header.lower():
                return v
    return None


def _get(row: dict[str, Any], key: str, cols: dict[str, list[str]] = _COLS) -> str:
    raw = _lookup_raw(row, key, cols)
    return "" if raw is None else str(raw).strip()


def _todo_get(row: dict[str, Any], key: str) -> str:
    return _get(row, key, _TODO_COLS)


def _is_done(row: dict[str, Any]) -> bool:
    """A todo's "เสร็จสิ้น" cell: a real Sheets checkbox comes back as a bool
    via gspread; a hand-typed cell might just be text like "TRUE"/"ติ๊ก"."""
    raw = _lookup_raw(row, "done", _TODO_COLS)
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("true", "1", "✓", "เสร็จ", "yes")


def pending_todos(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if not _is_done(row)]


def format_todos_section(rows: Iterable[dict[str, Any]]) -> list[str]:
    """Lines for the "อย่าลืม" block: a title line followed by one numbered
    line per pending item. Returns [] (no title either) when nothing is
    pending, so callers can skip the section entirely rather than print an
    empty heading."""
    pending = pending_todos(rows)
    if not pending:
        return []
    lines = ["📌 อย่าลืม / สิ่งที่ต้องปฏิบัติ"]
    for i, row in enumerate(pending, start=1):
        name = _todo_get(row, "name")
        task = _todo_get(row, "task")
        note = _todo_get(row, "note")
        lines.append(f"{i}) {name or '(ไม่ระบุผู้รับผิดชอบ)'} — {task or '(ไม่ระบุรายการ)'}")
        if note:
            lines.append(f"   - {note}")
    return lines


def _parse_date(raw: str) -> date | None:
    raw = str(raw).strip()
    if not raw:
        return None
    # Google may hand back a date cell as a serial number (days since 1899-12-30)
    try:
        n = float(raw)
        if 1 < n < 200000:
            return date(1899, 12, 30) + timedelta(days=int(n))
    except ValueError:
        pass
    raw = raw.split("T")[0].split(" ")[0]  # drop any time part
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def rows_for_day(rows: Iterable[dict[str, Any]], target: date) -> list[dict[str, Any]]:
    """Rows dated exactly `target`."""
    out = []
    for row in rows:
        if _parse_date(_get(row, "date")) == target:
            out.append(row)
    return out


def rows_from_day(rows: Iterable[dict[str, Any]], target: date) -> list[dict[str, Any]]:
    """Rows dated `target` or any later date (undated rows are dropped)."""
    out = []
    for row in rows:
        d = _parse_date(_get(row, "date"))
        if d is not None and d >= target:
            out.append(row)
    return out


def _sort_key(row: dict[str, Any]) -> str:
    t = _get(row, "time")
    return t if t else "99:99"


def _start_hour(row: dict[str, Any]) -> int | None:
    """Best-effort hour the row's time starts at, e.g. '13.00 น.' -> 13."""
    m = re.search(r"(\d{1,2})[:.]\d{2}", _get(row, "time"))
    if not m:
        return None
    h = int(m.group(1))
    return h if 0 <= h <= 23 else None


def afternoon_rows(rows: Iterable[dict[str, Any]], target: date) -> list[dict[str, Any]]:
    """Today's rows whose time starts at/after AFTERNOON_CUTOFF_HOUR.

    Rows with no parseable time are excluded — they were already covered by
    the morning announcement, so the noon reminder only repeats items that
    are clearly scheduled for the afternoon.
    """
    out = []
    for row in rows_for_day(rows, target):
        h = _start_hour(row)
        if h is not None and h >= AFTERNOON_CUTOFF_HOUR:
            out.append(row)
    return out


def format_afternoon_message(rows: list[dict[str, Any]], target: date) -> str | None:
    """Same-day, afternoon-only reminder. Returns None when there's nothing
    to say — the caller should skip sending entirely in that case."""
    if not rows:
        return None
    lines = [f"🔔 เตือนภารกิจช่วงบ่าย ประจำ{thai_date(target)}", ""]
    for i, row in enumerate(sorted(rows, key=_sort_key), start=1):
        lines.extend(_format_item(i, row))
    lines.append("")
    lines.append("— Bot แจ้งเตือน")
    return "\n".join(lines)


def _format_item(i: int, row: dict[str, Any]) -> list[str]:
    """One schedule item as a numbered head (time only) plus dash-bulleted
    name / task / place / note lines — no time end is required, an item with
    only a start time (or no time at all) still formats cleanly."""
    name = _get(row, "name")
    task = _get(row, "task")
    tm = _get(row, "time")
    place = _get(row, "place")
    note = _get(row, "note")

    head = f"{i}) {tm}" if tm else f"{i})"
    lines = [head, f"   - {name or '(ไม่ระบุชื่อ)'}", f"   - {task or '(ไม่ระบุภารกิจ)'}"]
    if place:
        lines.append(f"   - {place}")
    if note:
        lines.append(f"   - {note}")
    return lines


def format_message(rows: list[dict[str, Any]], target: date, send_when_empty: bool = True) -> str | None:
    """Format rows dated `target` or later, grouped by date (today first)."""
    header = f"📢 แจ้งกำหนดการปฏิบัติงาน\n{thai_date(target)}เป็นต้นไป"
    if not rows:
        if not send_when_empty:
            return None
        return f"{header}\n\n— ไม่มีกำหนดการที่บันทึกไว้\n\n— Bot แจ้งเตือน"

    by_date: dict[date, list[dict[str, Any]]] = {}
    for row in rows:
        d = _parse_date(_get(row, "date"))
        by_date.setdefault(d, []).append(row)

    lines = [header, ""]
    for d in sorted(by_date.keys()):
        lines.append(f"📅 {thai_date(d)}")
        for i, row in enumerate(sorted(by_date[d], key=_sort_key), start=1):
            lines.extend(_format_item(i, row))
        lines.append("")

    lines.append("— Bot แจ้งเตือน")
    return "\n".join(lines)


_FOOTER = "— Bot แจ้งเตือน"


def append_section(message: str, section_lines: list[str]) -> str:
    """Insert an extra block (e.g. the todos section) just before the
    footer of an already-formatted message. No-op if there's nothing to
    add, so callers can call this unconditionally."""
    if not section_lines:
        return message
    lines = message.split("\n")
    if lines and lines[-1] == _FOOTER:
        lines = lines[:-1]
    lines.extend(section_lines)
    lines.append("")
    lines.append(_FOOTER)
    return "\n".join(lines)


def todos_only_message(target: date, section_lines: list[str]) -> str:
    """Standalone message for when the schedule has nothing to say but
    there are still pending "อย่าลืม" items to remind about."""
    header = f"📢 แจ้งเตือนประจำ{thai_date(target)}"
    return "\n".join([header, "", *section_lines, "", _FOOTER])


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        print(f"ERROR: missing env var {name}", file=sys.stderr)
        sys.exit(2)
    return val or ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print the message, do not send")
    ap.add_argument("--date", help="override target date (YYYY-MM-DD), for testing")
    ap.add_argument("--debug", action="store_true", help="dump every row read from the sheet")
    ap.add_argument(
        "--session", choices=["morning", "afternoon"], default="morning",
        help="morning: today + upcoming days. "
             "afternoon: today's afternoon items only. "
             "Both sessions also append the 'อย่าลืม' todos section; skipped "
             "entirely only if both the schedule part and the todos are empty.",
    )
    args = ap.parse_args()

    target = _parse_date(args.date) if args.date else datetime.now(BKK_TZ).date()
    if target is None:
        print("ERROR: bad --date", file=sys.stderr)
        return 2

    send_when_empty = _env("SEND_WHEN_EMPTY", "1") != "0"

    from sheet_client import fetch_rows

    rows = fetch_rows(
        _env("GOOGLE_SA_JSON", required=True),
        _env("SHEET_ID", required=True),
        _env("SHEET_WORKSHEET", "schedule"),
    )
    if args.debug:
        print(f"อ่านได้ {len(rows)} แถวจากแท็บ '{_env('SHEET_WORKSHEET', 'schedule')}'")
        print(f"วันที่เป้าหมาย (วันนี้): {target}")
        for i, row in enumerate(rows, start=1):
            raw = _get(row, "date")
            print(f"  [{i}] date_raw={raw!r} -> parsed={_parse_date(raw)} | "
                  f"name={_get(row, 'name')!r} task={_get(row, 'task')!r}")
            if i == 1:
                print(f"      หัวคอลัมน์ที่เจอ: {list(row.keys())}")
        print("-" * 40)

    def _fetch_todos_lines() -> list[str]:
        try:
            todo_rows = fetch_rows(
                _env("GOOGLE_SA_JSON", required=True),
                _env("SHEET_ID", required=True),
                _env("TODO_WORKSHEET", "todos"),
            )
            lines = format_todos_section(todo_rows)
            if args.debug:
                pending = pending_todos(todo_rows)
                print(f"อ่านได้ {len(todo_rows)} แถวจากแท็บ '{_env('TODO_WORKSHEET', 'todos')}' "
                      f"({len(pending)} รายการยังไม่เสร็จ)")
            return lines
        except Exception as exc:  # e.g. the "todos" tab doesn't exist yet
            if args.debug:
                print(f"อ่านแท็บ 'อย่าลืม' ไม่ได้ (ข้ามส่วนนี้): {exc}")
            return []

    if args.session == "afternoon":
        selected = afternoon_rows(rows, target)
        message = format_afternoon_message(selected, target)
        todos_lines = _fetch_todos_lines()

        if message is None and not todos_lines:
            print("ไม่มีภารกิจช่วงบ่ายวันนี้และไม่มี 'อย่าลืม' ค้าง — ข้ามรอบนี้ ไม่ส่ง")
            return 0
        message = todos_only_message(target, todos_lines) if message is None else append_section(message, todos_lines)
        label = f"afternoon item(s) for {target}" + (" (+ todo(s))" if todos_lines else "")
    else:
        selected = rows_from_day(rows, target)
        message = format_message(selected, target, send_when_empty)
        todos_lines = _fetch_todos_lines()

        if message is None and not todos_lines:
            print("Nothing scheduled/pending and SEND_WHEN_EMPTY=0 — not sending.")
            return 0
        message = todos_only_message(target, todos_lines) if message is None else append_section(message, todos_lines)
        label = f"item(s) from {target} onward" + (" (+ todo(s))" if todos_lines else "")

    if args.dry_run:
        print(message)
        return 0

    from line_client import push_text

    push_text(
        _env("LINE_CHANNEL_ACCESS_TOKEN", required=True),
        _env("LINE_GROUP_ID", required=True),
        message,
    )
    print(f"Sent {len(selected)} {label}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
