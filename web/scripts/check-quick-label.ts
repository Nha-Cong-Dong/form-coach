// Kiểm tra logic thuần của chế độ gán nhãn nhanh (web/src/label/quick.ts) bằng Node, không cần
// thư viện test. tests/test_web_quick_label.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-quick-label.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import {
  buildQueue,
  firstUnreviewed,
  hasPreviousSession,
  keyAction,
  labelsChanged,
  parseStringSet,
  pickFrames,
  reviewedKey,
  toggleError,
  toggleValid,
} from '../src/label/quick.ts'

const label = (over = {}) => ({
  rep_index: 0,
  start_frame: 0,
  end_frame: 10,
  start_s: 0,
  end_s: 1,
  valid: true,
  errors: [] as string[],
  note: '',
  ...over,
})

// --- buildQueue: lọc theo ngày, bỏ hiệp hỏng / không rep, xếp cũ → mới
const sessions = [
  { session_id: 'c', recorded_at: '2026-10-23T09:00:00+07:00', n_reps: 5 },
  { session_id: 'a', recorded_at: '2026-10-20T10:14:01+07:00', n_reps: 4 }, // trước ngày bắt đầu
  { session_id: 'b', recorded_at: '2026-10-21T18:36:55+07:00', n_reps: 4 },
  { session_id: 'broken', error: 'file hỏng' },
  { session_id: 'empty', recorded_at: '2026-10-22T08:00:00+07:00', n_reps: 0 },
]
assert.deepEqual(
  buildQueue(sessions, '2026-10-21').map((s) => s.session_id),
  ['b', 'c'],
)
assert.deepEqual(buildQueue(sessions, '2026-10-23').map((s) => s.session_id), ['c'])
assert.equal(sessions[0].session_id, 'c') // không sửa mảng gốc

// --- keyAction
const errors = ['shallow', 'incomplete_lockout', 'hip_sag', 'hip_high', 'neck_drop']
assert.deepEqual(keyAction('1', errors), { type: 'toggle', error: 'shallow' })
assert.deepEqual(keyAction('5', errors), { type: 'toggle', error: 'neck_drop' })
assert.equal(keyAction('6', errors), null) // chỉ có 5 lỗi
assert.deepEqual(keyAction('0', errors), { type: 'valid' })
assert.deepEqual(keyAction('X', errors), { type: 'valid' })
assert.deepEqual(keyAction('Enter', errors), { type: 'save' })
assert.deepEqual(keyAction('Backspace', errors), { type: 'back' })
assert.deepEqual(keyAction('ArrowLeft', errors), { type: 'back' })
assert.equal(keyAction('a', errors), null)

// --- toggleError: bật/tắt, giữ thứ tự cố định, không sửa bản gốc, rep không hợp lệ bỏ qua
const base = label({ errors: ['shallow'] })
const withNeck = toggleError(base, 'neck_drop')
assert.deepEqual(withNeck.errors, ['neck_drop', 'shallow']) // sắp xếp như server lưu
assert.deepEqual(base.errors, ['shallow'])
assert.deepEqual(toggleError(withNeck, 'shallow').errors, ['neck_drop'])
assert.deepEqual(toggleError(label({ valid: false }), 'shallow').errors, [])

// --- toggleValid: không phải rep thì xoá lỗi; bật lại không tự khôi phục lỗi
const off = toggleValid(base)
assert.equal(off.valid, false)
assert.deepEqual(off.errors, [])
assert.equal(toggleValid(off).valid, true)
assert.deepEqual(toggleValid(off).errors, [])
assert.equal(base.valid, true)

// --- pickFrames: đáy từ bottom_frame, đỉnh = cuối rep, luôn trong khoảng khung hợp lệ
const rep = (over = {}, features: Record<string, number | null> = {}) => ({
  index: 0,
  start_frame: 10,
  end_frame: 40,
  start_s: 0,
  end_s: 1,
  features,
  ...over,
})
assert.deepEqual(pickFrames(rep({}, { bottom_frame: 25 }), 100), { bottom: 25, top: 40 })
assert.deepEqual(pickFrames(rep({}, {}), 100), { bottom: 25, top: 40 }) // thiếu → giữa rep
assert.deepEqual(pickFrames(rep({}, { bottom_frame: null }), 100), { bottom: 25, top: 40 })
assert.deepEqual(pickFrames(rep({ end_frame: 500 }, { bottom_frame: 600 }), 100), { bottom: 99, top: 99 })
assert.deepEqual(pickFrames(rep({ start_frame: -5, end_frame: -1 }, {}), 100), { bottom: 0, top: 0 })

// --- parseStringSet: dữ liệu hỏng thì rỗng, chỉ nhận chuỗi
assert.deepEqual([...parseStringSet(null)], [])
assert.deepEqual([...parseStringSet('không phải json')], [])
assert.deepEqual([...parseStringSet('{"a": 1}')], [])
assert.deepEqual([...parseStringSet('["a", 3, "b", null]')], ['a', 'b'])

// --- firstUnreviewed: tiếp tục từ rep chưa duyệt đầu tiên
const done = new Set([reviewedKey('s1', 0), reviewedKey('s1', 1), reviewedKey('s2', 0)])
assert.equal(firstUnreviewed('s1', [0, 1, 2, 3], done), 2)
assert.equal(firstUnreviewed('s1', [0, 1], done), null) // duyệt hết
assert.equal(firstUnreviewed('s3', [0, 1], done), 0)
assert.equal(firstUnreviewed('s2', [0, 1], done), 1) // khoá theo hiệp, không lẫn hiệp khác

// --- hasPreviousSession: quay lại hiệp trước chỉ khi còn hiệp chưa bị bỏ qua phía trước
const q = [{ session_id: 'a' }, { session_id: 'b' }, { session_id: 'c' }]
assert.equal(hasPreviousSession(q, 0, new Set()), false) // hiệp đầu tiên: không có gì phía trước
assert.equal(hasPreviousSession(q, 1, new Set()), true)
assert.equal(hasPreviousSession(q, 2, new Set(['a'])), true) // còn b
assert.equal(hasPreviousSession(q, 2, new Set(['a', 'b'])), false) // đã bỏ qua hết
assert.equal(hasPreviousSession(q, 1, new Set(['c'])), true) // chỉ xét phía trước

// --- labelsChanged: phát hiện sửa dở để lưu trước khi rời hiệp
const saved = [label({ errors: ['shallow'] }), label({ rep_index: 1 })]
assert.equal(labelsChanged(saved, [label({ errors: ['shallow'] }), label({ rep_index: 1 })]), false)
assert.equal(labelsChanged(saved, [saved[0], toggleError(saved[1], 'hip_sag')]), true)
assert.equal(labelsChanged(saved, [saved[0], { ...saved[1], note: 'không chắc' }]), true)
assert.equal(labelsChanged(saved, [saved[0]]), true)

console.log('check-quick-label: ok')
