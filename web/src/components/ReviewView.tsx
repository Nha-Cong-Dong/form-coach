// Xem lại và gán nhãn một hiệp: người que phát lại theo thời gian thật + đồ thị góc khuỷu/thân
// (3b), bảng nhãn từng rep + lưu (3c).
import { useEffect, useMemo, useRef, useState } from 'react'
import { getReview, putLabels } from '../label/api'
import type { RepLabel, ReviewData } from '../label/api'
import { localIsoString } from '../session/format'
import RepTable from './RepTable'
import SignalChart from './SignalChart'
import type { Series } from './SignalChart'
import StickFigure from './StickFigure'

interface Props {
  sessionId: string
  onBack: () => void
}

/** Khung cuối cùng có thời gian ≤ t (tìm nhị phân; times tăng dần). */
function frameAt(times: number[], t: number): number {
  let lo = 0
  let hi = times.length - 1
  while (lo < hi) {
    const mid = Math.ceil((lo + hi) / 2)
    if (times[mid] <= t) lo = mid
    else hi = mid - 1
  }
  return lo
}

const fmt = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v.toFixed(0)}°`)

export default function ReviewView({ sessionId, onBack }: Props) {
  const [data, setData] = useState<ReviewData | null>(null)
  const [labels, setLabels] = useState<RepLabel[]>([])
  const [dirty, setDirty] = useState(false) // có thay đổi chưa lưu
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [error, setError] = useState('')
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const timeRef = useRef(0) // thời điểm đang phát (s); ref vì đổi mỗi khung hình màn hình

  useEffect(() => {
    getReview(sessionId)
      .then((d) => {
        setData(d)
        setLabels(d.labels.reps)
      })
      .catch((e) => setError(`Không tải được hiệp (${e.message}).`))
  }, [sessionId])

  const times = useMemo(() => data?.times_s ?? [], [data])
  const series: Series[] = useMemo(
    () =>
      data
        ? [
            { name: 'góc khuỷu', values: data.signals[data.primary_signal] ?? [], color: '#2563eb' },
            { name: 'góc thân', values: data.signals.body_angle ?? [], color: '#9333ea' },
          ]
        : [],
    [data],
  )

  // Phát theo thời gian thật (t_ms của file), không theo số khung: fps điện thoại không đều.
  useEffect(() => {
    if (!playing || times.length === 0) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      timeRef.current += ((now - last) / 1000) * speed
      last = now
      const end = times[times.length - 1]
      if (timeRef.current >= end) {
        timeRef.current = end
        setFrame(times.length - 1)
        setPlaying(false)
        return
      }
      setFrame(frameAt(times, timeRef.current))
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, speed, times])

  // Còn nhãn chưa lưu mà đóng / tải lại trang → trình duyệt hỏi lại.
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  const seek = (t: number) => {
    timeRef.current = t
    setFrame(frameAt(times, t))
  }

  const back = (
    <div className="controls">
      <button
        className="secondary"
        onClick={() => (!dirty || window.confirm('Nhãn chưa lưu sẽ mất. Vẫn quay lại?')) && onBack()}
      >
        ← Danh sách hiệp
      </button>
    </div>
  )

  if (error)
    return (
      <>
        {back}
        <p className="error">{error}</p>
      </>
    )
  if (!data)
    return (
      <>
        {back}
        <p>Đang tải hiệp {sessionId}… (server chạy bộ đếm, mất vài giây)</p>
      </>
    )

  // Nhãn đã lưu không còn khớp rep hiện tại (bộ đếm đổi sau khi gán): không cho lưu đè,
  // vì gán lại theo số thứ tự có thể gắn nhãn nhầm rep.
  const misaligned = data.alignment_problems.length > 0

  const changeLabel = (index: number, label: RepLabel) => {
    setLabels((ls) => ls.map((l) => (l.rep_index === index ? label : l)))
    setDirty(true)
    setMessage(null)
  }

  const save = () => {
    setSaving(true)
    setMessage(null)
    putLabels({ ...data.labels, labeled_at: localIsoString(new Date()), reps: labels })
      .then(() => {
        setDirty(false)
        setData({ ...data, labels_saved: true })
        setMessage({ kind: 'ok', text: `Đã lưu nhãn ${labels.length} rep.` })
      })
      .catch((e) => setMessage({ kind: 'error', text: `Lưu thất bại: ${e.message}` }))
      .finally(() => setSaving(false))
  }

  const t = times[frame]
  const currentRep = data.reps.find((r) => frame >= r.start_frame && frame <= r.end_frame)
  const togglePlay = () => {
    if (!playing && frame >= times.length - 1) timeRef.current = 0 // hết rồi thì phát lại từ đầu
    setPlaying(!playing)
  }

  return (
    <section className="review">
      {back}
      <h2>{sessionId}</h2>
      <p className="hint">
        Lỗi cố ý của hiệp: {data.set_errors.length ? data.set_errors.join(', ') : 'không (tập đúng)'} ·{' '}
        {data.reps.length} rep · {data.fps} fps
      </p>
      {/* Ghi chú nhập ở trang quay: chỉ để đọc, giải thích điều kiện quay; model không dùng. */}
      <p className="session-notes">
        <b>Ghi chú lúc quay:</b> {data.notes || <span className="hint">(không ghi)</span>}
      </p>
      <div className="review-stage">
        <StickFigure joints={data.joints} points={data.keypoints[frame]} frameSize={data.frame_size} />
      </div>
      <div className="controls playback">
        <button onClick={togglePlay}>{playing ? '⏸ Dừng' : '▶ Phát'}</button>
        <label className="check">
          <input type="checkbox" checked={speed === 0.5} onChange={(e) => setSpeed(e.target.checked ? 0.5 : 1)} />
          chậm 0,5×
        </label>
        <span className="readout">
          {t.toFixed(2)} s · khung {frame} · khuỷu {fmt(series[0].values[frame])} · thân{' '}
          {fmt(series[1].values[frame])} · {currentRep ? `rep ${currentRep.index + 1}` : 'ngoài rep'}
        </span>
      </div>
      <input
        type="range"
        className="scrub"
        min={0}
        max={times.length - 1}
        value={frame}
        onChange={(e) => seek(times[Number(e.target.value)])}
      />
      <SignalChart
        times={times}
        series={series}
        reps={data.reps}
        thresholds={[{ value: data.thresholds.top_min, label: `top_min ${data.thresholds.top_min}° (sẵn sàng)` }]}
        cursorS={t}
        onSeek={seek}
      />
      <div className="panel">
        <h2>Nhãn từng rep</h2>
        <p className="hint">
          {data.labels_saved
            ? 'Đang hiện nhãn đã lưu lần trước.'
            : `Chưa lưu lần nào. Đã điền sẵn cho mọi rep lỗi bạn chọn lúc quay (${
                data.set_errors.length ? data.set_errors.join(', ') : 'không lỗi = tập đúng'
              }); xem lại từng rep, sửa rep nào khác đi, rồi bấm Lưu nhãn.`}
        </p>
        {misaligned && (
          <p className="warn">
            Nhãn đã lưu không còn khớp rep hiện tại (bộ đếm đã đổi): {data.alignment_problems.join('; ')}. Không
            lưu đè được; cần xử lý file nhãn trước.
          </p>
        )}
        {data.reps.length === 0 ? (
          <p>Hiệp này không đếm được rep nào.</p>
        ) : (
          <RepTable
            labels={labels}
            reps={data.reps}
            errorLabels={data.error_labels}
            setErrors={data.set_errors}
            currentIndex={currentRep ? currentRep.index : null}
            onChange={changeLabel}
            onJump={(i) => seek(data.reps[i].start_s)}
          />
        )}
        <div className="controls">
          <button onClick={save} disabled={saving || misaligned || labels.length === 0}>
            {saving ? 'Đang lưu…' : 'Lưu nhãn'}
          </button>{' '}
          {dirty && <span className="warn">Có thay đổi chưa lưu</span>}
          {message && <span className={message.kind}>{message.text}</span>}
        </div>
      </div>
    </section>
  )
}
