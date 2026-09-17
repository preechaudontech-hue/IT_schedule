import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from notify import (  # noqa: E402
    afternoon_rows,
    append_section,
    format_afternoon_message,
    format_message,
    format_todos_section,
    pending_todos,
    rows_for_day,
    rows_from_day,
    thai_date,
    todos_only_message,
)


ROWS = [
    {"วันที่": "2026-09-11", "ชื่อ-สกุล": "นายสมชาย ใจดี", "รายการ/ภารกิจ": "ประชุม IT",
     "เวลา": "13:00-15:00", "สถานที่": "ห้อง 2", "หมายเหตุ": "นำโน้ตบุ๊ก"},
    {"วันที่": "2026-09-11", "ชื่อ-สกุล": "นางสาวมาลี", "รายการ/ภารกิจ": "ตรวจระบบเครือข่าย",
     "เวลา": "09:00", "สถานที่": "", "หมายเหตุ": ""},
    {"วันที่": "11/09/2026", "ชื่อ-สกุล": "นายเอก", "รายการ/ภารกิจ": "อบรม",
     "เวลา": "", "สถานที่": "", "หมายเหตุ": ""},
    {"วันที่": "2026-09-12", "ชื่อ-สกุล": "คนอื่น", "รายการ/ภารกิจ": "งานพรุ่งนี้",
     "เวลา": "", "สถานที่": "", "หมายเหตุ": ""},
    {"วันที่": "2026-09-01", "ชื่อ-สกุล": "อดีต", "รายการ/ภารกิจ": "งานที่ผ่านมาแล้ว",
     "เวลา": "", "สถานที่": "", "หมายเหตุ": ""},
]


def test_thai_date():
    assert thai_date(date(2026, 9, 11)) == "วันศุกร์ที่ 11 ก.ย. 69"


def test_rows_for_day_matches_multiple_date_formats():
    got = rows_for_day(ROWS, date(2026, 9, 11))
    assert len(got) == 3


def test_rows_from_day_includes_today_and_future_only():
    got = rows_from_day(ROWS, date(2026, 9, 11))
    assert len(got) == 4  # 3 today + 1 tomorrow, excludes the past row
    assert all(r["ชื่อ-สกุล"] != "อดีต" for r in got)


def test_format_message_groups_by_date_and_sorts_by_time():
    msg = format_message(rows_from_day(ROWS, date(2026, 9, 11)), date(2026, 9, 11))
    assert "📢 แจ้งกำหนดการปฏิบัติงาน\nวันศุกร์ที่ 11 ก.ย. 69เป็นต้นไป" in msg
    assert "📅 วันศุกร์ที่ 11 ก.ย. 69" in msg
    assert "📅 วันเสาร์ที่ 12 ก.ย. 69" in msg
    # today's section comes before tomorrow's
    assert msg.index("วันศุกร์ที่ 11") < msg.index("วันเสาร์ที่ 12")
    # 09:00 entry should come before the 13:00 entry within the same day
    assert msg.index("นางสาวมาลี") < msg.index("นายสมชาย ใจดี")
    assert "1) 09:00" in msg
    assert "   - นางสาวมาลี" in msg
    assert "   - ห้อง 2" in msg
    assert "   - นำโน้ตบุ๊ก" in msg
    assert "งานที่ผ่านมาแล้ว" not in msg


def test_format_message_empty_default_sends_notice():
    msg = format_message([], date(2026, 9, 11))
    assert msg is not None
    assert "ไม่มีกำหนดการ" in msg


def test_format_message_empty_suppressed():
    assert format_message([], date(2026, 9, 11), send_when_empty=False) is None


AFTERNOON_ROWS = [
    {"วันที่": "2026-09-11", "ชื่อ-สกุล": "เช้า", "รายการ/ภารกิจ": "ประชุมเช้า",
     "เวลา": "09.00 น.", "สถานที่": "", "หมายเหตุ": ""},
    {"วันที่": "2026-09-11", "ชื่อ-สกุล": "บ่าย", "รายการ/ภารกิจ": "ตรวจงานบ่าย",
     "เวลา": "13.00 น.", "สถานที่": "", "หมายเหตุ": ""},
    {"วันที่": "2026-09-11", "ชื่อ-สกุล": "ไม่ระบุเวลา", "รายการ/ภารกิจ": "งานไม่ระบุเวลา",
     "เวลา": "", "สถานที่": "", "หมายเหตุ": ""},
    {"วันที่": "2026-09-12", "ชื่อ-สกุล": "พรุ่งนี้บ่าย", "รายการ/ภารกิจ": "งานพรุ่งนี้",
     "เวลา": "14.00 น.", "สถานที่": "", "หมายเหตุ": ""},
]


