// Kiểm tra logic màn kiểm tra độ nhất quán (web/src/label/audit.ts) bằng Node.
// tests/test_web_audit.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-audit.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { answerToken, answersString, parseAuditHash, parseSavedAnswers } from '../src/label/audit.ts'

const LABELS = ['shallow', 'incomplete_lockout', 'hip_sag', 'hip_high', 'neck_drop']

// parseAuditHash: đúng định dạng audit_hash bên Python
assert.deepEqual(parseAuditHash('#audit/2026-10-21T08-00-00_pushup~3,b_pushup~0'), [
  { sessionId: '2026-10-21T08-00-00_pushup', repIndex: 3 },
  { sessionId: 'b_pushup', repIndex: 0 },
])
assert.deepEqual(parseAuditHash('#audit/a%7E1'), [{ sessionId: 'a', repIndex: 1 }]) // ~ bị mã hoá
assert.equal(parseAuditHash('#quick'), null)
assert.equal(parseAuditHash('#audit/'), null)
assert.equal(parseAuditHash('#audit/../x~1'), null) // ký tự lạ trong id
assert.equal(parseAuditHash('#audit/a~1,b'), null) // thiếu số rep

// answerToken: khớp parse_answers bên Python ("0", "x", chữ số theo thứ tự lỗi)
assert.equal(answerToken({ valid: true, errors: [] }, LABELS), '0')
assert.equal(answerToken({ valid: false, errors: [] }, LABELS), 'x')
assert.equal(answerToken({ valid: true, errors: ['hip_sag', 'shallow'] }, LABELS), '13')
assert.equal(
  answersString(
    [
      { valid: true, errors: [] },
      { valid: true, errors: ['neck_drop'] },
      { valid: false, errors: [] },
    ],
    LABELS,
  ),
  '0,5,x',
)

// parseSavedAnswers: sai số lượng hoặc hỏng → null (bắt đầu lại)
assert.equal(parseSavedAnswers(null, 2), null)
assert.equal(parseSavedAnswers('khong-phai-json', 2), null)
assert.equal(parseSavedAnswers('[{"valid":true,"errors":[]}]', 2), null)
assert.deepEqual(parseSavedAnswers('[{"valid":true,"errors":["shallow"]}]', 1), [
  { valid: true, errors: ['shallow'] },
])

console.log('check-audit: ok')
