// Kiểm tra FrameRecorder và toBase64 (web/src/session/format.ts, định dạng v2) bằng Node.
// tests/test_web_recorder.py gọi script này; thoát mã khác 0 nếu có assert sai.
// Chạy: node web/scripts/check-recorder.ts   (Node ≥ 22.18 chạy thẳng .ts)
import assert from 'node:assert/strict'
import { FrameRecorder, KP_MISSING, toBase64 } from '../src/session/format.ts'
import type { Keypoint } from '../src/session/format.ts'

const kp = (v: number): Keypoint[] => Array.from({ length: 33 }, () => [v, v, v] as Keypoint)

// Hiệp dài hơn sức chứa ban đầu (1024 khung): khối byte nới ra, không mất khung nào.
const rec = new FrameRecorder()
const N = 2500
for (let i = 0; i < N; i++) rec.add(1000 + i * 50, i % 10 === 0 ? null : kp((i % 1000) / 10000))
assert.equal(rec.count, N)
assert.equal(rec.seenCount, N - N / 10)
assert.equal(rec.durationMs, (N - 1) * 50)
const out = rec.take()
assert.equal(out.t_ms.length, N)
assert.equal(out.kp.length, N * 33 * 3 * 2)
const view = new DataView(out.kp.buffer, out.kp.byteOffset, out.kp.byteLength)
const at = (frame: number, value: number) => view.getInt16((frame * 99 + value) * 2, true)
assert.equal(at(0, 0), KP_MISSING) // khung 0 không thấy người: cả khung
assert.equal(at(0, 98), KP_MISSING)
assert.equal(at(1, 0), 1) // 0,0001 → 1
assert.equal(at(2047, 50), 47) // khung sau lần nới
assert.equal(at(2499, 98), 499)

// take() trả hết và làm mới bộ ghi.
assert.equal(rec.count, 0)
assert.equal(rec.seenCount, 0)
assert.equal(rec.durationMs, 0)

// toBase64 khớp Buffer của Node, kể cả khối lớn hơn một khúc 32 KB.
const big = new Uint8Array(100_000).map((_, i) => (i * 31) % 256)
assert.equal(toBase64(big), Buffer.from(big).toString('base64'))
assert.equal(toBase64(new Uint8Array(0)), '')

console.log('check-recorder: ok')
