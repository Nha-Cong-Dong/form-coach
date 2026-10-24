// Định dạng cho trang kết quả (hàm thuần, có test: web/scripts/check-result-format.ts).

/** Số rep (đếm từ 1) → chuỗi gọn: [7] → "7", [9, 10, 11, 12] → "9–12", [1, 3, 4] → "1, 3–4". */
export function repRanges(numbers: number[]): string {
  const sorted = [...new Set(numbers)].sort((a, b) => a - b)
  const parts: string[] = []
  let i = 0
  while (i < sorted.length) {
    let j = i
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j] + 1) j++
    parts.push(j === i ? `${sorted[i]}` : `${sorted[i]}–${sorted[j]}`)
    i = j + 1
  }
  return parts.join(', ')
}

/** Giây → "m:ss" (65.4 → "1:05"). */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/** "2026-10-24T18:42:00+07:00" → "24/10 · 18:42" theo giờ của máy; chuỗi lạ → giữ nguyên. */
export function formatRecordedAt(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const two = (n: number) => String(n).padStart(2, '0')
  return `${two(d.getDate())}/${two(d.getMonth() + 1)} · ${two(d.getHours())}:${two(d.getMinutes())}`
}

/** Khung đang hiện tại thời điểm t (giây): khung cuối cùng có times[i] ≤ t. Rỗng → -1. */
export function frameAt(times: (number | null)[], t: number): number {
  let lo = 0
  let hi = times.length - 1
  if (hi < 0) return -1
  let best = 0
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if ((times[mid] ?? 0) <= t) {
      best = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return best
}

/** Mục tiêu của một số đo: lỗi khi `giá trị > ngưỡng` thì mục tiêu "≤ ngưỡng", và ngược lại. */
export function targetText(op: '<' | '>', threshold: number, unit: string): string {
  return `${op === '>' ? '≤' : '≥'} ${Math.round(threshold)}${unit}`
}

/** Số đo một rep: làm tròn, kèm đơn vị; không đo được (null) → "—". */
export function measureText(value: number | null | undefined, unit: string): string {
  return value === null || value === undefined ? '—' : `${Math.round(value)}${unit}`
}

/** Mỗi lỗi có ít nhất một rep → danh sách số rep (đếm từ 1), theo thứ tự `errorLabels`. */
export function repsByError(
  reps: { index: number; errors: string[] }[],
  errorLabels: string[],
): { error: string; reps: number[] }[] {
  return errorLabels
    .map((error) => ({ error, reps: reps.filter((r) => r.errors.includes(error)).map((r) => r.index + 1) }))
    .filter((e) => e.reps.length > 0)
}
