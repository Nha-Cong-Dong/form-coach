// Tạo PoseLandmarker của MediaPipe JS (cùng model "full" với đường Python offline).
// web/ không chứa logic ML: chỉ lấy keypoint từng khung để vẽ và (bước 9b(ii)) gửi về server.
import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision'

export const MEDIAPIPE_VERSION = '1.1.1' // khớp package.json; ghi vào JSON ở bước 9b(ii)
export const MODEL_NAME = 'pose_landmarker_full'

// Do scripts/copy-mediapipe-assets.mjs chép vào public/ (phục vụ từ laptop, không qua CDN).
const WASM_PATH = '/mediapipe/wasm'
const MODEL_PATH = `/models/${MODEL_NAME}.task`

export type Delegate = 'GPU' | 'CPU'

export interface LoadedLandmarker {
  landmarker: PoseLandmarker
  delegate: Delegate
}

/** Thử chạy trên GPU (nhanh hơn); máy nào không hỗ trợ thì lùi về CPU. */
export async function createPoseLandmarker(): Promise<LoadedLandmarker> {
  const fileset = await FilesetResolver.forVisionTasks(WASM_PATH)
  let lastError: unknown
  for (const delegate of ['GPU', 'CPU'] as const) {
    try {
      const landmarker = await PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_PATH, delegate },
        runningMode: 'VIDEO', // nhớ vị trí người ở khung trước, cần timestamp tăng ngặt
        numPoses: 1,
      })
      return { landmarker, delegate }
    } catch (err) {
      lastError = err
    }
  }
  throw lastError
}
