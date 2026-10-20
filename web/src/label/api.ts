// Gọi API gán nhãn của backend (ARCHITECTURE §4). Chỉ lấy/gửi dữ liệu, không có logic ML:
// rep được cắt và kiểm tra ở server (formcoach).

export const EXERCISE = 'pushup'

/** Một dòng của GET /api/sessions/{exercise}. File hỏng chỉ có session_id + error. */
export interface SessionSummary {
  session_id: string
  recorded_at?: string
  set_errors?: string[]
  notes?: string
  duration_s?: number
  n_reps?: number
  labeled?: boolean
  error?: string
}

/** Lỗi HTTP kèm thông báo `detail` của FastAPI, để hiện cho người dùng biết sai ở đâu. */
async function failure(r: Response): Promise<Error> {
  let detail = ''
  try {
    const body: { detail?: unknown } = await r.json()
    detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch {
    // body không phải JSON (vd backend chưa chạy, Vite trả 502): chỉ báo mã HTTP
  }
  return new Error(detail ? `HTTP ${r.status}: ${detail}` : `HTTP ${r.status}`)
}

export async function listSessions(exercise: string = EXERCISE): Promise<SessionSummary[]> {
  const r = await fetch(`/api/sessions/${exercise}`)
  if (!r.ok) throw await failure(r)
  return r.json()
}

/** Một rep do bộ đếm ở server cắt ra (khung tính từ 0, thời gian tính từ khung đầu). */
export interface ReviewRep {
  index: number
  start_frame: number
  end_frame: number
  start_s: number
  end_s: number
  features: Record<string, number | null>
}

/** Nhãn một rep (ARCHITECTURE §2c). valid = false: không phải rep (cắt nhầm), không gắn lỗi. */
export interface RepLabel {
  rep_index: number
  start_frame: number
  end_frame: number
  start_s: number
  end_s: number
  valid: boolean
  errors: string[]
  note: string
}

/** File nhãn của một hiệp (ARCHITECTURE §2c); server kiểm tra lại khi lưu. */
export interface LabelsFile {
  format_version: number
  session_id: string
  exercise: string
  labeled_at: string
  segmenter_thresholds: Record<string, number>
  reps: RepLabel[]
}

/** GET /api/sessions/{exercise}/{id}/review (formcoach/review.py). */
export interface ReviewData {
  session_id: string
  exercise: string
  recorded_at: string
  set_errors: string[]
  notes: string // ghi chú điều kiện quay (trang quay); "" nếu không ghi
  error_labels: string[]
  frame_size: [number, number]
  fps: number
  times_s: number[]
  primary_signal: string
  signals: Record<string, (number | null)[]>
  thresholds: Record<string, number>
  joints: string[]
  keypoints: ([number, number] | null)[][] // [khung][khớp], toạ độ chuẩn hoá 0–1
  reps: ReviewRep[]
  labels: LabelsFile // nhãn đã lưu, hoặc nhãn mặc định (set_errors cho mọi rep) nếu chưa gán
  labels_saved: boolean
  alignment_problems: string[]
}

export async function getReview(sessionId: string, exercise: string = EXERCISE): Promise<ReviewData> {
  const r = await fetch(`/api/sessions/${exercise}/${encodeURIComponent(sessionId)}/review`)
  if (!r.ok) throw await failure(r)
  return r.json()
}

/** PUT nhãn. Server trả 422 nếu nhãn sai, 409 nếu không còn khớp rep (bộ đếm đã đổi). */
export async function putLabels(labels: LabelsFile): Promise<void> {
  const url = `/api/sessions/${labels.exercise}/${encodeURIComponent(labels.session_id)}/labels`
  const r = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(labels),
  })
  if (!r.ok) throw await failure(r)
}
