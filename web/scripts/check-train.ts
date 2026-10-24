// Kiểm tra logic thuần màn Tập (web/src/train/body.ts) bằng Node.
// tests/test_web_train.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-train.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { RollingRatio, bodyVisible } from '../src/train/body.ts'

const pose = (visible: number[], vis = 0.9) =>
  Array.from({ length: 33 }, (_, i) => ({ visibility: visible.includes(i) ? vis : 0.1 }))

// Không thấy người
assert.equal(bodyVisible(undefined), false)
// Đủ một bên (trái: vai 11, cổ tay 15, hông 23, cổ chân 27) → thấy
assert.equal(bodyVisible(pose([11, 15, 23, 27])), true)
// Đủ bên phải → thấy
assert.equal(bodyVisible(pose([12, 16, 24, 28])), true)
// Thiếu cổ chân (bị cắt khỏi khung) → chưa thấy
assert.equal(bodyVisible(pose([11, 15, 23])), false)
// Mỗi bên thiếu một khớp khác nhau → chưa thấy (phải đủ trên CÙNG một bên)
assert.equal(bodyVisible(pose([11, 15, 23, 16, 24, 28])), false)
// Visibility thấp hơn ngưỡng → chưa thấy
assert.equal(bodyVisible(pose([11, 15, 23, 27], 0.4)), false)
// Thiếu hẳn khớp trong mảng (mảng ngắn) → chưa thấy, không lỗi
assert.equal(bodyVisible([{ visibility: 1 }]), false)

// RollingRatio: tỉ lệ trong cửa sổ trượt
const r = new RollingRatio(4)
assert.equal(r.push(true), 1)
assert.equal(r.push(false), 0.5)
r.push(false)
r.push(false)
assert.equal(r.push(true), 0.25) // cửa sổ 4: [false, false, false, true]

console.log('check-train: ok')
