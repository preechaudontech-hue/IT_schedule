/**
 * Google Apps Script Web App — backend for the schedule web form.
 *
 * Deploy: Extensions → Apps Script (from the target Sheet) → paste this file →
 *   Deploy → New deployment → type "Web app" → Execute as: Me →
 *   Who has access: Anyone → Deploy → copy the /exec URL into web/index.html.
 *
 * The Sheet must have a tab named as SHEET_NAME with a header row containing
 * (in any order): วันที่, ชื่อ-สกุล, รายการ/ภารกิจ, เวลา, สถานที่, หมายเหตุ
 */

var SHEET_NAME = 'schedule';

// Optional shared passcode. Leave '' to disable. To enable: set a value here,
// redeploy, and pass ?key=... (GET) or "key" in the POST body.
var PASSCODE = '';

var HEADERS = {
  date: ['วันที่', 'date'],
  name: ['ชื่อ-สกุล', 'ชื่อ', 'name'],
  task: ['รายการ/ภารกิจ', 'รายการ', 'ภารกิจ', 'task'],
  time: ['เวลา', 'time'],
  place: ['สถานที่', 'place'],
  note: ['หมายเหตุ', 'note'],
};

function _sheet() {
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  if (!sh) throw new Error('ไม่พบแท็บชื่อ "' + SHEET_NAME + '"');
  return sh;
}

/** Map canonical key -> 0-based column index, from the header row. */
function _colMap(headerRow) {
  var norm = headerRow.map(function (h) { return String(h).trim().toLowerCase(); });
  var map = {};
  Object.keys(HEADERS).forEach(function (key) {
    for (var i = 0; i < HEADERS[key].length; i++) {
      var idx = norm.indexOf(HEADERS[key][i].toLowerCase());
      if (idx !== -1) { map[key] = idx; break; }
    }
  });
  return map;
}

function _toISO(raw) {
  if (raw instanceof Date) {
    return Utilities.formatDate(raw, 'Asia/Bangkok', 'yyyy-MM-dd');
  }
  var s = String(raw).trim();
  var m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return m[1] + '-' + _pad(m[2]) + '-' + _pad(m[3]);
  m = s.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/); // DD/MM/YYYY
  if (m) return m[3] + '-' + _pad(m[2]) + '-' + _pad(m[1]);
  return s;
}
function _pad(n) { n = String(n); return n.length === 1 ? '0' + n : n; }

function _readRows() {
  var sh = _sheet();
  var values = sh.getDataRange().getValues();
  if (values.length < 2) return { map: {}, rows: [] };
  var map = _colMap(values[0]);
  var rows = [];
  for (var r = 1; r < values.length; r++) {
    var row = values[r];
    if (row.join('').trim() === '') continue;
    rows.push({
      row: r + 1, // 1-based sheet row number
      date: map.date != null ? _toISO(row[map.date]) : '',
      name: map.name != null ? String(row[map.name]).trim() : '',
      task: map.task != null ? String(row[map.task]).trim() : '',
      time: map.time != null ? String(row[map.time]).trim() : '',
      place: map.place != null ? String(row[map.place]).trim() : '',
      note: map.note != null ? String(row[map.note]).trim() : '',
    });
  }
  return { map: map, rows: rows };
}

function _json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function _checkKey(provided) {
  if (!PASSCODE) return;
  if (String(provided || '') !== PASSCODE) throw new Error('รหัสผ่านไม่ถูกต้อง');
}

function doGet(e) {
  try {
    var p = (e && e.parameter) || {};
    // Debug helper: open <url>?debug=groupid in a browser to see the last
    // group/room id this Web App has seen come through the LINE webhook.
    if (p.debug === 'groupid') {
      var props = PropertiesService.getScriptProperties();
      return _json({
        ok: true,
        lastGroupId: props.getProperty('LAST_GROUP_ID') || null,
        lastSeenAt: props.getProperty('LAST_GROUP_ID_AT') || null,
        note: 'ส่งข้อความอะไรก็ได้ในกลุ่ม LINE ที่เชิญบอทเข้าไปแล้ว รีเฟรชหน้านี้เพื่อดูค่าล่าสุด',
      });
    }
    _checkKey(p.key);
    var data = _readRows();
    var rows = data.rows;
    var from = p.from;
    if (from) rows = rows.filter(function (x) { return x.date >= from; });
    rows.sort(function (a, b) {
      return (a.date + (a.time || '99:99')).localeCompare(b.date + (b.time || '99:99'));
    });
    return _json({ ok: true, rows: rows });
  } catch (err) {
    return _json({ ok: false, error: String(err.message || err) });
  }
}

function doPost(e) {
  try {
    var body = {};
    if (e && e.postData && e.postData.contents) body = JSON.parse(e.postData.contents);

    // LINE webhook calls land here with an "events" array (no "action" of ours).
    // Use this same Web App URL as the LINE Messaging API webhook to capture
    // the group/room id without needing any tunnel (ngrok/cloudflared).
    if (body && body.events) {
      _recordLineEvents(body.events);
      return ContentService.createTextOutput('OK');
    }

    _checkKey(body.key);
    var action = body.action;

    if (action === 'add') {
      return _json(_add(body));
    } else if (action === 'delete') {
      return _json(_delete(body));
    }
    return _json({ ok: false, error: 'ไม่รู้จัก action: ' + action });
  } catch (err) {
    return _json({ ok: false, error: String(err.message || err) });
  }
}

function _recordLineEvents(events) {
  var props = PropertiesService.getScriptProperties();
  events.forEach(function (ev) {
    var src = ev.source || {};
    var id = src.groupId || src.roomId;
    if (id) {
      props.setProperty('LAST_GROUP_ID', id);
      props.setProperty('LAST_GROUP_ID_AT', new Date().toISOString());
    }
  });
}

function _add(body) {
  var date = _toISO(body.date || '');
  var name = String(body.name || '').trim();
  var task = String(body.task || '').trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return { ok: false, error: 'วันที่ไม่ถูกต้อง (YYYY-MM-DD)' };
  if (!name) return { ok: false, error: 'กรุณากรอกชื่อ-สกุล' };
  if (!task) return { ok: false, error: 'กรุณากรอกรายการ/ภารกิจ' };

  var sh = _sheet();
  var header = sh.getDataRange().getValues()[0];
  var map = _colMap(header);
  var out = new Array(header.length).fill('');
  var vals = {
    date: date, name: name, task: task,
    time: String(body.time || '').trim(),
    place: String(body.place || '').trim(),
    note: String(body.note || '').trim(),
  };
  Object.keys(vals).forEach(function (k) { if (map[k] != null) out[map[k]] = vals[k]; });
  sh.appendRow(out);
  return { ok: true, row: sh.getLastRow() };
}

function _delete(body) {
  var row = parseInt(body.row, 10);
  var sh = _sheet();
  if (!row || row < 2 || row > sh.getLastRow()) return { ok: false, error: 'หมายเลขแถวไม่ถูกต้อง' };
  sh.deleteRow(row);
  return { ok: true };
}
