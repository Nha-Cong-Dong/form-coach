// Gọi API kết quả (ARCHITECTURE §4). Chỉ lấy dữ liệu; phân loại rep nằm ở server (formcoach).
import { failure } from '../http'

export interface ResultRep {
  index: number
  start_frame: number
  end_frame: number
  errors: string[]
  scores: Record<string, number> | null
  measures: Record<string, number | null> // số đo hiện cho người dùng (vd min_elbow_angle)
}

/** Số đo hiện ở trang kết quả; mục tiêu = phía ngược với luật của lỗi (lỗi khi giá trị <op> ngưỡng). */
export interface Measure {
  error: string
  feature: string
  label: string
  unit: string
  op: '<' | '>'
  threshold: number
}

export interface ResultSummary {
  n_reps: number
  n_good: number
  good_ratio: number | null
  error_counts: Record<string, number>
}

export interface SessionResult {
  session_id: string
  exercise: string
  recorded_at: string
  set_errors: string[]
  model_name: string
  n_frames: number
  duration_s: number
  reps: ResultRep[]
  summary: ResultSummary
  measures: Measure[]
  coach?: CoachText // server dựng câu (TemplateCoach); web chỉ hiển thị
}

/** Nhận xét của coach; các dòng cách nhau bằng "\n". `source`: "template" (sau này "deepseek"). */
export interface CoachText {
  text: string
  source: string
}

export interface ExerciseInfo {
  name: string
  error_labels: string[]
  error_display: Record<string, string>
}

/** Kết quả đã lưu của một hiệp; 404 (không có / không phải của mình) → null. */
export async function fetchResult(exercise: string, sessionId: string): Promise<SessionResult | null> {
  const r = await fetch(`/api/sessions/${exercise}/${encodeURIComponent(sessionId)}/result`)
  if (r.status === 404) return null
  if (!r.ok) throw await failure(r)
  return r.json()
}

export async function fetchExercise(exercise: string): Promise<ExerciseInfo> {
  const r = await fetch(`/api/exercises/${exercise}`)
  if (!r.ok) throw await failure(r)
  return r.json()
}

/** Người que của một rep để phát lại (chỉ khung xương, không có video). */
export interface RepReplayData {
  joints: string[]
  frame_size: [number, number]
  times_s: (number | null)[] // tính từ khung đầu của đoạn cắt
  keypoints: ([number, number] | null)[][] // [khung][khớp], toạ độ 0–1
  rep_start_s: number // rep thật bắt đầu/kết thúc trong đoạn (có đệm 0,3 s mỗi bên)
  rep_end_s: number
}

export async function fetchRepReplay(
  exercise: string,
  sessionId: string,
  index: number,
): Promise<RepReplayData> {
  const r = await fetch(
    `/api/sessions/${exercise}/${encodeURIComponent(sessionId)}/result/reps/${index}/replay`,
  )
  if (!r.ok) throw await failure(r)
  return r.json()
}

/** Hash URL của trang kết quả, vd `#result/pushup/2026-10-24T18-42-00_pushup`. */
export const resultHash = (exercise: string, sessionId: string) =>
  `#result/${exercise}/${encodeURIComponent(sessionId)}`
