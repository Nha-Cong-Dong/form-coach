// Kiểm tra tên hiệp (makeSessionId, randomSuffix trong web/src/session/format.ts) bằng Node.
// tests/test_web_session_id.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-session-id.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { makeSessionId, randomSuffix } from '../src/session/format.ts'

const at = new Date(2026, 9, 31, 8, 37, 32)

// Đuôi cố định: định dạng giờ_đuôi_bài
assert.equal(makeSessionId(at, 'pushup', 'a3f9c1'), '2026-10-31T08-37-32_a3f9c1_pushup')

// Đuôi ngẫu nhiên: 6 ký tự hex; cùng một giây, hai lần gọi ra hai tên khác nhau
assert.match(randomSuffix(), /^[0-9a-f]{6}$/)
const names = new Set(Array.from({ length: 200 }, () => makeSessionId(at, 'pushup')))
assert.ok(names.size >= 199) // 24 bit: trùng trong 200 lần gần như không xảy ra

// Server chỉ nhận chữ/số/'-'/'_', tối đa 100 ký tự (formcoach/pose/session_json.py SESSION_ID_RE)
for (const n of names) assert.match(n, /^[A-Za-z0-9_-]{1,100}$/)

// Sắp theo tên vẫn là theo thời gian (đuôi đứng sau giờ)
const earlier = makeSessionId(new Date(2026, 9, 31, 8, 37, 31), 'pushup', 'ffffff')
const later = makeSessionId(at, 'pushup', '000000')
assert.ok(earlier < later)

console.log('check-session-id: ok')
