// Kiểm tra hàm định dạng trang kết quả (web/src/results/format.ts) bằng Node.
// tests/test_web_result_format.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-result-format.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { formatDuration, formatRecordedAt, repRanges, repsByError } from '../src/results/format.ts'

// repRanges: gộp số liên tiếp, bỏ trùng, sắp xếp
assert.equal(repRanges([]), '')
assert.equal(repRanges([7]), '7')
assert.equal(repRanges([9, 10, 11, 12]), '9–12')
assert.equal(repRanges([4, 1, 3]), '1, 3–4')
assert.equal(repRanges([2, 2, 3]), '2–3')

// formatDuration
assert.equal(formatDuration(65.4), '1:05')
assert.equal(formatDuration(0), '0:00')
assert.equal(formatDuration(-3), '0:00')
assert.equal(formatDuration(600), '10:00')

// formatRecordedAt: chuỗi lạ giữ nguyên; chuỗi hợp lệ có dạng dd/mm · hh:mm
assert.equal(formatRecordedAt('khong-phai-ngay'), 'khong-phai-ngay')
assert.match(formatRecordedAt('2026-10-24T18:42:00Z'), /^\d{2}\/\d{2} · \d{2}:\d{2}$/)

// repsByError: số rep đếm từ 1, theo thứ tự lỗi, bỏ lỗi không có rep
const reps = [
  { index: 0, errors: [] },
  { index: 1, errors: ['hip_sag'] },
  { index: 2, errors: ['shallow', 'hip_sag'] },
]
assert.deepEqual(repsByError(reps, ['shallow', 'incomplete_lockout', 'hip_sag']), [
  { error: 'shallow', reps: [3] },
  { error: 'hip_sag', reps: [2, 3] },
])

console.log('check-result-format: ok')
