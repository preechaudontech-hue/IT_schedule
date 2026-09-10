# ระบบแจ้งเตือนการปฏิบัติงานผ่านกลุ่ม LINE (ทุกวัน 08:00)

ทุกเช้า GitHub Actions จะรัน `src/notify.py` → อ่านตารางงานจาก Google Sheet →
กรองงานของ "วันนี้" → ส่งข้อความสรุปเข้ากลุ่ม LINE ผ่าน Messaging API

```
Google Sheet  ──►  GitHub Actions (cron 01:00 UTC = 08:00 ไทย)  ──►  LINE push  ──►  กลุ่ม
```

## 1. เตรียม Google Sheet
1. สร้าง Sheet ใหม่ ตั้งชื่อแท็บว่า `schedule`
2. แถวแรกเป็นหัวคอลัมน์ (ลำดับใดก็ได้): `วันที่ | ชื่อ-สกุล | รายการ/ภารกิจ | เวลา | สถานที่ | หมายเหตุ`
3. คอลัมน์ `วันที่` ใช้ `YYYY-MM-DD` (รองรับ `DD/MM/YYYY` ด้วย), `เวลา` เช่น `09:00` หรือ `13:00-15:00`

| วันที่ | ชื่อ-สกุล | รายการ/ภารกิจ | เวลา | สถานที่ | หมายเหตุ |
|---|---|---|---|---|---|
| 2026-09-11 | นายสมชาย ใจดี | ประชุมคณะกรรมการ IT | 09:00-12:00 | ห้องประชุม 2 | นำโน้ตบุ๊ก |

## 2. Google service account
1. https://console.cloud.google.com → สร้างโปรเจกต์ → เปิดใช้ **Google Sheets API**
2. IAM & Admin → Service Accounts → สร้าง → Keys → Add key → JSON (ดาวน์โหลดไฟล์)
3. เปิด Sheet → Share → ใส่อีเมล service account (`...@...iam.gserviceaccount.com`) สิทธิ์ **Viewer**
4. `SHEET_ID` = ส่วนกลาง URL: `https://docs.google.com/spreadsheets/d/`**`<SHEET_ID>`**`/edit`

## 3. LINE Messaging API
1. https://developers.line.biz/console → สร้าง Provider → สร้าง channel แบบ **Messaging API**
2. แท็บ Messaging API → ออก **Channel access token (long-lived)** → นี่คือ `LINE_CHANNEL_ACCESS_TOKEN`
3. ปิด "Auto-reply" / "Greeting" ได้ตามต้องการ
4. เพิ่มบอทเป็นเพื่อน แล้ว **เชิญบอทเข้ากลุ่ม**
5. หา `LINE_GROUP_ID`:
   - รัน `python src/get_group_id.py` บนเครื่อง
   - เปิด tunnel: `cloudflared tunnel --url http://localhost:8000` (หรือ ngrok)
   - เอา URL ไปใส่ช่อง Webhook URL ในคอนโซล LINE + เปิด "Use webhook"
   - พิมพ์อะไรก็ได้ในกลุ่ม → เทอร์มินัลจะพิมพ์ `source: {"type":"group","groupId":"Cxxxx..."}`
   - ปิด webhook ได้หลังได้ id แล้ว

## 4. ใส่ค่าเป็น GitHub Secrets
Repo → Settings → Secrets and variables → Actions → New repository secret:

| ชื่อ | ค่า |
|---|---|
| `LINE_CHANNEL_ACCESS_TOKEN` | token จากขั้น 3 |
| `LINE_GROUP_ID` | `Cxxxxxxxx...` |
| `GOOGLE_SA_JSON` | เนื้อหาไฟล์ JSON ทั้งไฟล์ (วางทั้งก้อน) |
| `SHEET_ID` | id จากขั้น 2 |

## 5. ทดสอบ
```bash
pip install -r requirements.txt
python -m pytest -q                 # ตรวจ logic จัดข้อความ/กรองวันที่
python src/notify.py --dry-run      # ต้องตั้ง env ก่อน (ดู .env.example) — พิมพ์ข้อความ ไม่ส่ง
python src/notify.py --date 2026-09-11 --dry-run
```
บน GitHub: แท็บ **Actions → daily-notify → Run workflow** (ติ๊ก dry run ได้) เพื่อเช็คว่า secrets ครบ

## หน้าเว็บกรอกข้อมูล
แทนการแก้ Google Sheet ตรง ๆ มีหน้าเว็บให้กรอก/ดู/ลบรายการ (`web/index.html`)

1. ตั้งค่า Apps Script ตาม [apps_script/README.md](apps_script/README.md) → ได้ Web app URL
2. ใส่ URL ลงใน `web/index.html` ที่ `const APPS_SCRIPT_URL = ...`
3. เปิดใช้ GitHub Pages: repo → Settings → Pages → Source = **GitHub Actions**
4. push โค้ด → workflow `deploy-pages` จะเผยแพร่โฟลเดอร์ `web/` → เปิดได้ที่ `https://<user>.github.io/<repo>/`
5. ทดสอบบนเครื่องก่อนได้: `python -m http.server 8000 -d web` แล้วเปิด http://localhost:8000

> ⚠️ ความปลอดภัย: หน้านี้เปิดให้ทุกคนที่มีลิงก์กรอก/ลบได้ (ไม่มีรหัส) หากต้องการจำกัด
> ให้ตั้ง `PASSCODE` ทั้งใน `apps_script/Code.gs` และ `web/index.html`

## ปรับแต่ง
- ไม่อยากส่งวันที่ไม่มีงาน: ตั้ง secret/`env` `SEND_WHEN_EMPTY=0`
- เปลี่ยนเวลา: แก้ `cron` ใน `.github/workflows/daily-notify.yml` (เป็น UTC — ไทยลบ 7)
- GitHub cron ดีเลย์ได้ 5–15 นาที ถ้าต้องเป๊ะให้ย้ายไป VPS + crontab เรียก `python src/notify.py`
