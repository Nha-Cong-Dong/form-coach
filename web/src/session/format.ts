// Định dạng file keypoint mà trang quay gửi về server (docs/ARCHITECTURE.md §2b, format_version 2).
// Phía Python kiểm tra bằng formcoach/pose/session_json.py: sai một trường là bị từ chối (422).
// File này không import gì, nên chạy được trực tiếp bằng `node` (dùng để kiểm tra chéo với Python).
//
// v2: keypoint cả hiệp là MỘT khối int16 (base64), không phải list lồng nhau như v1: server đọc
// bằng numpy, không tạo hàng triệu object (v1 làm server hết RAM với hiệp > ~10 phút). Ghi thẳng
// vào khối này ngay lúc quay nên điện thoại cũng không giữ hàng triệu mảng nhỏ.

export const FORMAT_VERSION = 2
// Giá trị int16 = round(v × KP_SCALE) (đúng 4 chữ số như v1); cả khung = KP_MISSING: không thấy người.
export const KP_SCALE = 10000
export const KP_MISSING = -32768
const KP_MAX = 32767 // kẹp toạ độ quá ±3,28 lần khung (vô nghĩa) để vừa int16
// Mỗi hiệp tối đa 30 phút: server từ chối hiệp dài hơn (backend/limits.py MAX_SESSION_S), nên
// trang quay tự dừng ở mốc này thay vì để người tập mất cả hiệp.
export const MAX_SESSION_MS = 30 * 60 * 1000

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

/** Các khung đã ghi của một hiệp, dạng đóng gói (FrameRecorder.take()). */
export interface RecordedFrames {
  t_ms: number[] // ms kể từ khung đầu, tăng ngặt
  kp: Uint8Array // int16 little-endian, [khung][33 khớp][x, y, visibility]
  seen: number // số khung thấy người
}

export interface SessionFile {
  format_version: number
  session_id: string
  exercise: string
  set_errors: string[]
  recorded_at: string
  notes: string // ghi chú tuỳ chọn về điều kiện quay (ánh sáng, quần áo, chỗ quay…); "" nếu không ghi
  // "train" = chế độ Tập (không có lỗi cố ý), "dataset" = Quay dữ liệu (ARCHITECTURE §2b)
  capture_mode: CaptureMode
  source: { pose: string; version: string; model: string }
  frame_size: [number, number]
  joint_names: string[]
  t_ms: number[]
  kp_i16: string // base64 của RecordedFrames.kp
}

/** Landmark tối thiểu cần dùng (khớp với NormalizedLandmark của MediaPipe). */
export interface LandmarkLike {
  x: number
  y: number
  visibility: number
}

const pad = (n: number) => String(n).padStart(2, '0')

/** "2026-10-20T19-05-12_a3f9c1_pushup": theo giờ máy + đuôi ngẫu nhiên, chỉ gồm chữ/số/'-'/'_'
 *  (server dùng làm tên file). Hiệp cũ không có đuôi vẫn hợp lệ. */
export function makeSessionId(date: Date, exercise: string, suffix: string = randomSuffix()): string {
  const d = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  const t = `${pad(date.getHours())}-${pad(date.getMinutes())}-${pad(date.getSeconds())}`
  return `${d}T${t}_${suffix}_${exercise}`
}

/** 6 ký tự hex ngẫu nhiên (24 bit). session_id là duy nhất trên cả server: thiếu đuôi này thì hai
 *  người gửi hiệp cùng một giây đụng tên, người sau bị 409 mãi (gửi lại vẫn trùng). Đuôi đặt SAU
 *  giờ để sắp theo tên file vẫn là theo thời gian. */
export function randomSuffix(): string {
  const bytes = new Uint8Array(3)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
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

const VALUES_PER_FRAME = JOINT_NAMES.length * 3
const BYTES_PER_FRAME = VALUES_PER_FRAME * 2

const toInt16 = (v: number) => Math.max(-KP_MAX, Math.min(KP_MAX, Math.round(v * KP_SCALE)))

/**
 * Ghi khung cho một hiệp, đóng gói ngay vào khối int16 (định dạng v2). Giữ t_ms tăng ngặt (làm
 * tròn 0,1 ms có thể làm hai khung sát nhau trùng giá trị).
 */
export class FrameRecorder {
  private times: number[] = []
  private bytes = new Uint8Array(BYTES_PER_FRAME * 1024) // nới gấp đôi khi đầy
  private seen = 0
  private startTs: number | null = null

  add(ts: number, kp: Keypoint[] | null): void {
    if (this.startTs === null) this.startTs = ts
    let t = round(ts - this.startTs, 1)
    const last = this.times.at(-1)
    if (last !== undefined && t <= last) t = round(last + 0.1, 1)
    const offset = this.times.length * BYTES_PER_FRAME
    if (offset + BYTES_PER_FRAME > this.bytes.length) {
      const bigger = new Uint8Array(this.bytes.length * 2)
      bigger.set(this.bytes)
      this.bytes = bigger
    }
    // DataView ghi rõ little-endian (định dạng quy định), không phụ thuộc máy.
    const view = new DataView(this.bytes.buffer, offset, BYTES_PER_FRAME)
    for (let i = 0; i < VALUES_PER_FRAME; i++) {
      const value = kp === null ? KP_MISSING : toInt16(kp[Math.floor(i / 3)][i % 3])
      view.setInt16(i * 2, value, true)
    }
    if (kp !== null) this.seen += 1
    this.times.push(t)
  }

  get count(): number {
    return this.times.length
  }

  get seenCount(): number {
    return this.seen
  }

  /** ms từ khung đầu tới khung cuối (0 khi chưa có khung). */
  get durationMs(): number {
    return this.times.at(-1) ?? 0
  }

  take(): RecordedFrames {
    const out = {
      t_ms: this.times,
      kp: this.bytes.slice(0, this.times.length * BYTES_PER_FRAME),
      seen: this.seen,
    }
    this.times = []
    this.bytes = new Uint8Array(BYTES_PER_FRAME * 1024)
    this.seen = 0
    this.startTs = null
    return out
  }
}

/** Byte → base64. Từng khúc 32 KB: String.fromCharCode(...mảng lớn) tràn stack. Không dùng
 *  Uint8Array.toBase64 vì điện thoại cũ chưa có. */
export function toBase64(bytes: Uint8Array): string {
  const CHUNK = 0x8000
  let binary = ''
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK))
  }
  return btoa(binary)
}

export type CaptureMode = 'dataset' | 'train'

export function buildSession(args: {
  exercise: string
  setErrors: string[]
  notes: string
  captureMode: CaptureMode
  startedAt: Date
  frameSize: [number, number]
  frames: RecordedFrames
  source: { version: string; model: string }
  idSuffix?: string // chỉ để test có tên cố định; bỏ trống = ngẫu nhiên
}): SessionFile {
  return {
    format_version: FORMAT_VERSION,
    session_id: makeSessionId(args.startedAt, args.exercise, args.idSuffix),
    exercise: args.exercise,
    set_errors: [...args.setErrors],
    recorded_at: localIsoString(args.startedAt),
    notes: args.notes.trim(),
    capture_mode: args.captureMode,
    source: { pose: 'mediapipe-js', version: args.source.version, model: args.source.model },
    frame_size: args.frameSize,
    joint_names: [...JOINT_NAMES],
    t_ms: args.frames.t_ms,
    kp_i16: toBase64(args.frames.kp),
  }
}
