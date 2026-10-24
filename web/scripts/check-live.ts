// Kiểm tra logic đếm trực tiếp phía web (web/src/train/live.ts) bằng Node.
// tests/test_web_live.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-live.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { FpsMeter, SendThrottle, encodeFrame, liveUrl, parseServerMessage } from '../src/train/live.ts'

// liveUrl: cùng nguồn, https → wss
assert.equal(liveUrl({ protocol: 'https:', host: '192.168.1.5:5173' }), 'wss://192.168.1.5:5173/api/live')
assert.equal(liveUrl({ protocol: 'http:', host: 'localhost:5173' }), 'ws://localhost:5173/api/live')

// FpsMeter: 15 khung cách đều 66,7 ms → 15 fps
const meter = new FpsMeter(30)
assert.equal(meter.fps, null)
for (let i = 0; i < 15; i++) meter.push(i * (1000 / 15))
assert.ok(Math.abs((meter.fps ?? 0) - 15) < 0.01)
// Cửa sổ trượt: chỉ nhớ `size` khung gần nhất (đổi nhịp thì đo theo nhịp mới)
const small = new FpsMeter(5)
for (let i = 0; i < 10; i++) small.push(i * 100) // 10 fps
for (let i = 0; i < 5; i++) small.push(1000 + i * 50) // 20 fps
assert.ok(Math.abs((small.fps ?? 0) - 20) < 0.01)

// SendThrottle: camera 60 fps → gửi ~30 fps (bỏ mỗi khung thứ hai)
const th = new SendThrottle(30)
const sent = Array.from({ length: 60 }, (_, i) => th.shouldSend(i * (1000 / 60))).filter(Boolean).length
assert.equal(sent, 30)
// Camera 15 fps: không bỏ khung nào
const th15 = new SendThrottle(30)
assert.equal(Array.from({ length: 15 }, (_, i) => th15.shouldSend(i * (1000 / 15))).filter(Boolean).length, 15)

// encodeFrame: làm tròn 4 chữ số; không người → null; visibility thiếu → 0
const f = JSON.parse(encodeFrame(1234.567, [{ x: 0.123456, y: 0.98765, visibility: 0.912345 }]))
assert.deepEqual(f, { t_ms: 1234.6, kp: [[0.1235, 0.9877, 0.9123]] })
assert.deepEqual(JSON.parse(encodeFrame(10, undefined)), { t_ms: 10, kp: null })
assert.deepEqual(JSON.parse(encodeFrame(0, [{ x: 0.5, y: 0.5 }])).kp, [[0.5, 0.5, 0]])

// parseServerMessage: đúng dạng → tin; sai → null (không ném lỗi)
assert.deepEqual(parseServerMessage('{"type":"count","n_reps":3,"phase":"up"}'), {
  type: 'count',
  n_reps: 3,
  phase: 'up',
})
assert.deepEqual(parseServerMessage('{"type":"final","n_reps":5}'), { type: 'final', n_reps: 5 })
assert.deepEqual(parseServerMessage('{"type":"error","detail":"x"}'), { type: 'error', detail: 'x' })
for (const bad of ['khong-json', '[]', '{"type":"count"}', '{"type":"la","n_reps":1}', 'null']) {
  assert.equal(parseServerMessage(bad), null, bad)
}

console.log('check-live: ok')
