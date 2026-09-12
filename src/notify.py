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


def thai_date(d: date) -> str:
    yy = (d.year + 543) % 100  # 2-digit Buddhist year, e.g. 2026 -> 69
    return f"วัน{_TH_WEEKDAYS[d.weekday()]}ที่ {d.day} {_TH_MONTHS[d.month]} {yy:02d}"


def _get(row: dict[str, Any], key: str) -> str:
    for header in _COLS[key]:
        for k, v in row.items():
            if str(k).strip().lower() == header.lower():
                return str(v).strip()
    return ""


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
    lines.append("— ระบบแจ้งเตือนอัตโนมัติ แผนก IT")
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
        return f"{header}\n\n— ไม่มีกำหนดการที่บันทึกไว้\n\n— ระบบแจ้งเตือนอัตโนมัติ แผนก IT"

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

    lines.append("— ระบบแจ้งเตือนอัตโนมัติ แผนก IT")
    return "\n".join(lines)


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
        help="morning: today + upcoming days (always sends). "
             "afternoon: today's afternoon items only, skipped entirely if none.",
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

    if args.session == "afternoon":
        selected = afternoon_rows(rows, target)
        message = format_afternoon_message(selected, target)
        if message is None:
            print("ไม่มีภารกิจช่วงบ่ายวันนี้ — ข้ามรอบนี้ ไม่ส่ง")
            return 0
        label = f"afternoon item(s) for {target}"
    else:
        selected = rows_from_day(rows, target)
        message = format_message(selected, target, send_when_empty)
        if message is None:
            print("Nothing scheduled and SEND_WHEN_EMPTY=0 — not sending.")
            return 0
        label = f"item(s) from {target} onward"

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
