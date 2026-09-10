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

## ทดสอบเร็ว ๆ
- เปิด Web app URL ตรง ๆ ในเบราว์เซอร์ → ควรเห็น `{"ok":true,"rows":[...]}`
- เพิ่มแถว:
  ```bash
  curl -L -X POST "<URL>" -H "Content-Type: text/plain" \
    -d '{"action":"add","date":"2026-09-15","name":"ทดสอบ","task":"เช็คระบบ","time":"09:00"}'
  ```
