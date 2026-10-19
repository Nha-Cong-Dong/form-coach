// Dựng một file quay mẫu bằng CHÍNH code của trang quay (src/session/format.ts), ghi ra đĩa.
// tests/test_web_format.py gọi script này rồi kiểm tra file bằng parse_session của Python,
// để chắc hai bên (TypeScript và Python) hiểu cùng một định dạng.
// Chạy: node web/scripts/sample-session.ts <đường-dẫn-ra.json>   (Node ≥ 22.18 chạy thẳng .ts)
import { writeFileSync } from 'node:fs'
import { FrameRecorder, JOINT_NAMES, buildSession, toKeypoints } from '../src/session/format.ts'

const out = process.argv[2]
if (!out) {
  console.error('Thiếu đường dẫn file ra')
  process.exit(2)
}

const recorder = new FrameRecorder()
let ts = 1000.0 // như performance.now(): không bắt đầu từ 0
for (let i = 0; i < 60; i++) {
  // Khoảng cách khung dao động như camera thật; khung 30–31 sát nhau (0,04 ms) để thử giữ t_ms tăng ngặt.
  ts += i === 31 ? 0.04 : 33.3 + ((i * 7) % 11) - 5
  const visible = i !== 20 // khung 20 không thấy người
  const pose = visible
    ? JOINT_NAMES.map((_, j) => ({ x: 0.3 + j * 0.01, y: 0.5, visibility: 0.9 }))
    : undefined
  recorder.add(ts, toKeypoints(pose))
}

const session = buildSession({
  exercise: 'pushup',
  setErrors: ['shallow'],
  startedAt: new Date(2026, 9, 20, 19, 5, 12),
  frameSize: [1280, 720],
  frames: recorder.take(),
  source: { version: '1.1.1', model: 'pose_landmarker_full' },
})
writeFileSync(out, JSON.stringify(session))
console.log(`ghi ${session.frames.length} khung vào ${out}`)
