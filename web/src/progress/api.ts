// Gọi API mục tiêu và tiến độ (ARCHITECTURE §4). Chỉ lấy dữ liệu: "đạt", streak tính ở server
// (formcoach/progress/goals.py). "Hôm nay" là ngày theo giờ điện thoại, web gửi lên.
import { failure } from '../http'

export interface Goal {
  daily_reps: number
  min_good_ratio: number | null
  from_date: string
}

export interface DayProgress {
  day: string // YYYY-MM-DD
  n_reps: number
  n_good: number
  good_ratio: number | null
  daily_reps: number | null // mục tiêu của ngày đó (null = chưa đặt)
  met: boolean
}

export interface Progress {
  exercise: string
  from: string
  to: string
  goal: Goal | null
  today: DayProgress
  streak: number
  totals: { n_reps: number; n_good: number; good_ratio: number | null }
  days: DayProgress[]
}

export async function fetchProgress(exercise: string, from: string, to: string): Promise<Progress> {
  const q = new URLSearchParams({ exercise, from, to })
  const r = await fetch(`/api/progress?${q}`)
  if (!r.ok) throw await failure(r)
  return r.json()
}

/** Đặt mục tiêu từ hôm nay (đặt lại cùng ngày thì ghi đè). */
export async function saveGoal(exercise: string, dailyReps: number, today: string): Promise<Goal> {
  const r = await fetch('/api/goals', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ exercise, daily_reps: dailyReps, today }),
  })
  if (!r.ok) throw await failure(r)
  return (await r.json()).goal
}

/** Hiệp gần nhất của mình (lịch sử mới nhất trước), không có → null. */
export async function fetchLatestSession(): Promise<{ exercise: string; session_id: string } | null> {
  const r = await fetch('/api/results')
  if (!r.ok) throw await failure(r)
  const items: { exercise: string; session_id: string }[] = await r.json()
  return items[0] ?? null
}
