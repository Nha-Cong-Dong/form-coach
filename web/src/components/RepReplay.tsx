// Xem lại MỘT rep ở trang kết quả: người que chuyển động theo đúng thời gian thật (không có
// video, chỉ khung xương), lặp lại liên tục, có tạm dừng và chậm 0,5×. Kèm lỗi và số đo của rep.
import { useEffect, useRef, useState } from 'react'
import { fetchRepReplay } from '../results/api'
import type { Measure, RepReplayData, ResultRep } from '../results/api'
import { frameAt, measureText } from '../results/format'
import StickFigure from './StickFigure'

interface Props {
  exercise: string
  sessionId: string
  rep: ResultRep
  measures: Measure[]
  errorName: (code: string) => string
  onClose: () => void
}

const SPEEDS = [1, 0.5] as const

export default function RepReplay({ exercise, sessionId, rep, measures, errorName, onClose }: Props) {
  const [data, setData] = useState<RepReplayData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1)
  const [t, setT] = useState(0) // giây trong đoạn đang phát
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    let cancelled = false
    fetchRepReplay(exercise, sessionId, rep.index)
      .then((d) => !cancelled && setData(d))
      .catch((e: Error) => !cancelled && setError(e.message))
    return () => {
      cancelled = true
    }
  }, [exercise, sessionId, rep.index])

  // Esc để đóng; đưa focus vào nút Đóng khi mở (bàn phím, trình đọc màn hình).
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // Vòng phát: thời gian thật × tốc độ, quay lại đầu khi hết đoạn.
  useEffect(() => {
    if (!data || !playing) return
    const duration = data.times_s[data.times_s.length - 1] ?? 0
    if (duration <= 0) return
    let handle = 0
    let last = performance.now()
    const tick = (now: number) => {
      const dt = ((now - last) / 1000) * speed
      last = now
      setT((cur) => (cur + dt) % duration)
      handle = requestAnimationFrame(tick)
    }
    handle = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(handle)
  }, [data, playing, speed])

  const frame = data ? frameAt(data.times_s, t) : -1
  const inRep = data ? t >= data.rep_start_s && t <= data.rep_end_s : false

  return (
    <div className="replay-backdrop" onClick={onClose}>
      <div
        className="replay card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="replay-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="replay-head">
          <h2 id="replay-title">Rep {rep.index + 1}</h2>
          <button ref={closeRef} type="button" className="icon-button" aria-label="Đóng" onClick={onClose}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <p className="replay-verdict">
          {rep.errors.length === 0 ? 'Đúng kỹ thuật' : rep.errors.map(errorName).join(' · ')}
        </p>
        {measures.length > 0 && (
          <p className="label">
            {measures
              .map((m) => `${m.label}: ${measureText(rep.measures?.[m.feature], m.unit)}`)
              .join(' · ')}
          </p>
        )}

        <div className="replay-stage">
          {error && <p className="form-alert">Không tải được rep ({error}).</p>}
          {!data && !error && <p className="label">Đang tải…</p>}
          {data && frame >= 0 && (
            <StickFigure joints={data.joints} points={data.keypoints[frame]} frameSize={data.frame_size} />
          )}
          {/* Đoạn phát có đệm 0,3 s trước/sau rep: báo rõ đang ở trong rep hay ở phần đệm. */}
          {data && <span className={inRep ? 'replay-phase in' : 'replay-phase'}>{inRep ? 'Trong rep' : 'Trước / sau rep'}</span>}
        </div>

        <div className="replay-controls">
          <button type="button" className="secondary-button" onClick={() => setPlaying((p) => !p)}>
            {playing ? 'Tạm dừng' : 'Phát'}
          </button>
          <div className="segmented" role="group" aria-label="Tốc độ phát">
            {SPEEDS.map((s) => (
              <button key={s} type="button" aria-pressed={speed === s} onClick={() => setSpeed(s)}>
                {s === 1 ? '1×' : '0,5×'}
              </button>
            ))}
          </div>
        </div>
        <p className="caption">Chỉ có khung xương (video không được lưu).</p>
      </div>
    </div>
  )
}
