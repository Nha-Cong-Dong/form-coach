// Màn Lịch sử (D0e, bạn chọn bản B): lịch tháng tô theo tiến độ (đạt / có tập / nghỉ, như đồ thị
// Dashboard) + danh sách hiệp của ngày đang chọn, bấm → trang kết quả. Chỉ hiển thị: "đạt" do
// server tính (/api/progress), danh sách hiệp từ /api/results. Không có trong canvas.
import { useEffect, useState } from 'react'
import {
  dayState,
  groupByDay,
  monthGrid,
  monthLabel,
  monthOf,
  monthRange,
  sessionTime,
  shiftMonth,
} from '../history/calendar'
import type { Month } from '../history/calendar'
import { fetchProgress } from '../progress/api'
import type { DayProgress } from '../progress/api'
import { dayLabel, localDate } from '../progress/format'
import { fetchHistory, resultHash } from '../results/api'
import type { HistoryItem } from '../results/api'
import { formatDuration } from '../results/format'

const EXERCISE = 'pushup'
const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
const STATE_TEXT = { met: 'đạt mục tiêu', trained: 'có tập, chưa đạt', rest: 'không tập' }

interface Props {
  admin: boolean // admin: thêm link Gán nhãn (thanh dưới điện thoại không có mục này)
}

export default function HistoryView({ admin }: Props) {
  // "Hôm nay" chốt lúc mở màn (theo giờ máy), như Dashboard.
  const [today] = useState(() => localDate(new Date()))
  const [month, setMonth] = useState<Month>(() => monthOf(today))
  const [selected, setSelected] = useState(today)
  const [sessions, setSessions] = useState<HistoryItem[] | null>(null)
  // Tiến độ kèm tháng của nó: đổi tháng thì `days` tự thành null (đang tải) cho tới khi có số mới.
  const [loaded, setLoaded] = useState<{ month: Month; days: Map<string, DayProgress> } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchHistory()
      .then((items) => setSessions(items.filter((s) => s.exercise === EXERCISE)))
      .catch((e: Error) => setError(e.message))
  }, [])

  // Tiến độ từng ngày của tháng đang xem; tháng hiện tại chỉ hỏi tới hôm nay.
  useEffect(() => {
    let cancelled = false
    const { first, last } = monthRange(month)
    fetchProgress(EXERCISE, first, last < today ? last : today)
      .then((p) => !cancelled && setLoaded({ month, days: new Map(p.days.map((d) => [d.day, d])) }))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [month, today])

  if (error) {
    return (
      <div className="form-alert" role="alert">
        Không tải được lịch sử ({error}).
      </div>
    )
  }

  const thisMonth = monthOf(today)
  const days = loaded?.month === month ? loaded.days : null
  const goTo = (m: Month) => {
    setMonth(m)
    // Đổi tháng thì chọn hôm nay (tháng này) hoặc ngày cuối tháng (tháng trước).
    setSelected(m === thisMonth ? today : monthRange(m).last)
  }
  const byDay = groupByDay(sessions ?? [])
  const daySessions = byDay.get(selected) ?? []
  const dayReps = daySessions.reduce((n, s) => n + s.n_reps, 0)
  const dayGood = daySessions.reduce((n, s) => n + s.n_good, 0)

  return (
    <div className="history">
      <header className="result-head">
        <h1>Lịch sử</h1>
        <span>Push-up · {sessions === null ? '…' : `${sessions.length} hiệp`}</span>
      </header>

      <section className="card history-cal">
        <div className="cal-head">
          <button type="button" className="icon-button" aria-label="Tháng trước" onClick={() => goTo(shiftMonth(month, -1))}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          <h2 aria-live="polite">{monthLabel(month)}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="Tháng sau"
            disabled={month >= thisMonth}
            onClick={() => goTo(shiftMonth(month, 1))}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        </div>
        <div className="cal-grid" role="grid" aria-label={monthLabel(month)}>
          {WEEKDAYS.map((w) => (
            <span key={w} className="cal-weekday" aria-hidden="true">
              {w}
            </span>
          ))}
          {monthGrid(month)
            .flat()
            .map((day, i) => {
              if (day === null) return <span key={`blank-${i}`} />
              const n = Number(day.slice(8))
              if (day > today) {
                return (
                  <span key={day} className="cal-day future" aria-hidden="true">
                    {n}
                  </span>
                )
              }
              const state = dayState(days?.get(day))
              const classes = ['cal-day', state, day === selected ? 'selected' : '', day === today ? 'today' : '']
              return (
                <button
                  key={day}
                  type="button"
                  className={classes.join(' ')}
                  aria-pressed={day === selected}
                  aria-label={`${dayLabel(day, true)}: ${STATE_TEXT[state]}`}
                  onClick={() => setSelected(day)}
                >
                  {n}
                </button>
              )
            })}
        </div>
        <div className="legend" aria-hidden="true">
          <span>
            <i className="legend-swatch met" />
            Đạt mục tiêu
          </span>
          <span>
            <i className="legend-swatch unmet" />
            Có tập, chưa đạt
          </span>
        </div>
      </section>

      <section className="card">
        <h2>{selected === today ? `Hôm nay · ${dayLabel(selected)}` : dayLabel(selected, true)}</h2>
        {sessions === null ? (
          <p className="label">Đang tải…</p>
        ) : daySessions.length === 0 ? (
          <p className="label">Không tập ngày này.</p>
        ) : (
          <>
            <p className="label history-day-sum">
              {daySessions.length} hiệp · {dayReps} rep · {dayGood} đúng
            </p>
            <ul className="history-list">
              {daySessions.map((s) => (
                <li key={s.session_id}>
                  <a href={resultHash(s.exercise, s.session_id)}>
                    <span className="history-time">{sessionTime(s.recorded_at)}</span>
                    <span className="history-reps">
                      {s.n_reps} rep · {s.n_good} đúng
                    </span>
                    <span className="label">{formatDuration(s.duration_s)}</span>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M9 18l6-6-6-6" />
                    </svg>
                  </a>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {admin && (
        <p className="label history-admin">
          <a href="#label">Gán nhãn (công cụ dữ liệu) →</a>
        </p>
      )}
    </div>
  )
}
