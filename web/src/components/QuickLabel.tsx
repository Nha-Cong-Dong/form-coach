// Chế độ gán nhãn nhanh (nhãn v2): mỗi lần MỘT rep, hai khung tĩnh (đáy và đỉnh), phím tắt,
// Enter lưu và sang rep kế. Không hiện số đo: chỉ nhìn hình, để nhãn không bị luật dẫn đường.
//
// Nhãn v1 (chỉ một lỗi mỗi rep, lỗi của hiệp) được điền sẵn; việc cần làm là thêm mọi lỗi còn
// thiếu. Mỗi rep được lưu ngay lên server (PUT cả file nhãn của hiệp), nên đóng trang giữa chừng
// không mất gì; tiến độ ("đã duyệt") nhớ trong trình duyệt này để làm tiếp lần sau.
import { useEffect, useRef, useState } from 'react'
import { getReview, listSessions, putLabels } from '../label/api'
import type { RepLabel, ReviewData, SessionSummary } from '../label/api'
import {
  DEFAULT_SINCE,
  buildQueue,
  firstUnreviewed,
  hasPreviousSession,
  keyAction,
  labelsChanged,
  parseStringSet,
  pickFrames,
  reviewedKey,
  toggleError,
  toggleValid,
} from '../label/quick'
import type { KeyAction } from '../label/quick'
import { localIsoString } from '../session/format'
import StickFigure from './StickFigure'

const REVIEWED_KEY = 'formcoach.quicklabel.v2.reviewed'
const SKIPPED_KEY = 'formcoach.quicklabel.v2.skipped'

// Mô tả ngắn từ docs/labeling-criteria.md ("Mô tả bằng lời"), chỉ để nhắc cách hiểu; không có ngưỡng.
const HELP: Record<string, string> = {
  shallow: 'chưa xuống đủ sâu ở đáy',
  incomplete_lockout: 'chưa đẩy lên hết ở đỉnh',
  hip_sag: 'hông võng xuống',
  hip_high: 'hông nhô cao',
  neck_drop: 'cổ gục hoặc rướn, giữ phần lớn rep',
}

const BACKUP_CMD = 'mkdir -p data/v1 && ln -s ../sessions data/v1/sessions && cp -r data/labels data/v1/labels'

type Stage = 'setup' | 'loading' | 'labeling' | 'finished'

function loadSet(key: string): Set<string> {
  try {
    return parseStringSet(window.localStorage.getItem(key))
  } catch {
    return new Set()
  }
}

function saveSet(key: string, set: Set<string>) {
  try {
    window.localStorage.setItem(key, JSON.stringify([...set]))
  } catch {
    // chế độ riêng tư / bị chặn: chỉ mất khả năng làm tiếp, nhãn vẫn đã lưu trên server
  }
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e))

