/**
 * Shared storage for the "Home from CIV" page (GitHub Pages).
 * Keeps changed school times and Icilà booking marks in this Google Sheet,
 * so Sarah, Alara and their parents all see the same thing.
 *
 * Setup (once):
 *  1. Project Settings -> Script properties -> add PIN = a family code (e.g. 4-6 digits).
 *  2. Deploy -> New deployment -> type "Web app", Execute as "Me", Who has access "Anyone".
 *  3. Copy the web app URL (ends in /exec) into SYNC_URL in index.html.
 */
const SHEET = 'data';
const KEY_RE = /^(mon|tue|wed|thu|fri)-(sarah|alara)(-start)?$|^ic-(mon|tue|wed|thu|fri)-(sarah|alara)-(am|pm)$/;
const VAL_RE = /^(off|([01]\d|2[0-3]):[0-5]\d|cancelled|booked@([01]\d|2[0-3]):[0-5]\d@(off|([01]\d|2[0-3]):[0-5]\d))$/;

function sheet_() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(SHEET);
  if (!sh) {
    sh = ss.insertSheet(SHEET);
    sh.getRange('A:E').setNumberFormat('@'); // keep dates and times as plain text
    sh.appendRow(['week', 'key', 'value', 'by', 'updated']);
  }
  return sh;
}
function out_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
function pinOk_(p) {
  const pin = PropertiesService.getScriptProperties().getProperty('PIN');
  return !!pin && String(p || '') === pin;
}
function items_(week) {
  const rows = sheet_().getDataRange().getDisplayValues();
  const items = {};
  for (let i = 1; i < rows.length; i++) if (rows[i][0] === week) items[rows[i][1]] = rows[i][2];
  return items;
}
function doGet(e) {
  const p = e.parameter || {};
  if (!pinOk_(p.pin)) return out_({ ok: false, error: 'pin' });
  const week = String(p.week || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(week)) return out_({ ok: false, error: 'week' });
  return out_({ ok: true, items: items_(week) });
}
function doPost(e) {
  let b;
  try { b = JSON.parse(e.postData.contents); } catch (err) { return out_({ ok: false, error: 'json' }); }
  if (!pinOk_(b.pin)) return out_({ ok: false, error: 'pin' });
  const week = String(b.week || ''), key = String(b.key || ''), val = b.value === null ? null : String(b.value || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(week) || !KEY_RE.test(key) || (val !== null && !VAL_RE.test(val)))
    return out_({ ok: false, error: 'invalid' });
  const by = String(b.by || '').slice(0, 20);
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sh = sheet_();
    const rows = sh.getDataRange().getDisplayValues();
    let row = -1;
    for (let i = 1; i < rows.length; i++) if (rows[i][0] === week && rows[i][1] === key) { row = i + 1; break; }
    if (val === null) { if (row > 0) sh.deleteRow(row); }
    else if (row > 0) sh.getRange(row, 3, 1, 3).setValues([[val, by, new Date().toISOString()]]);
    else sh.appendRow([week, key, val, by, new Date().toISOString()]);
  } finally { lock.releaseLock(); }
  return out_({ ok: true, items: items_(week) });
}
