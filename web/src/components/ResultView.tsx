// Trang kết quả một hiệp, theo canvas "Kết quả" (DESIGN.md). Chỉ hiển thị: rep và lỗi do server
// phân loại (formcoach) và câu coach do server dựng.
import { useEffect, useState } from 'react'
import RepReplay from './RepReplay'
import { fetchExercise, fetchResult } from '../results/api'
import type { ExerciseInfo, SessionResult } from '../results/api'
import {
  formatDuration,
  formatRecordedAt,
  measureText,
  outsideTarget,
  repRanges,
  repsByError,
  targetText,
} from '../results/format'

const EXERCISE_NAMES: Record<string, string> = { pushup: 'Push-up', squat: 'Squat' }
const MODEL_NAMES: Record<string, string> = {
  rules: 'luật ngưỡng',
  stump: 'ngưỡng học',
  rf: 'random forest',
}

// Vòng tiến độ: bán kính 58 trong khung 132 (như canvas); chu vi = 2πr.
const RING_R = 58
const RING_C = 2 * Math.PI * RING_R

interface Props {
  exercise: string
  sessionId: string
}

export default function ResultView({ exercise, sessionId }: Props) {
  const [result, setResult] = useState<SessionResult | null | undefined>(undefined)
  const [info, setInfo] = useState<ExerciseInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [replay, setReplay] = useState<number | null>(null) // rep đang xem lại (người que)

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchResult(exercise, sessionId), fetchExercise(exercise)])
      .then(([r, i]) => {
        if (cancelled) return
        setResult(r)
        setInfo(i)
      })
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [exercise, sessionId])

  if (error) {
    return (
      <div className="form-alert" role="alert">
        Không tải được kết quả ({error}).
      </div>
    )
  }
  if (result === undefined || info === null) return <p className="hint">Đang tải kết quả…</p>
  if (result === null) {
    return (
      <div className="result">
        <p className="form-notice">Chưa có kết quả cho hiệp này. Hiệp quay trước khi có trang kết quả, hoặc không phải hiệp của bạn.</p>
        <a className="primary link-button" href="#capture">
          Quay hiệp mới
        </a>
      </div>
    )
  }

  const name = (code: string) => info.error_display[code] ?? code
  const { n_reps, n_good, good_ratio } = result.summary
  const n_fix = n_reps - n_good
  const percent = good_ratio === null ? 0 : Math.round(good_ratio * 100)
  const byError = repsByError(result.reps, info.error_labels)
  const top = byError.reduce<(typeof byError)[number] | null>(
    (best, e) => (best === null || e.reps.length > best.reps.length ? e : best),
    null,
  )
  const headline =
    n_reps === 0 ? 'Chưa đếm được rep nào' : n_fix === 0 ? 'Tất cả rep đều đúng' : `${n_fix} rep cần sửa`

  return (
    <div className="result">
      <header className="result-head">
        <h1>Kết quả hiệp</h1>
        <span>
          {EXERCISE_NAMES[result.exercise] ?? result.exercise} · {formatRecordedAt(result.recorded_at)}
        </span>
      </header>

      <section className="card result-ring-card">
        <div className="ring">
          <svg width="132" height="132" viewBox="0 0 132 132" role="img" aria-label={`${n_good} trên ${n_reps} rep đúng kỹ thuật`}>
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
              strokeDashoffset={RING_C * (1 - (good_ratio ?? 0))}
              transform="rotate(-90 66 66)"
              style={{ stroke: 'var(--color-accent)' }}
            />
          </svg>
          <div className="ring-text" aria-hidden="true">
            <span className="ring-number">{n_good}</span>
            <span>/ {n_reps} rep</span>
          </div>
        </div>
        <div className="result-ring-copy">
          <span className="label">{n_reps === 0 ? 'Không có rep để chấm' : `Đúng kỹ thuật · ${percent}%`}</span>
          <span className="headline">{headline}</span>
          {n_reps === 0 && (
            <span className="label">Kiểm tra cả người nằm trong khung, quay từ bên hông và xuống đủ sâu.</span>
          )}
        </div>
      </section>

      <div className="stat-grid">
        <section className="card stat">
          <span className="label">Thời lượng</span>
          <span className="stat-number">{formatDuration(result.duration_s)}</span>
          <span className="label">{n_reps} rep</span>
        </section>
        <section className="card stat">
          <span className="label">Lỗi nhiều nhất</span>
          {top ? (
            <>
              <span className="stat-number">{top.reps.length}</span>
              <span className="label">{name(top.error)}</span>
            </>
          ) : (
            <>
              <span className="stat-number">0</span>
              <span className="label">Không có lỗi</span>
            </>
          )}
        </section>
      </div>

      {n_reps > 0 && (
        <section className="card">
          <h2>Từng rep</h2>
          <p className="label measure-target">Bấm vào một rep để xem lại bằng người que.</p>
          <ol className="rep-grid">
            {result.reps.map((rep) => {
              const ok = rep.errors.length === 0
              return (
                <li key={rep.index}>
                  <button
                    type="button"
                    className={ok ? 'rep-dot ok' : 'rep-dot fix'}
                    aria-label={`Rep ${rep.index + 1}, ${ok ? 'đúng' : rep.errors.map(name).join(', ')}. Xem lại`}
                    onClick={() => setReplay(rep.index)}
                  >
                    {rep.index + 1}
                  </button>
                </li>
              )
            })}
          </ol>
          <div className="legend" aria-hidden="true">
            <span>
              <i className="rep-dot ok mini" />
              Đúng
            </span>
            <span>
              <i className="rep-dot fix mini" />
              Cần sửa
            </span>
          </div>
        </section>
      )}

      {/* Số đo từng rep (vd góc khuỷu ở đáy) kèm mục tiêu: người tập thấy cần sửa bao nhiêu,
          không chỉ "sai". Viền theo số đo so với mục tiêu, không theo bộ phân loại: mô hình (rf)
          có thể báo lỗi dù số đo trong mục tiêu, viền khi đó tự mâu thuẫn ("57°" viền đậm cạnh
          "Mục tiêu ≤ 67°"). Kết luận của mô hình vẫn ở vòng rep và thẻ "Cần sửa". */}
      {n_reps > 0 &&
        result.measures.map((m) => (
          <section className="card" key={m.feature}>
            <h2>{m.label}</h2>
            <p className="label measure-target">
              Mục tiêu {targetText(m.op, m.threshold, m.unit)}
            </p>
            <ol className="measure-grid">
              {result.reps.map((rep) => {
                const raw = rep.measures?.[m.feature]
                const outside = outsideTarget(m.op, m.threshold, raw)
                const value = measureText(raw, m.unit)
                return (
                  <li key={rep.index}>
                    <button
                      type="button"
                      className={outside ? 'measure measure-fix' : 'measure measure-ok'}
                      aria-label={`Rep ${rep.index + 1}: ${m.label.toLowerCase()} ${value}${outside ? ', ngoài mục tiêu' : ''}. Xem lại`}
                      onClick={() => setReplay(rep.index)}
                    >
                      <span className="measure-rep">Rep {rep.index + 1}</span>
                      <span className="measure-value">{value}</span>
                    </button>
                  </li>
                )
              })}
            </ol>
            <div className="legend" aria-hidden="true">
              <span>
                <i className="measure-swatch measure-ok" />
                Đạt
              </span>
              <span>
                <i className="measure-swatch measure-fix" />
                Chưa đạt
              </span>
            </div>
          </section>
        ))}

      {byError.length > 0 && (
        <section className="card">
          <h2>Cần sửa</h2>
          <ul className="fix-list">
            {byError.map((e) => (
              <li key={e.error}>
                <span className="fix-name">{name(e.error)}</span>
                <span className="label">
                  {e.reps.length === 1 ? 'Rep' : `${e.reps.length} rep:`} {repRanges(e.reps)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.coach && (
        <section className="card coach-card" aria-labelledby="coach-title">
          <h2 id="coach-title">Coach</h2>
          <p className="coach-text">{result.coach.text}</p>
          <p className="caption">Công cụ hỗ trợ, không thay huấn luyện viên.</p>
        </section>
      )}

      <div className="result-actions">
        <a className="primary link-button" href="#capture">
          Hiệp tiếp theo
        </a>
        <span className="caption">Phân tích bằng {MODEL_NAMES[result.model_name] ?? result.model_name}.</span>
      </div>

      {replay !== null && result.reps[replay] && (
        <RepReplay
          exercise={result.exercise}
          sessionId={result.session_id}
          rep={result.reps[replay]}
          measures={result.measures}
          errorName={name}
          onClose={() => setReplay(null)}
        />
      )}
    </div>
  )
}
