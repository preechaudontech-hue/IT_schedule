"""Daily work-schedule announcement to a LINE group.

Reads a Google Sheet, filters rows for "today" (Asia/Bangkok), formats a Thai
message and pushes it to a LINE group via the Messaging API.

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
import sys
from datetime import date, datetime, timezone, timedelta
from typing import Any, Iterable

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
    return f"วัน{_TH_WEEKDAYS[d.weekday()]}ที่ {d.day} {_TH_MONTHS[d.month]} {d.year + 543}"


def _get(row: dict[str, Any], key: str) -> str:
    for header in _COLS[key]:
        for k, v in row.items():
            if str(k).strip().lower() == header.lower():
                return str(v).strip()
    return ""


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def rows_for_day(rows: Iterable[dict[str, Any]], target: date) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if _parse_date(_get(row, "date")) == target:
            out.append(row)
    return out


def _sort_key(row: dict[str, Any]) -> str:
    t = _get(row, "time")
    return t if t else "99:99"


def format_message(rows: list[dict[str, Any]], target: date, send_when_empty: bool = True) -> str | None:
    header = f"📢 แจ้งกำหนดการปฏิบัติงาน ประจำ{thai_date(target)}"
    if not rows:
        if not send_when_empty:
            return None
        return f"{header}\n\n— วันนี้ไม่มีกำหนดการที่บันทึกไว้\n\n— ระบบแจ้งเตือนอัตโนมัติ แผนก IT"

    lines = [header, ""]
    for i, row in enumerate(sorted(rows, key=_sort_key), start=1):
        name = _get(row, "name")
        task = _get(row, "task")
        tm = _get(row, "time")
        place = _get(row, "place")
        note = _get(row, "note")

        head = f"{i}) "
        head += f"{tm} — " if tm else ""
        head += name or "(ไม่ระบุชื่อ)"
        lines.append(head)

        detail = task or "(ไม่ระบุภารกิจ)"
        if place:
            detail += f" @ {place}"
        lines.append(f"   {detail}")
        if note:
            lines.append(f"   • {note}")
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
    todays = rows_for_day(rows, target)
    message = format_message(todays, target, send_when_empty)

    if message is None:
        print("Nothing scheduled and SEND_WHEN_EMPTY=0 — not sending.")
        return 0

    if args.dry_run:
        print(message)
        return 0

    from line_client import push_text

    push_text(
        _env("LINE_CHANNEL_ACCESS_TOKEN", required=True),
        _env("LINE_GROUP_ID", required=True),
        message,
    )
    print(f"Sent {len(todays)} item(s) for {target}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
