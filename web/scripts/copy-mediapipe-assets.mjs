// Chép wasm của MediaPipe JS và file model vào public/ để Vite phục vụ từ chính laptop.
// Chạy tự động trước `npm run dev` / `npm run build` (predev / prebuild trong package.json).
// Lý do không dùng CDN: điện thoại hay dùng hotspot, tải ~13 MB wasm từ internet mỗi lần tốn data;
// lấy từ laptop thì đi qua mạng nội bộ, và đúng phiên bản trong package-lock.json.
import { cpSync, existsSync, mkdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const web = join(dirname(fileURLToPath(import.meta.url)), '..')

const wasmSrc = join(web, 'node_modules/@mediapipe/tasks-vision/wasm')
const wasmDst = join(web, 'public/mediapipe/wasm')
cpSync(wasmSrc, wasmDst, { recursive: true })
console.log(`[assets] wasm  -> ${wasmDst}`)

// Cùng file model với đường offline (assets/ ở gốc repo), để hai đường dùng chung một model.
const modelSrc = join(web, '../assets/pose_landmarker_full.task')
const modelDst = join(web, 'public/models/pose_landmarker_full.task')
if (!existsSync(modelSrc)) {
  console.error(
    `[assets] THIẾU model ${modelSrc}\n` +
      '  Tải bằng: mkdir -p assets && curl -L -o assets/pose_landmarker_full.task ' +
      'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task',
  )
  process.exit(1)
}
if (!existsSync(modelDst) || statSync(modelDst).size !== statSync(modelSrc).size) {
  mkdirSync(dirname(modelDst), { recursive: true })
  cpSync(modelSrc, modelDst)
}
console.log(`[assets] model -> ${modelDst}`)
