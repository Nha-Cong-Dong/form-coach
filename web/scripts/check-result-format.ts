// Kiểm tra hàm định dạng trang kết quả (web/src/results/format.ts) bằng Node.
// tests/test_web_result_format.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-result-format.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import {
  frameAt,
  formatDuration,
  formatRecordedAt,
  measureText,
  outsideTarget,
  repRanges,
  repsByError,
  targetText,
} from '../src/results/format.ts'

// targetText: mục tiêu là phía ngược với luật lỗi
assert.equal(targetText('>', 67, '°'), '≤ 67°') // shallow: lỗi khi góc đáy > 67°
assert.equal(targetText('<', 146, '°'), '≥ 146°') // incomplete_lockout: lỗi khi góc đỉnh < 146°
assert.equal(targetText('>', 66.6, '°'), '≤ 67°')

// outsideTarget: cùng phía với luật lỗi; đúng bằng ngưỡng vẫn trong mục tiêu; không đo được → false
assert.equal(outsideTarget('>', 67, 57), false) // 57° đáy: trong mục tiêu ≤ 67° dù mô hình báo lỗi
assert.equal(outsideTarget('>', 67, 80), true)
assert.equal(outsideTarget('>', 67, 67), false)
assert.equal(outsideTarget('<', 146, 130), true)
assert.equal(outsideTarget('<', 146, 160), false)
assert.equal(outsideTarget('>', 67, null), false)
assert.equal(outsideTarget('>', 67, undefined), false)

// frameAt: khung cuối cùng có thời gian ≤ t
const times = [0, 0.033, 0.067, 0.1]
assert.equal(frameAt(times, 0), 0)
assert.equal(frameAt(times, 0.05), 1)
assert.equal(frameAt(times, 0.067), 2)
assert.equal(frameAt(times, 5), 3) // quá cuối → khung cuối
assert.equal(frameAt(times, -1), 0) // trước đầu → khung đầu
assert.equal(frameAt([], 1), -1)

// measureText
assert.equal(measureText(94.6, '°'), '95°')
assert.equal(measureText(null, '°'), '—')
assert.equal(measureText(undefined, '°'), '—')

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