def test_afternoon_rows_only_todays_afternoon_items():
    got = afternoon_rows(AFTERNOON_ROWS, date(2026, 9, 11))
    assert [r["ชื่อ-สกุล"] for r in got] == ["บ่าย"]


def test_format_afternoon_message_none_when_empty():
    assert format_afternoon_message([], date(2026, 9, 11)) is None
    # 9/13 has no rows at all -> no afternoon items either
    assert format_afternoon_message(afternoon_rows(AFTERNOON_ROWS, date(2026, 9, 13)), date(2026, 9, 13)) is None


def test_format_afternoon_message_lists_items():
    rows = afternoon_rows(AFTERNOON_ROWS, date(2026, 9, 11))
    msg = format_afternoon_message(rows, date(2026, 9, 11))
    assert "เตือนภารกิจช่วงบ่าย" in msg
    assert "ตรวจงานบ่าย" in msg
    assert "ประชุมเช้า" not in msg


TODO_ROWS = [
    {"รายการ": "ส่งเอกสารงบประมาณ", "ผู้รับผิดชอบ": "อ.ปรีชา", "เสร็จสิ้น": False, "หมายเหตุ": ""},
    {"รายการ": "ติดตามเรื่อง X", "ผู้รับผิดชอบ": "อ.วิชัย", "เสร็จสิ้น": True, "หมายเหตุ": ""},
    {"รายการ": "เคลียร์ของเก่า", "ผู้รับผิดชอบ": "อ.รุ่งนภา", "เสร็จสิ้น": "TRUE", "หมายเหตุ": ""},
    {"รายการ": "อัปเดตทะเบียน", "ผู้รับผิดชอบ": "อ.ณัฐพล", "เสร็จสิ้น": "", "หมายเหตุ": "รอเอกสารจากฝ่ายบุคคล"},
]


def test_pending_todos_filters_done_regardless_of_bool_or_string():
    pending = pending_todos(TODO_ROWS)
    assert [t["รายการ"] for t in pending] == ["ส่งเอกสารงบประมาณ", "อัปเดตทะเบียน"]


def test_format_todos_section_empty_when_all_done():
    all_done = [row for row in TODO_ROWS if row["รายการ"] != "ส่งเอกสารงบประมาณ" and row["รายการ"] != "อัปเดตทะเบียน"]
    assert format_todos_section(all_done) == []


def test_format_todos_section_lists_pending_with_note():
    lines = format_todos_section(TODO_ROWS)
    text = "\n".join(lines)
    assert "อย่าลืม" in text
    assert "อ.ปรีชา — ส่งเอกสารงบประมาณ" in text
    assert "รอเอกสารจากฝ่ายบุคคล" in text
    assert "ติดตามเรื่อง X" not in text  # done -> excluded


def test_append_section_inserts_before_footer():
    base = format_message(rows_from_day(ROWS, date(2026, 9, 11)), date(2026, 9, 11))
    combined = append_section(base, format_todos_section(TODO_ROWS))
    assert combined.endswith("— Bot แจ้งเตือน")
    assert combined.index("อย่าลืม") > combined.index("📅 วันศุกร์ที่ 11 ก.ย. 69")
    assert "ส่งเอกสารงบประมาณ" in combined


def test_append_section_noop_when_no_todos():
    base = format_message(rows_from_day(ROWS, date(2026, 9, 11)), date(2026, 9, 11))
    assert append_section(base, []) == base


def test_todos_only_message_when_nothing_scheduled():
    msg = todos_only_message(date(2026, 9, 11), format_todos_section(TODO_ROWS))
    assert "ส่งเอกสารงบประมาณ" in msg
    assert msg.endswith("— Bot แจ้งเตือน")
