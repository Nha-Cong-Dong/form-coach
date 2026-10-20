// Định dạng file keypoint mà trang quay gửi về server (docs/ARCHITECTURE.md §2b, format_version 1).
// Phía Python kiểm tra bằng formcoach/pose/session_json.py: sai một trường là bị từ chối (422).
// File này không import gì, nên chạy được trực tiếp bằng `node` (dùng để kiểm tra chéo với Python).

export const FORMAT_VERSION = 1

// 33 khớp MediaPipe theo đúng thứ tự index (giống formcoach/pose/joints.py).
// Server so khớp danh sách này từng phần tử, lệch là báo lỗi ngay ở lần gửi đầu.
export const JOINT_NAMES = [
  'nose',
  'left_eye_inner',
  'left_eye',
  'left_eye_outer',
  'right_eye_inner',
  'right_eye',
  'right_eye_outer',
  'left_ear',
  'right_ear',
  'mouth_left',
  'mouth_right',
  'left_shoulder',
  'right_shoulder',
  'left_elbow',
  'right_elbow',
  'left_wrist',
  'right_wrist',
  'left_pinky',
  'right_pinky',
  'left_index',
  'right_index',
  'left_thumb',
  'right_thumb',
  'left_hip',
  'right_hip',
  'left_knee',
  'right_knee',
  'left_ankle',
  'right_ankle',
  'left_heel',
  'right_heel',
  'left_foot_index',
  'right_foot_index',
] as const

/** [x, y, visibility]; x, y chuẩn hoá 0–1 theo chiều rộng / chiều cao khung. */
export type Keypoint = [number, number, number]

export interface FrameRecord {
  t_ms: number // ms kể từ lúc bấm Bắt đầu, tăng ngặt
  kp: Keypoint[] | null // null = khung không thấy người
}

export interface SessionFile {
  format_version: number
  session_id: string
  exercise: string
  set_errors: string[]
  recorded_at: string
  notes: string // ghi chú tuỳ chọn về điều kiện quay (ánh sáng, quần áo, chỗ quay…); "" nếu không ghi
  source: { pose: string; version: string; model: string }
  frame_size: [number, number]
  joint_names: string[]
  frames: FrameRecord[]
}

/** Landmark tối thiểu cần dùng (khớp với NormalizedLandmark của MediaPipe). */
export interface LandmarkLike {
  x: number
  y: number
  visibility: number
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "2026-10-20T19-05-12_pushup": theo giờ máy, chỉ gồm chữ/số/'-'/'_' (server dùng làm tên file). */
export function makeSessionId(date: Date, exercise: string): string {
  const d = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  const t = `${pad(date.getHours())}-${pad(date.getMinutes())}-${pad(date.getSeconds())}`
  return `${d}T${t}_${exercise}`
}

/** ISO 8601 theo giờ máy kèm múi giờ, vd "2026-10-20T19:05:12+07:00". */
export function localIsoString(date: Date): string {
  const offsetMin = -date.getTimezoneOffset()
  const sign = offsetMin >= 0 ? '+' : '-'
  const abs = Math.abs(offsetMin)
  const d = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  const t = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  return `${d}T${t}${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

const round = (v: number, digits: number) => Number(v.toFixed(digits))

/** Landmark của một khung → 33 × [x, y, visibility] (làm tròn 4 chữ số để file gọn), hoặc null. */
export function toKeypoints(pose: LandmarkLike[] | undefined): Keypoint[] | null {
  if (!pose || pose.length !== JOINT_NAMES.length) return null
  return pose.map((l) => [round(l.x, 4), round(l.y, 4), round(l.visibility, 4)])
}

/**
 * Ghi khung cho một hiệp: giữ t_ms tăng ngặt (làm tròn 0,1 ms có thể làm hai khung sát nhau trùng giá trị).
 */
export class FrameRecorder {
  private frames: FrameRecord[] = []
  private startTs: number | null = null

  add(ts: number, kp: Keypoint[] | null): void {
    if (this.startTs === null) this.startTs = ts
    let t = round(ts - this.startTs, 1)
    const last = this.frames.at(-1)
    if (last && t <= last.t_ms) t = round(last.t_ms + 0.1, 1)
    this.frames.push({ t_ms: t, kp })
  }

  get count(): number {
    return this.frames.length
  }

  get seenCount(): number {
    return this.frames.filter((f) => f.kp !== null).length
  }

  take(): FrameRecord[] {
    const out = this.frames
    this.frames = []
    this.startTs = null
    return out
  }
}

export function buildSession(args: {
  exercise: string
  setErrors: string[]
  notes: string
  startedAt: Date
  frameSize: [number, number]
  frames: FrameRecord[]
  source: { version: string; model: string }
}): SessionFile {
  return {
    format_version: FORMAT_VERSION,
    session_id: makeSessionId(args.startedAt, args.exercise),
    exercise: args.exercise,
    set_errors: [...args.setErrors],
    recorded_at: localIsoString(args.startedAt),
    notes: args.notes.trim(),
    source: { pose: 'mediapipe-js', version: args.source.version, model: args.source.model },
    frame_size: args.frameSize,
    joint_names: [...JOINT_NAMES],
    frames: args.frames,
  }
}
