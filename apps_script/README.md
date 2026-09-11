# ตั้งค่า Apps Script Web App (backend ของหน้าเว็บ)

หน้าเว็บ `web/index.html` คุยกับ Google Sheet ผ่าน Apps Script ตัวนี้ ไม่ต้องมี server

## ขั้นตอน
1. เปิด Google Sheet ที่ใช้เก็บตาราง (แท็บชื่อ `schedule`)
2. เมนู **Extensions → Apps Script**
3. ลบโค้ดเดิมในไฟล์ `Code.gs` แล้ววางเนื้อหาจาก [`Code.gs`](Code.gs) ทั้งหมด
4. กด **Save** (ไอคอนแผ่นดิสก์)
5. กด **Deploy → New deployment**
   - Select type (เฟือง) → **Web app**
   - Description: `schedule api`
   - Execute as: **Me**
   - Who has access: **Anyone**
   - กด **Deploy** → อนุญาตสิทธิ์ (Authorize access) → เลือกบัญชี → Advanced → Go to … → Allow
6. คัดลอก **Web app URL** (ลงท้าย `/exec`)
7. เปิด `web/index.html` แก้บรรทัด
   ```js
   const APPS_SCRIPT_URL = "PASTE_YOUR_APPS_SCRIPT_EXEC_URL_HERE";
   ```
   เป็น URL ที่คัดลอกมา แล้ว commit/push

## แก้โค้ดภายหลัง
ทุกครั้งที่แก้ `Code.gs` ต้อง **Deploy → Manage deployments → (ดินสอ) → Version: New version → Deploy**
มิฉะนั้น URL เดิมจะยังรันโค้ดเวอร์ชันเก่า

## เปิดใช้รหัสผ่าน (ถ้าต้องการ)
ใน `Code.gs` ตั้ง `var PASSCODE = 'ค่าอะไรก็ได้';` แล้ว deploy เวอร์ชันใหม่
จากนั้นใส่ค่าเดียวกันใน `web/index.html` ที่ `const PASSCODE = "...";`

## หา LINE Group ID (ไม่ต้องใช้ tunnel/ngrok)
Web app URL ตัวนี้เป็น public HTTPS อยู่แล้ว ใช้เป็น LINE webhook ได้เลย:

1. คัดลอก Web app URL (ตัวเดียวกับที่ใช้ใน `web/index.html`)
2. developers.line.biz → channel ของคุณ → แท็บ **Messaging API**
3. ช่อง **Webhook URL** → วาง URL นั้น → กด **Update**
4. เปิด **Use webhook** = Enabled
5. กด **Verify** (ควรขึ้น Success — ถ้าไม่สำเร็จดูหัวข้อ "แก้ปัญหา" ด้านล่าง)
6. ให้บอทเข้ากลุ่ม LINE (ถ้ายัง) → พิมพ์ข้อความอะไรก็ได้ในกลุ่ม 1 ครั้ง
7. เปิด `<Web app URL>?debug=groupid` ในเบราว์เซอร์ → จะเห็น
   ```json
   {"ok":true,"lastGroupId":"Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", ...}
   ```
8. คัดลอกค่า `Cxxxx...` → ใส่ GitHub Secret ชื่อ `LINE_GROUP_ID`
9. (แนะนำ) กลับไปปิด **Use webhook** เป็น Disabled อีกครั้งหลังได้ id แล้ว — เพราะระบบนี้ส่งข้อความแบบ push ไม่ได้ใช้ webhook ตอนทำงานจริง

### แก้ปัญหา
- **Verify ไม่ผ่าน**: ต้อง deploy เวอร์ชันใหม่ก่อน (Deploy → Manage deployments → ดินสอ → New version → Deploy) เพราะ URL เดิมยังรันโค้ดเก่าที่ไม่รู้จัก `events`
- **`lastGroupId` เป็น null**: บอทอาจยังไม่ได้อยู่ในกลุ่มจริง หรือยังไม่ได้พิมพ์ข้อความหลังเปิด webhook — เชิญบอทใหม่แล้วพิมพ์อีกครั้ง
- **ตั้ง PASSCODE ไว้**: debug endpoint นี้ไม่เช็ค PASSCODE (เพื่อความง่าย) — ปิด webhook ทันทีหลังใช้เสร็จ

## ทดสอบเร็ว ๆ
- เปิด Web app URL ตรง ๆ ในเบราว์เซอร์ → ควรเห็น `{"ok":true,"rows":[...]}`
- เพิ่มแถว:
  ```bash
  curl -L -X POST "<URL>" -H "Content-Type: text/plain" \
    -d '{"action":"add","date":"2026-09-15","name":"ทดสอบ","task":"เช็คระบบ","time":"09:00"}'
  ```
