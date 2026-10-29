// Kiểm tra lịch tháng của màn Lịch sử (web/src/history/calendar.ts) bằng Node.
// tests/test_web_history_calendar.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-history-calendar.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import {
  dayState,
  groupByDay,
  monthGrid,
  monthLabel,
  monthOf,
  monthRange,
  sessionDay,
  sessionTime,
  shiftMonth,
} from '../src/history/calendar.ts'

// shiftMonth: qua năm cả hai chiều
assert.equal(shiftMonth('2026-10', 1), '2026-11')
assert.equal(shiftMonth('2026-12', 1), '2027-01')
assert.equal(shiftMonth('2026-01', -1), '2025-12')
assert.equal(monthOf('2026-10-29'), '2026-10')

// monthRange: số ngày từng tháng, năm nhuận
assert.deepEqual(monthRange('2026-10'), { first: '2026-10-01', last: '2026-10-31' })
assert.equal(monthRange('2026-11').last, '2026-11-30')
assert.equal(monthRange('2026-02').last, '2026-02-28')
assert.equal(monthRange('2028-02').last, '2028-02-29')

// monthGrid: 10/2026 bắt đầu Thứ Năm → 3 ô trống đầu; 31 ngày → 5 tuần, đủ 7 ô mỗi tuần
const oct = monthGrid('2026-10')
assert.equal(oct.length, 5)
assert.ok(oct.every((w) => w.length === 7))
assert.deepEqual(oct[0].slice(0, 4), [null, null, null, '2026-10-01'])
assert.equal(oct[4][5], '2026-10-31') // 31/10/2026 là Thứ Bảy
assert.equal(oct[4][6], null)
// 2/2027 bắt đầu Thứ Hai, 28 ngày → đúng 4 tuần, không ô trống
const feb = monthGrid('2027-02')
assert.equal(feb.length, 4)
assert.equal(feb[0][0], '2027-02-01')
assert.equal(feb[3][6], '2027-02-28')
// 3/2026 bắt đầu Chủ Nhật → 6 ô trống, 6 tuần
const mar = monthGrid('2026-03')
assert.equal(mar.length, 6)
assert.equal(mar[0][6], '2026-03-01')
// mọi ngày trong tháng có mặt đúng một lần
assert.equal(oct.flat().filter(Boolean).length, 31)

// sessionDay / sessionTime: theo chuỗi, không đổi múi giờ (0h30 giờ VN vẫn là ngày đó)
assert.equal(sessionDay('2026-10-29T00:30:00+07:00'), '2026-10-29')
assert.equal(sessionTime('2026-10-29T18:42:05+07:00'), '18:42')

// groupByDay: giữ thứ tự vào
const items = [
  { id: 'c', recorded_at: '2026-10-29T18:42:00+07:00' },
  { id: 'b', recorded_at: '2026-10-29T08:37:00+07:00' },
  { id: 'a', recorded_at: '2026-10-27T21:10:00+07:00' },
]
const g = groupByDay(items)
assert.deepEqual(
  g.get('2026-10-29')?.map((x) => x.id),
  ['c', 'b'],
)
assert.deepEqual(
  g.get('2026-10-27')?.map((x) => x.id),
  ['a'],
)
assert.equal(g.get('2026-10-28'), undefined)

// dayState
assert.equal(dayState(undefined), 'rest')
assert.equal(dayState({ n_reps: 0, met: false }), 'rest')
assert.equal(dayState({ n_reps: 0, met: true }), 'rest') // không tập thì không tô, kể cả server báo đạt
assert.equal(dayState({ n_reps: 8, met: false }), 'trained')
assert.equal(dayState({ n_reps: 27, met: true }), 'met')

assert.equal(monthLabel('2026-10'), 'Tháng 10, 2026')

console.log('check-history-calendar: ok')
