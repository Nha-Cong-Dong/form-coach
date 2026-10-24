// Gán lại MÙ để đo độ nhất quán của chính người gán (evaluation/relabel_consistency.py).
// Mở bằng link do lệnh `sample` in ra (#audit/...). Cố ý KHÔNG hiện: nhãn đã lưu, mã hiệp, ghi
// chú, lỗi cố ý của hiệp, số đo. Không ghi gì vào file nhãn: xong thì chép chuỗi đáp án.
import { useEffect, useRef, useState } from 'react'
import { getReview } from '../label/api'
import type { ReviewData } from '../label/api'
import { answersString, emptyAnswer, parseSavedAnswers } from '../label/audit'
import type { AuditAnswer, AuditItem } from '../label/audit'
import { keyAction, pickFrames } from '../label/quick'
import type { KeyAction } from '../label/quick'
import StickFigure from './StickFigure'

// Như màn Gán nhanh: mô tả bằng lời, không có ngưỡng.
const HELP: Record<string, string> = {
  shallow: 'chưa xuống đủ sâu ở đáy',
  incomplete_lockout: 'chưa đẩy lên hết ở đỉnh',
  hip_sag: 'hông võng xuống',
  hip_high: 'hông nhô cao',
  neck_drop: 'cổ gục hoặc rướn, giữ phần lớn rep',
}

interface Props {
  items: AuditItem[]
  storageKey: string // theo mẫu: tải lại trang thì làm tiếp
}

function loadAnswers(key: string, n: number): AuditAnswer[] {
  try {
    return parseSavedAnswers(window.localStorage.getItem(key), n) ?? Array.from({ length: n }, emptyAnswer)
  } catch {
    return Array.from({ length: n }, emptyAnswer)
  }
}

