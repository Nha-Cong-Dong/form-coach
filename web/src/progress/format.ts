// Ngày và chữ cho Dashboard (hàm thuần, có test: web/scripts/check-progress-format.ts).
// Ngày luôn theo giờ của máy (khớp `recorded_at` do web ghi), không đổi sang UTC.

const two = (n: number) => String(n).padStart(2, '0')

/** Ngày theo giờ máy → "YYYY-MM-DD" (toISOString() sẽ đổi sang UTC: sai từ 0h tới 7h ở VN). */
export function localDate(d: Date): string {
  return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`
}

/** "YYYY-MM-DD" cộng n ngày (n âm = lùi). Tính bằng ngày lịch, không bằng 24 giờ. */
export function addDays(day: string, n: number): string {
  const [y, m, d] = day.split('-').map(Number)
  return localDate(new Date(y, m - 1, d + n))
}

const WEEKDAYS = ['Chủ Nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy']

/** "2026-10-23" → "23/10"; kèm thứ → "Thứ Sáu, 23/10". */
export function dayLabel(day: string, withWeekday = false): string {
  const [y, m, d] = day.split('-').map(Number)
  const short = `${two(d)}/${two(m)}`
  return withWeekday ? `${WEEKDAYS[new Date(y, m - 1, d).getDay()]}, ${short}` : short
}

/** Câu dưới vòng tiến độ, theo số rep hôm nay và mục tiêu. */
export function goalHeadline(
  nReps: number,
  goal: { daily_reps: number; min_good_ratio: number | null } | null,
  met: boolean,
): string {
  if (goal === null) return nReps > 0 ? 'Hôm nay đã tập' : 'Chưa tập hôm nay'
  if (met) return 'Đã đạt mục tiêu hôm nay'
  const left = goal.daily_reps - nReps
  if (left > 0) return `Còn ${left} rep nữa là đạt mục tiêu`
  // Đủ rep nhưng tỉ lệ rep đúng dưới mức tối thiểu.
  return `Đủ rep, cần ít nhất ${Math.round((goal.min_good_ratio ?? 0) * 100)}% rep đúng`
}

/** Tỉ lệ 0–1 → "71%"; chưa có rep → "—". */
export function percentText(ratio: number | null): string {
  return ratio === null ? '—' : `${Math.round(ratio * 100)}%`
}
