import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from notify import format_message, rows_for_day, rows_from_day, thai_date  # noqa: E402


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
    assert thai_date(date(2026, 9, 11)) == "วันศุกร์ที่ 11 ก.ย. 2569"


def test_rows_for_day_matches_multiple_date_formats():
    got = rows_for_day(ROWS, date(2026, 9, 11))
    assert len(got) == 3


def test_rows_from_day_includes_today_and_future_only():
    got = rows_from_day(ROWS, date(2026, 9, 11))
    assert len(got) == 4  # 3 today + 1 tomorrow, excludes the past row
    assert all(r["ชื่อ-สกุล"] != "อดีต" for r in got)


def test_format_message_groups_by_date_and_sorts_by_time():
    msg = format_message(rows_from_day(ROWS, date(2026, 9, 11)), date(2026, 9, 11))
    assert "ตั้งแต่วันศุกร์ที่ 11 ก.ย. 2569เป็นต้นไป" in msg
    assert "📅 วันศุกร์ที่ 11 ก.ย. 2569" in msg
    assert "📅 วันเสาร์ที่ 12 ก.ย. 2569" in msg
    # today's section comes before tomorrow's
    assert msg.index("วันศุกร์ที่ 11") < msg.index("วันเสาร์ที่ 12")
    # 09:00 entry should come before the 13:00 entry within the same day
    assert msg.index("นางสาวมาลี") < msg.index("นายสมชาย ใจดี")
    assert "@ ห้อง 2" in msg
    assert "• นำโน้ตบุ๊ก" in msg
    assert "งานที่ผ่านมาแล้ว" not in msg


def test_format_message_empty_default_sends_notice():
    msg = format_message([], date(2026, 9, 11))
    assert msg is not None
    assert "ไม่มีกำหนดการ" in msg


def test_format_message_empty_suppressed():
    assert format_message([], date(2026, 9, 11), send_when_empty=False) is None
