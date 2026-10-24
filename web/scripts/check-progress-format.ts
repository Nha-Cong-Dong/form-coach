// Kiểm tra hàm ngày/chữ của Dashboard (web/src/progress/format.ts) bằng Node.
// tests/test_web_progress_format.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-progress-format.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { addDays, dayLabel, goalHeadline, localDate, percentText } from '../src/progress/format.ts'

// localDate: ngày theo giờ máy, kể cả 0h30 (toISOString ở VN sẽ ra ngày hôm trước)
assert.equal(localDate(new Date(2026, 9, 25, 0, 30)), '2026-10-25')
assert.equal(localDate(new Date(2026, 0, 5)), '2026-01-05')

// addDays: qua tháng, qua năm, lùi
assert.equal(addDays('2026-10-25', -13), '2026-10-12')
assert.equal(addDays('2026-10-31', 1), '2026-11-01')
assert.equal(addDays('2026-01-01', -1), '2025-12-31')
assert.equal(addDays('2028-02-28', 1), '2028-02-29') // năm nhuận

// dayLabel
assert.equal(dayLabel('2026-10-23'), '23/10')
assert.equal(dayLabel('2026-10-23', true), 'Thứ Sáu, 23/10')
assert.equal(dayLabel('2026-10-25', true), 'Chủ Nhật, 25/10')

// goalHeadline
const goal = { daily_reps: 50, min_good_ratio: null }
assert.equal(goalHeadline(36, goal, false), 'Còn 14 rep nữa là đạt mục tiêu')
assert.equal(goalHeadline(50, goal, true), 'Đã đạt mục tiêu hôm nay')
assert.equal(goalHeadline(50, { daily_reps: 50, min_good_ratio: 0.7 }, false), 'Đủ rep, cần ít nhất 70% rep đúng')
assert.equal(goalHeadline(0, null, false), 'Chưa tập hôm nay')
assert.equal(goalHeadline(3, null, true), 'Hôm nay đã tập')

// percentText
assert.equal(percentText(0.714), '71%')
assert.equal(percentText(null), '—')

console.log('check-progress-format: ok')