export default function AuditLabel({ items, storageKey }: Props) {
  const [answers, setAnswers] = useState<AuditAnswer[]>(() => loadAnswers(storageKey, items.length))
  const [pos, setPos] = useState(0)
  const [done, setDone] = useState(false)
  // Dữ liệu đã tải kèm mã hiệp; rep đang xem thuộc hiệp khác thì coi như đang tải.
  const [loaded, setLoaded] = useState<{ id: string; data: ReviewData } | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const cache = useRef(new Map<string, Promise<ReviewData>>())

  const fetchReview = (id: string) => {
    let p = cache.current.get(id)
    if (!p) {
      p = getReview(id)
      cache.current.set(id, p)
      p.catch(() => cache.current.delete(id))
    }
    return p
  }

  const item = items[pos]
  const data = loaded?.id === item.sessionId ? loaded.data : null
  useEffect(() => {
    if (done) return
    let cancelled = false
    fetchReview(item.sessionId)
      .then((d) => !cancelled && setLoaded({ id: item.sessionId, data: d }))
      .catch((e: Error) => !cancelled && setError(`Không tải được rep (${e.message}).`))
    // Tải trước rep kế.
    const next = items[pos + 1]
    if (next) fetchReview(next.sessionId).catch(() => {})
    return () => {
      cancelled = true
    }
  }, [item, items, pos, done])

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(answers))
    } catch {
      // không lưu được tiến độ: vẫn gán được, chỉ mất khả năng làm tiếp sau khi tải lại
    }
  }, [answers, storageKey])

  const answer = answers[pos]
  const update = (next: AuditAnswer) => setAnswers((list) => list.map((a, i) => (i === pos ? next : a)))
  const toggle = (err: string) =>
    answer.valid &&
    update({
      ...answer,
      errors: answer.errors.includes(err) ? answer.errors.filter((e) => e !== err) : [...answer.errors, err],
    })
  const next = () => (pos + 1 < items.length ? setPos(pos + 1) : setDone(true))
  const back = () => pos > 0 && setPos(pos - 1)
  // Xoá mọi đáp án của mẫu này, về rep 1 (mẫu giữ nguyên; nhãn đã lưu không bị đụng tới).
  const restart = () => {
    if (!window.confirm('Xoá mọi đáp án đã gán trong lần kiểm tra này và làm lại từ rep 1?')) return
    setAnswers(Array.from({ length: items.length }, emptyAnswer))
    setPos(0)
    setDone(false)
  }

  const errorLabels = data?.error_labels
  const actRef = useRef<(a: KeyAction) => void>(() => {})
  useEffect(() => {
    actRef.current = (a) => {
      if (a.type === 'toggle') toggle(a.error)
      else if (a.type === 'valid') update({ valid: !answer.valid, errors: [] })
      else if (a.type === 'save') next()
      else back()
    }
  })
  useEffect(() => {
    if (done || !errorLabels) return
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return
      const action = keyAction(e.key, errorLabels)
      if (!action) return
      e.preventDefault()
      actRef.current(action)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [done, errorLabels])

  if (done && errorLabels) {
    const text = answersString(answers, errorLabels)
    const cmd = `python -m evaluation.relabel_consistency score --answers "${text}"`
    return (
      <section className="quick">
        <h2>Xong {items.length} rep</h2>
        <p>Chạy lệnh này ở gốc dự án để tính độ nhất quán:</p>
        <pre>{cmd}</pre>
        <div className="controls">
          <button
            onClick={() => {
              navigator.clipboard?.writeText(cmd).then(() => setCopied(true), () => setCopied(false))
            }}
          >
            {copied ? 'Đã chép' : 'Chép lệnh'}
          </button>{' '}
          <button className="secondary" onClick={() => setDone(false)}>
            ← Xem lại
          </button>{' '}
          <button className="secondary" onClick={restart}>
            Làm lại từ đầu
          </button>
        </div>
        <p className="hint">Nhãn đã lưu không bị đổi. Mẫu này chỉ dùng để đo, không sửa nhãn theo kết quả.</p>
      </section>
    )
  }

  const rep = data?.reps[item.repIndex]
  const frames = rep && data ? pickFrames(rep, data.keypoints.length) : null

  return (
    <section className="quick">
      <p className="quick-progress">
        Gán lại mù · rep {pos + 1}/{items.length} · chỉ nhìn hình, không có nhãn cũ
      </p>
      {error && <p className="error">{error}</p>}
      {!data || !frames ? (
        <p>Đang tải rep… (server chạy bộ đếm, vài giây)</p>
      ) : (
        <>
          <div className="frames">
            <figure>
              <StickFigure joints={data.joints} points={data.keypoints[frames.bottom]} frameSize={data.frame_size} />
              <figcaption>Đáy</figcaption>
            </figure>
            <figure>
              <StickFigure joints={data.joints} points={data.keypoints[frames.top]} frameSize={data.frame_size} />
              <figcaption>Đỉnh (vừa lên xong)</figcaption>
            </figure>
          </div>
          <div className="quick-buttons">
            {data.error_labels.map((err, i) => (
              <button
                key={err}
                className={`toggle${answer.errors.includes(err) ? ' on' : ''}`}
                disabled={!answer.valid}
                onClick={(e) => {
                  toggle(err)
                  e.currentTarget.blur()
                }}
              >
                <kbd>{i + 1}</kbd>
                {err}
                <small className="help"> · {HELP[err] ?? ''}</small>
              </button>
            ))}
            <button
              className={`toggle invalid${answer.valid ? '' : ' on'}`}
              onClick={(e) => {
                update({ valid: !answer.valid, errors: [] })
                e.currentTarget.blur()
              }}
            >
              <kbd>0</kbd>Không phải rep
            </button>
          </div>
          <div className="controls">
            <button className="secondary" onClick={back} disabled={pos === 0}>
              ← Quay lại
            </button>{' '}
            <button onClick={next}>{pos + 1 < items.length ? 'Rep kế (Enter)' : 'Xong (Enter)'}</button>{' '}
            <button className="secondary" onClick={restart}>
              Làm lại từ đầu
            </button>
          </div>
          <p className="hint">
            Phím: 1–{data.error_labels.length} bật/tắt lỗi · 0 hoặc X: không phải rep · Enter: rep kế ·
            Backspace hoặc ←: quay lại
          </p>
        </>
      )}
    </section>
  )
}
