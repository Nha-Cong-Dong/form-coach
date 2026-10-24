// Gọi API kết quả (ARCHITECTURE §4). Chỉ lấy dữ liệu; phân loại rep nằm ở server (formcoach).
import { failure } from '../http'

export interface ResultRep {
  index: number
  start_frame: number
  end_frame: number
  errors: string[]
  scores: Record<string, number> | null
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

/** Hash URL của trang kết quả, vd `#result/pushup/2026-10-24T18-42-00_pushup`. */
export const resultHash = (exercise: string, sessionId: string) =>
  `#result/${exercise}/${encodeURIComponent(sessionId)}`
