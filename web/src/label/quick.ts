// Logic thuần của chế độ gán nhãn nhanh: không React, không DOM, để test bằng Node
// (web/scripts/check-quick-label.ts, chạy qua tests/test_web_quick_label.py).
// Chỉ import kiểu (import type) nên Node chạy thẳng file .ts này được.
import type { RepLabel, ReviewRep, SessionSummary } from './api'

/** Ngày đầu tiên của dataset chấm điểm (các hiệp quay thử nằm trước đó). */
export const DEFAULT_SINCE = '2026-10-21'

/**
 * Hiệp đưa vào hàng đợi gán nhãn lại: không hỏng, có rep, quay từ ngày `since` (YYYY-MM-DD, theo
 * giờ ghi trong file) trở đi. Xếp cũ → mới để gán nhãn theo đúng thứ tự đã quay.
 */
export function buildQueue(sessions: SessionSummary[], since: string): SessionSummary[] {
  return sessions
    .filter((s) => !s.error && (s.n_reps ?? 0) > 0 && (s.recorded_at ?? '').slice(0, 10) >= since)
    .sort((a, b) => (a.recorded_at ?? '').localeCompare(b.recorded_at ?? ''))
}

export type KeyAction =
  | { type: 'toggle'; error: string }
  | { type: 'valid' }
  | { type: 'save' }
  | { type: 'back' }

/** Phím tắt: 1–9 bật/tắt lỗi theo thứ tự `errorLabels`, 0 hoặc X = "không phải rep". */
export function keyAction(key: string, errorLabels: string[]): KeyAction | null {
  if (/^[1-9]$/.test(key)) {
    const error = errorLabels[Number(key) - 1]
    return error === undefined ? null : { type: 'toggle', error }
  }
  switch (key.toLowerCase()) {
    case '0':
    case 'x':
      return { type: 'valid' }
    case 'enter':
      return { type: 'save' }
    case 'backspace':
    case 'arrowleft':
      return { type: 'back' }
    default:
      return null
  }
}

/** Bật/tắt một lỗi. Rep "không phải rep" không gắn lỗi nên bỏ qua. Không sửa bản gốc. */
export function toggleError(label: RepLabel, error: string): RepLabel {
  if (!label.valid) return label
  const errors = label.errors.includes(error)
    ? label.errors.filter((e) => e !== error)
    : [...label.errors, error].sort()
  return { ...label, errors }
}

/** Đổi "là rep / không phải rep". Không phải rep thì xoá lỗi (server không nhận cả hai). */
export function toggleValid(label: RepLabel): RepLabel {
  return { ...label, valid: !label.valid, errors: label.valid ? [] : label.errors }
}

/** Hai khung tĩnh để xem: đáy rep và lúc vừa lên xong. Luôn nằm trong [0, nFrames - 1]. */
export function pickFrames(rep: ReviewRep, nFrames: number): { bottom: number; top: number } {
  const clamp = (f: number) => Math.min(Math.max(Math.round(f), 0), nFrames - 1)
  const bottom = rep.features.bottom_frame ?? (rep.start_frame + rep.end_frame) / 2
  return { bottom: clamp(bottom), top: clamp(rep.end_frame) }
}

/** Còn hiệp nào phía trước (chưa bị bỏ qua) để quay lại không. */
export function hasPreviousSession(
  queue: SessionSummary[],
  index: number,
  skipped: ReadonlySet<string>,
): boolean {
  return queue.slice(0, index).some((s) => !skipped.has(s.session_id))
}

/** Nhãn đang sửa khác bản đã lưu không (để lưu trước khi rời hiệp). */
export function labelsChanged(saved: RepLabel[], current: RepLabel[]): boolean {
  return JSON.stringify(saved) !== JSON.stringify(current)
}

export const reviewedKey = (sessionId: string, repIndex: number) => `${sessionId}:${repIndex}`

/** Đọc tập chuỗi đã lưu trong localStorage; dữ liệu hỏng hoặc thiếu thì coi như rỗng. */
export function parseStringSet(raw: string | null): Set<string> {
  if (!raw) return new Set()
  try {
    const value: unknown = JSON.parse(raw)
    return new Set(Array.isArray(value) ? value.filter((v) => typeof v === 'string') : [])
  } catch {
    return new Set()
  }
}

/** Vị trí rep đầu tiên chưa duyệt trong hiệp, hoặc null nếu đã duyệt hết. */
export function firstUnreviewed(
  sessionId: string,
  repIndexes: number[],
  reviewed: ReadonlySet<string>,
): number | null {
  const pos = repIndexes.findIndex((r) => !reviewed.has(reviewedKey(sessionId, r)))
  return pos === -1 ? null : pos
}
