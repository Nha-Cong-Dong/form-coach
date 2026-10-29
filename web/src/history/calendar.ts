// Lịch tháng cho màn Lịch sử (hàm thuần, có test: web/scripts/check-history-calendar.ts).
// Ngày là chuỗi "YYYY-MM-DD" theo giờ máy, như Dashboard (progress/format.ts).
// Đuôi .ts để script test chạy bằng Node trực tiếp (Vite và tsconfig đều cho phép).
import { localDate } from '../progress/format.ts'

/** Tháng dạng "YYYY-MM". */
export type Month = string

/** "2026-10-29" → "2026-10". */
export const monthOf = (day: string): Month => day.slice(0, 7)

/** Tháng cộng n (n âm = lùi), qua năm đúng. */
export function shiftMonth(month: Month, n: number): Month {
  const [y, m] = month.split('-').map(Number)
  return localDate(new Date(y, m - 1 + n, 1)).slice(0, 7)
}

/** Ngày đầu và cuối tháng (cuối = ngày 28–31 tuỳ tháng). */
export function monthRange(month: Month): { first: string; last: string } {
  const [y, m] = month.split('-').map(Number)
  return { first: `${month}-01`, last: localDate(new Date(y, m, 0)) }
}

/** Lưới tháng theo tuần, tuần bắt đầu Thứ Hai; ô trước ngày 1 và sau ngày cuối là null. */
export function monthGrid(month: Month): (string | null)[][] {
  const [y, m] = month.split('-').map(Number)
  const { last } = monthRange(month)
  const nDays = Number(last.slice(8))
  // getDay(): 0 = Chủ Nhật; đổi sang 0 = Thứ Hai.
  const lead = (new Date(y, m - 1, 1).getDay() + 6) % 7
  const cells: (string | null)[] = Array(lead).fill(null)
  for (let d = 1; d <= nDays; d++) cells.push(`${month}-${String(d).padStart(2, '0')}`)
  while (cells.length % 7) cells.push(null)
  const weeks: (string | null)[][] = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
}

/** Ngày của một hiệp: phần ngày trong `recorded_at`, theo múi giờ của chính chuỗi đó (giờ điện
 *  thoại lúc quay). Cùng quy tắc với server (formcoach/progress/goals.py) để lịch khớp tiến độ. */
export const sessionDay = (recordedAt: string): string => recordedAt.slice(0, 10)

/** Gom hiệp theo ngày; trong ngày giữ thứ tự của danh sách vào (API trả mới nhất trước). */
export function groupByDay<T extends { recorded_at: string }>(items: T[]): Map<string, T[]> {
  const byDay = new Map<string, T[]>()
  for (const it of items) {
    const day = sessionDay(it.recorded_at)
    const list = byDay.get(day)
    if (list) list.push(it)
    else byDay.set(day, [it])
  }
  return byDay
}

export type DayState = 'met' | 'trained' | 'rest'

/** Màu một ô: đạt mục tiêu / có tập nhưng chưa đạt / không tập ("đạt" do server tính). */
export function dayState(p: { n_reps: number; met: boolean } | undefined): DayState {
  if (!p || p.n_reps === 0) return 'rest'
  return p.met ? 'met' : 'trained'
}

/** "2026-10" → "Tháng 10, 2026". */
export function monthLabel(month: Month): string {
  const [y, m] = month.split('-').map(Number)
  return `Tháng ${m}, ${y}`
}

/** "2026-10-29T18:42:00+07:00" → "18:42" (giờ ghi trong chuỗi, không đổi múi giờ). */
export const sessionTime = (recordedAt: string): string => recordedAt.slice(11, 16)
