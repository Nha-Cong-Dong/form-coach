// Dashboard theo canvas "Dashboard" (DESIGN.md): mục tiêu hôm nay, streak, tỉ lệ rep đúng, đồ thị
// 14 ngày. Chỉ hiển thị: "đạt" và streak do server tính (formcoach/progress). Chưa có coach (K1)
// và "lỗi hay gặp" (chưa có API).
import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { fetchLatestSession, fetchProgress, saveGoal } from '../progress/api'
import type { DayProgress, Progress } from '../progress/api'
import { addDays, dayLabel, goalHeadline, localDate, percentText } from '../progress/format'
import { resultHash } from '../results/api'

const EXERCISE = 'pushup'
const DAYS = 14

// Vòng tiến độ như trang kết quả: bán kính 58 trong khung 132.
const RING_R = 58
const RING_C = 2 * Math.PI * RING_R

export default function DashboardView() {
  // "Hôm nay" chốt lúc mở màn (theo giờ máy); mở lại tab thì tính lại.
  const [today] = useState(() => localDate(new Date()))
  const [progress, setProgress] = useState<Progress | null>(null)
  const [latest, setLatest] = useState<{ exercise: string; session_id: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)

  const load = useCallback(
    () =>
      fetchProgress(EXERCISE, addDays(today, -(DAYS - 1)), today)
        .then(setProgress)
        .catch((e: Error) => setError(e.message)),
    [today],
  )

  useEffect(() => {
    load()
    fetchLatestSession()
      .then(setLatest)
      .catch(() => setLatest(null)) // chỉ ẩn nút "Xem buổi gần nhất"
  }, [load])

  if (error) {
    return (
      <div className="form-alert" role="alert">
        Không tải được tiến độ ({error}).
      </div>
    )
  }
  if (progress === null) return <p className="hint">Đang tải tiến độ…</p>

  const { goal, today: day, streak, totals } = progress
  const target = goal?.daily_reps ?? null
  const ratio = target ? Math.min(day.n_reps / target, 1) : day.n_reps > 0 ? 1 : 0

  return (
    <div className="dashboard">
      <header className="result-head dashboard-head">
        <h1>Hôm nay</h1>
        <span>Push-up · {dayLabel(today, true)}</span>
      </header>

      <div className="dashboard-cols">
        <div className="dashboard-col">
          <section className="card result-ring-card">
            <div className="ring">
              <svg
                width="132"
                height="132"
                viewBox="0 0 132 132"
                role="img"
                aria-label={
                  target ? `${day.n_reps} trên ${target} rep mục tiêu hôm nay` : `${day.n_reps} rep hôm nay`
                }
              >
                <circle cx="66" cy="66" r={RING_R} fill="none" strokeWidth="12" style={{ stroke: 'var(--color-track)' }} />
                <circle
                  className="ring-value"
                  cx="66"
                  cy="66"
                  r={RING_R}
                  fill="none"
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeDasharray={RING_C}
                  strokeDashoffset={RING_C * (1 - ratio)}
                  transform="rotate(-90 66 66)"
                  style={{ stroke: 'var(--color-accent)' }}
                />
              </svg>
              <div className="ring-text" aria-hidden="true">
                <span className="ring-number">{day.n_reps}</span>
                <span>{target ? `/ ${target} rep` : 'rep'}</span>
              </div>
            </div>
            <div className="result-ring-copy">
              {/* Mục tiêu đếm mọi rep (quyết định P1), không chỉ rep đúng như chữ trên canvas. */}
              <span className="label">Rep hôm nay</span>
              <span className="headline">{goalHeadline(day.n_reps, goal, day.met)}</span>
              {!editing && (
                <button type="button" className="text-button goal-edit" onClick={() => setEditing(true)}>
                  {goal ? 'Đổi mục tiêu' : 'Đặt mục tiêu'}
                </button>
              )}
            </div>
          </section>

          {editing && (
            <GoalForm
              initial={target}
              onCancel={() => setEditing(false)}
              onSave={async (n) => {
                await saveGoal(EXERCISE, n, today)
                setEditing(false)
                await load()
              }}
            />
          )}

          <div className="stat-grid">
            <section className="card stat">
              <span className="label stat-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ stroke: 'var(--color-accent)' }}>
                  <path d="M12 3c1 3.5 5 5.5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 .5 1.5 1.5 2 2 2 0-3-.5-5 1-8z" />
                </svg>
                Streak
              </span>
              <span className="stat-number">
                {streak} <span className="stat-unit">ngày</span>
              </span>
              <span className="label">{goal ? 'Đạt mục tiêu liên tiếp' : 'Tập liên tiếp'}</span>
            </section>
            <section className="card stat">
              <span className="label">Tỉ lệ rep đúng</span>
              <span className="stat-number">{percentText(totals.good_ratio)}</span>
              <span className="label">
                {DAYS} ngày qua · {totals.n_reps} rep
                {goal?.min_good_ratio != null && ` · tối thiểu ${percentText(goal.min_good_ratio)}`}
              </span>
            </section>
          </div>
        </div>

        <div className="dashboard-col">
          <DayChart days={progress.days} target={target} today={today} />
          <div className="result-actions">
            <a className="primary link-button" href="#capture">
              Bắt đầu hiệp mới
            </a>
            {latest && (
              <a className="text-button link-button" href={resultHash(latest.exercise, latest.session_id)}>
                Xem buổi gần nhất
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Đặt số rep mục tiêu mỗi ngày; áp dụng từ hôm nay, ngày cũ giữ mục tiêu cũ. */
function GoalForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: number | null
  onSave: (dailyReps: number) => Promise<void>
  onCancel: () => void
}) {
  const [value, setValue] = useState(initial ? String(initial) : '')
  const [fieldError, setFieldError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const n = Number(value)
    if (!Number.isInteger(n) || n < 1 || n > 10000) {
      setFieldError('Nhập số rep từ 1 tới 10000.')
      return
    }
    setFieldError(null)
    setSaveError(null)
    setSaving(true)
    try {
      await onSave(n)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
      setSaving(false)
    }
  }

  return (
    <form className="card goal-form" onSubmit={submit} noValidate>
      <h2>Mục tiêu mỗi ngày</h2>
      {saveError && (
        <div className="form-alert" role="alert">
          Chưa lưu được ({saveError}).
        </div>
      )}
      <div className="field">
        <label htmlFor="goal-reps">Số rep mỗi ngày</label>
        <input
          id="goal-reps"
          type="number"
          inputMode="numeric"
          min={1}
          max={10000}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={fieldError !== null}
          aria-describedby={fieldError ? 'goal-error' : undefined}
          autoFocus
        />
        {fieldError && (
          <span id="goal-error" className="field-error">
            {fieldError}
          </span>
        )}
      </div>
      <p className="label">Áp dụng từ hôm nay; các ngày trước giữ mục tiêu cũ.</p>
      <div className="goal-actions">
        <button type="button" className="secondary-button" onClick={onCancel}>
          Huỷ
        </button>
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Đang lưu…' : 'Lưu'}
        </button>
      </div>
    </form>
  )
}

// Đồ thị cột như canvas: khung 308×100, 14 cột rộng 14, cách nhau 22.
const CHART_W = 308
const CHART_H = 100
const BAR_W = 14
const STEP = 22

/** Số rep mỗi ngày: cột đạt mục tiêu `accent`, chưa đạt `tint`, ngày nghỉ một vạch `track`. */
function DayChart({ days, target, today }: { days: DayProgress[]; target: number | null; today: string }) {
  const top = Math.max(...days.map((d) => Math.max(d.n_reps, d.daily_reps ?? 0)), 1) * 1.1
  const y = (n: number) => CHART_H - (n / top) * CHART_H
  const nMet = days.filter((d) => d.met).length
  const nRest = days.filter((d) => d.n_reps === 0).length
  const summary =
    `Số rep mỗi ngày trong ${days.length} ngày qua. ${nMet} ngày đạt mục tiêu, ${nRest} ngày nghỉ, ` +
    `hôm nay ${days[days.length - 1]?.n_reps ?? 0} rep.`

  return (
    <section className="card chart-card">
      <div className="chart-head">
        <h2>{days.length} ngày qua</h2>
        <span className="label">{target ? `Mục tiêu ${target} rep` : 'Chưa đặt mục tiêu'}</span>
      </div>
      <svg width="100%" viewBox={`0 0 ${CHART_W} ${CHART_H}`} role="img" aria-label={summary} className="day-chart">
        {/* Đường mục tiêu vẽ theo từng ngày: đổi mục tiêu thì đường đổi theo, ngày chưa đặt mục
            tiêu thì không có đường (ngày đó "đạt" khi có tập). */}
        {days.map((d, i) =>
          d.daily_reps === null ? null : (
            <line
              key={`goal-${d.day}`}
              x1={i * STEP}
              x2={(i + 1) * STEP}
              y1={y(d.daily_reps)}
              y2={y(d.daily_reps)}
              strokeWidth="1"
              strokeDasharray="3 4"
              style={{ stroke: 'var(--color-ink2)' }}
            />
          ),
        )}
        {days.map((d, i) => {
          const x = 4 + i * STEP
          if (d.n_reps === 0) {
            return (
              <rect key={d.day} x={x} y={CHART_H - 2} width={BAR_W} height="2" rx="1" style={{ fill: 'var(--color-track)' }}>
                <title>{`${dayLabel(d.day)}: nghỉ`}</title>
              </rect>
            )
          }
          const isToday = d.day === today
          return (
            <rect
              key={d.day}
              x={x}
              y={y(d.n_reps)}
              width={BAR_W}
              height={CHART_H - y(d.n_reps)}
              rx="4"
              strokeWidth={isToday ? 2 : 0}
              style={{
                fill: d.met ? 'var(--color-accent)' : 'var(--color-tint)',
                stroke: isToday ? 'var(--color-accent)' : 'none',
              }}
            >
              <title>{`${dayLabel(d.day)}: ${d.n_reps} rep${d.met ? ', đạt' : ''}`}</title>
            </rect>
          )
        })}
      </svg>
      <div className="chart-axis label">
        <span>{dayLabel(days[0]?.day ?? today)}</span>
        <span className="chart-today">Hôm nay</span>
      </div>
      <div className="legend" aria-hidden="true">
        <span>
          <i className="legend-swatch met" />
          Đạt mục tiêu
        </span>
        <span>
          <i className="legend-swatch unmet" />
          Chưa đạt
        </span>
      </div>
    </section>
  )
}