export default function QuickLabel() {
  const [stage, setStage] = useState<Stage>('setup')
  const [since, setSince] = useState(DEFAULT_SINCE)
  const [backupDone, setBackupDone] = useState(false)
  const [queue, setQueue] = useState<SessionSummary[]>([])
  const [qIndex, setQIndex] = useState(0)
  const [data, setData] = useState<ReviewData | null>(null)
  const [labels, setLabels] = useState<RepLabel[]>([])
  const [pos, setPos] = useState(0)
  const [reviewed, setReviewed] = useState<Set<string>>(() => loadSet(REVIEWED_KEY))
  const [skipped, setSkipped] = useState<Set<string>>(() => loadSet(SKIPPED_KEY))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notices, setNotices] = useState<string[]>([])
  const cache = useRef(new Map<string, Promise<ReviewData>>())

  // Tải review (chạy bộ đếm ở server, vài giây); hiệp kế tiếp được tải trước.
  const fetchReview = (id: string): Promise<ReviewData> => {
    let p = cache.current.get(id)
    if (!p) {
      p = getReview(id)
      cache.current.set(id, p)
      p.catch(() => cache.current.delete(id))
    }
    return p
  }

  // Mở hiệp đầu tiên từ vị trí `from` còn rep chưa duyệt; hết hàng đợi thì kết thúc.
  async function openFrom(q: SessionSummary[], from: number, rev: Set<string>, skp: Set<string>) {
    setStage('loading')
    setError('')
    const found: string[] = []
    for (let i = from; i < q.length; i++) {
      const s = q[i]
      if (skp.has(s.session_id)) continue
      let d: ReviewData
      try {
        d = await fetchReview(s.session_id)
      } catch (e) {
        setError(`Không tải được hiệp ${s.session_id} (${message(e)}). Backend đã chạy chưa?`)
        setStage('setup')
        return
      }
      if (d.alignment_problems.length > 0) {
        // Nhãn đã lưu không còn khớp rep hiện tại: server sẽ từ chối lưu, nên bỏ qua và báo.
        found.push(`${s.session_id}: nhãn không khớp rep hiện tại, đã bỏ qua`)
        continue
      }
      const at = firstUnreviewed(d.session_id, d.labels.reps.map((l) => l.rep_index), rev)
      if (at === null) continue // hiệp này đã duyệt hết
      setNotices((n) => [...n, ...found])
      setQIndex(i)
      setData(d)
      setLabels(d.labels.reps)
      setPos(at)
      setStage('labeling')
      if (i + 1 < q.length) fetchReview(q[i + 1].session_id).catch(() => {})
      return
    }
    setNotices((n) => [...n, ...found])
    setStage('finished')
  }

  async function start() {
    setStage('loading')
    setError('')
    let list: SessionSummary[]
    try {
      list = await listSessions()
    } catch (e) {
      setError(`Không lấy được danh sách hiệp (${message(e)}). Backend đã chạy chưa?`)
      setStage('setup')
      return
    }
    const q = buildQueue(list, since)
    setQueue(q)
    setNotices([])
    await openFrom(q, 0, reviewed, skipped)
  }

  function resetProgress() {
    if (!window.confirm('Xoá tiến độ gán nhãn nhanh? Nhãn đã lưu trên server vẫn giữ nguyên.')) return
    const empty = new Set<string>()
    setReviewed(empty)
    setSkipped(empty)
    saveSet(REVIEWED_KEY, empty)
    saveSet(SKIPPED_KEY, empty)
  }

  const label = labels[pos]

  function update(next: RepLabel) {
    setLabels((ls) => ls.map((l, i) => (i === pos ? next : l)))
  }

  // Lưu cả file nhãn của hiệp hiện tại. Xoá bản review lưu tạm của hiệp này: nếu quay lại hiệp
  // sau đó, phải tải nhãn mới từ server chứ không dùng bản cũ (nhãn v1 chưa sửa).
  async function persist(): Promise<boolean> {
    if (!data) return false
    const merged = { ...data.labels, labeled_at: localIsoString(new Date()), reps: labels }
    try {
      await putLabels(merged)
    } catch (e) {
      setError(`Lưu thất bại: ${message(e)}`)
      return false
    }
    cache.current.delete(data.session_id)
    setData({ ...data, labels: merged, labels_saved: true })
    return true
  }

  async function saveAndNext() {
    if (!data || !label || saving) return
    setSaving(true)
    setError('')
    const ok = await persist()
    setSaving(false)
    if (!ok) return
    const rev = new Set(reviewed).add(reviewedKey(data.session_id, label.rep_index))
    setReviewed(rev)
    saveSet(REVIEWED_KEY, rev)
    if (pos + 1 < labels.length) setPos(pos + 1)
    else await openFrom(queue, qIndex + 1, rev, skipped)
  }

  // Đang ở rep đầu của hiệp: quay về rep CUỐI của hiệp trước (bỏ qua hiệp đã "Bỏ qua" hoặc có nhãn
  // lệch rep). Lưu phần sửa dở của rep đang xem trước khi rời; tải lại hiệp trước từ server.
  async function goBackSession() {
    if (!data || saving) return
    if (labelsChanged(data.labels.reps, labels)) {
      setSaving(true)
      const ok = await persist()
      setSaving(false)
      if (!ok) return
    }
    setError('')
    setStage('loading')
    for (let i = qIndex - 1; i >= 0; i--) {
      const s = queue[i]
      if (skipped.has(s.session_id)) continue
      let d: ReviewData
      try {
        d = await fetchReview(s.session_id)
      } catch (e) {
        setError(`Không tải được hiệp ${s.session_id} (${message(e)}).`)
        setStage('labeling')
        return
      }
      if (d.alignment_problems.length > 0) continue
      setQIndex(i)
      setData(d)
      setLabels(d.labels.reps)
      setPos(d.labels.reps.length - 1)
      setStage('labeling')
      return
    }
    setStage('labeling') // không còn hiệp nào phía trước
  }

  function back() {
    if (pos > 0) setPos(pos - 1)
    else void goBackSession()
  }

  function skipSession() {
    if (!data) return
    const skp = new Set(skipped).add(data.session_id)
    setSkipped(skp)
    saveSet(SKIPPED_KEY, skp)
    void openFrom(queue, qIndex + 1, reviewed, skp)
  }

  // Phím tắt dùng bản mới nhất của các hàm trên (gán trong effect, không gán lúc render).
  const actRef = useRef<(a: KeyAction) => void>(() => {})
  useEffect(() => {
    actRef.current = (a) => {
      if (!label) return
      if (a.type === 'toggle') update(toggleError(label, a.error))
      else if (a.type === 'valid') update(toggleValid(label))
      else if (a.type === 'save') void saveAndNext()
      else back()
    }
  })

  const errorLabels = data?.error_labels
  useEffect(() => {
    if (stage !== 'labeling' || !errorLabels) return
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return
      const tag = (e.target as HTMLElement | null)?.tagName
      // Đang gõ ghi chú thì chỉ nhận Enter (lưu); các phím khác là chữ.
      if ((tag === 'INPUT' || tag === 'TEXTAREA') && e.key !== 'Enter') return
      const action = keyAction(e.key, errorLabels)
      if (!action) return
      e.preventDefault()
      actRef.current(action)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [stage, errorLabels])

  // Đang chuyển giữa các hiệp (đã có dữ liệu): chỉ báo đang tải, không hiện lại màn bắt đầu.
  if (stage === 'loading' && data) {
    return (
      <section className="quick">
        <p>Đang tải hiệp… (server chạy bộ đếm, vài giây)</p>
      </section>
    )
  }

  if (stage === 'setup' || stage === 'loading') {
    return (
      <section className="quick">
        <p>
          Gán nhãn lại <b>nhanh</b> cho dataset (nhãn v2): mỗi lần một rep, chỉ nhìn hình, tick{' '}
          <b>mọi</b> lỗi thấy được (không chỉ lỗi của hiệp). Nhãn v1 điền sẵn; bạn thêm những lỗi
          còn thiếu. Mỗi rep được lưu ngay khi bấm Enter.
        </p>
        <ul className="hint">
          <li>Không đọc số đo, không chạy analyze / error_analysis trước khi gán xong.</li>
          <li>Rep nào không chắc: ghi chú. Vùng xám (nông nhẹ, võng nhẹ) mắt người cũng nhiễu.</li>
        </ul>
        <label className="check">
          Từ ngày{' '}
          <input type="date" value={since} onChange={(e) => setSince(e.target.value)} />
        </label>
        <p>
          <label className="check">
            <input
              type="checkbox"
              checked={backupDone}
              onChange={(e) => setBackupDone(e.target.checked)}
            />
            Tôi đã sao lưu nhãn v1 (chạy lệnh dưới ở gốc dự án, một lần duy nhất trước khi gán):
          </label>
        </p>
        <pre>{BACKUP_CMD}</pre>
        <div className="controls">
          <button onClick={start} disabled={!backupDone || stage === 'loading'}>
            {stage === 'loading' ? 'Đang tải… (server chạy bộ đếm)' : reviewed.size ? 'Tiếp tục' : 'Bắt đầu'}
          </button>{' '}
          {reviewed.size > 0 && (
            <>
              <span className="hint">Đã duyệt {reviewed.size} rep (nhớ trong trình duyệt này)</span>{' '}
              <button className="secondary" onClick={resetProgress}>
                Xoá tiến độ
              </button>
            </>
          )}
        </div>
        {error && <p className="error">{error}</p>}
      </section>
    )
  }

  if (stage === 'finished' || !data || !label) {
    return (
      <section className="quick">
        <h2>Xong</h2>
        <p className="ok">Đã duyệt {reviewed.size} rep. Nhãn v2 đã được lưu trên server.</p>
        {notices.length > 0 && (
          <>
            <p className="warn">Hiệp đã bỏ qua:</p>
            <ul>
              {notices.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </>
        )}
        {data && label && (
          <p>
            <button
              className="secondary"
              onClick={() => {
                setPos(labels.length - 1)
                setStage('labeling')
              }}
            >
              ← Quay lại rep cuối
            </button>
          </p>
        )}
        <p className="hint">
          Kiểm tra: <code>python -m evaluation.dataset_report</code>, rồi chấm lại bằng{' '}
          <code>python -m evaluation.baseline</code>. Kết quả v1: dùng <code>--data data/v1</code>.
        </p>
      </section>
    )
  }

  const hasPrev = hasPreviousSession(queue, qIndex, skipped)
  const rep = data.reps[label.rep_index]
  const frames = pickFrames(rep, data.keypoints.length)
  const queueIds = new Set(queue.map((s) => s.session_id))
  const reviewedInQueue = [...reviewed].filter((k) => queueIds.has(k.slice(0, k.lastIndexOf(':')))).length
  const totalReps = queue.reduce((n, s) => n + (s.n_reps ?? 0), 0)

  return (
    <section className="quick">
      <p className="quick-progress">
        Hiệp {qIndex + 1}/{queue.length} · rep {pos + 1}/{labels.length} · đã duyệt {reviewedInQueue}/
        {totalReps} · {data.session_id}
        {data.notes && <> · {data.notes}</>}
      </p>
      <div className="frames">
        <figure>
          <StickFigure
            joints={data.joints}
            points={data.keypoints[frames.bottom]}
            frameSize={data.frame_size}
          />
          <figcaption>Đáy</figcaption>
        </figure>
        <figure>
          <StickFigure
            joints={data.joints}
            points={data.keypoints[frames.top]}
            frameSize={data.frame_size}
          />
          <figcaption>Đỉnh (vừa lên xong)</figcaption>
        </figure>
      </div>
      <div className="quick-buttons">
        {data.error_labels.map((err, i) => (
          <button
            key={err}
            className={`toggle${label.errors.includes(err) ? ' on' : ''}`}
            disabled={!label.valid}
            title={HELP[err]}
            onClick={(e) => {
              update(toggleError(label, err))
              e.currentTarget.blur()
            }}
          >
            <kbd>{i + 1}</kbd>
            {err}
            <small className="help"> · {HELP[err] ?? ''}</small>
          </button>
        ))}
        <button
          className={`toggle invalid${label.valid ? '' : ' on'}`}
          onClick={(e) => {
            update(toggleValid(label))
            e.currentTarget.blur()
          }}
        >
          <kbd>0</kbd>Không phải rep
        </button>
      </div>
      <input
        className="note"
        type="text"
        value={label.note}
        placeholder="ghi chú (tuỳ chọn)"
        onChange={(e) => update({ ...label, note: e.target.value })}
      />
      <div className="controls">
        <button
          className="secondary"
          onClick={back}
          disabled={saving || (pos === 0 && !hasPrev)}
          title="Rep trước; ở rep đầu của hiệp thì về rep cuối của hiệp trước"
        >
          ← Quay lại
        </button>{' '}
        <button onClick={() => void saveAndNext()} disabled={saving}>
          {saving ? 'Đang lưu…' : 'Lưu và rep kế (Enter)'}
        </button>{' '}
        <button className="secondary" onClick={skipSession}>
          Bỏ qua hiệp này
        </button>
        {error && <span className="error"> {error}</span>}
      </div>
      <p className="hint">
        Phím: 1–{data.error_labels.length} bật/tắt lỗi · 0 hoặc X: không phải rep · Enter: lưu và
        sang rep kế · Backspace hoặc ←: quay lại
      </p>
    </section>
  )
}
