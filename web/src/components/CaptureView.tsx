// Bước 9b(ii): chọn tập lỗi của hiệp → Bắt đầu → tập → Xong → gửi file JSON (§2b) về server.
// Không có logic ML: chỉ ghi keypoint từng khung và gửi đi; server kiểm tra và lưu.
//
// Một hiệp đã tập thì không quay lại được, nên hiệp gửi thất bại KHÔNG bao giờ bị bỏ âm thầm:
// nó nằm trong danh sách "chờ gửi" (kể cả khi quay hiệp mới) cho tới khi gửi được hoặc tải về.
import { useEffect, useRef, useState } from 'react'
import { MEDIAPIPE_VERSION, MODEL_NAME } from '../pose/landmarker'
import { FrameRecorder, buildSession, toKeypoints } from '../session/format'
import type { SessionFile } from '../session/format'
import CameraPose from './CameraPose'
import type { PoseFrame } from './CameraPose'

const EXERCISE = 'pushup'

interface UploadResult {
  session_id: string
  n_frames: number
  duration_s: number
  fps: number
  frames_with_person: number
}

interface Unsent {
  session: SessionFile
  error: string
}

/** Tải file JSON xuống máy: dự phòng khi gửi server thất bại (chép tay vào data/sessions/). */
function downloadJson(session: SessionFile) {
  const blob = new Blob([JSON.stringify(session)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${session.session_id}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export default function CaptureView() {
  const [errorLabels, setErrorLabels] = useState<string[] | null>(null)
  const [labelsError, setLabelsError] = useState('')
  const [setErrors, setSetErrors] = useState<string[]>([])
  const [cameraOn, setCameraOn] = useState(false)
  const [recording, setRecording] = useState(false)
  const [uploading, setUploading] = useState(0) // số hiệp đang gửi
  const [counts, setCounts] = useState({ frames: 0, seen: 0 })
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [unsent, setUnsent] = useState<Unsent[]>([])
  const [savedCount, setSavedCount] = useState(0) // số hiệp đã lưu trong lần mở trang này

  // Dữ liệu ghi từng khung để trong ref, không phải state: 30 khung/giây mà mỗi khung
  // một lần vẽ lại React là lãng phí. Chỉ số đếm hiển thị mới cập nhật (thưa) qua state.
  const recorderRef = useRef<FrameRecorder | null>(null)
  const recordingRef = useRef(false)
  const startedAtRef = useRef<Date | null>(null)
  const frameSizeRef = useRef<[number, number]>([0, 0])
  const lastCountUpdate = useRef(0)

  // Lấy danh sách lỗi hợp lệ từ server (không tự chép trong web/).
  useEffect(() => {
    fetch(`/api/exercises/${EXERCISE}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const body: { error_labels: string[] } = await r.json()
        setErrorLabels(body.error_labels)
      })
      .catch((e) => setLabelsError(`Không lấy được danh sách lỗi từ server (${e}). Backend đã chạy chưa?`))
  }, [])

  // Còn hiệp chưa gửi mà đóng / tải lại trang → trình duyệt hỏi lại trước khi mất dữ liệu.
  useEffect(() => {
    if (unsent.length === 0) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [unsent.length])

  function handleFrame(f: PoseFrame) {
    frameSizeRef.current = [f.width, f.height]
    const recorder = recorderRef.current
    if (!recordingRef.current || !recorder) return
    recorder.add(f.ts, toKeypoints(f.landmarks))
    if (f.ts - lastCountUpdate.current > 250) {
      lastCountUpdate.current = f.ts
      setCounts({ frames: recorder.count, seen: recorder.seenCount })
    }
  }

  function start() {
    recorderRef.current = new FrameRecorder()
    startedAtRef.current = new Date()
    setCounts({ frames: 0, seen: 0 })
    setMessage(null)
    recordingRef.current = true
    setRecording(true)
  }

  function markUnsent(session: SessionFile, error: string) {
    setUnsent((list) => [
      ...list.filter((u) => u.session.session_id !== session.session_id),
      { session, error },
    ])
  }

  async function upload(session: SessionFile) {
    setUploading((n) => n + 1)
    try {
      const r = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(session),
      })
      const body = await r.json().catch(() => ({}))
      if (r.status === 409) {
        // Đã có trên server (vd lần gửi trước thành công nhưng mất phản hồi): coi như đã lưu.
        setMessage({ kind: 'ok', text: `${session.session_id} đã có trên server từ trước.` })
      } else if (!r.ok) {
        throw new Error(`HTTP ${r.status}: ${body.detail ?? 'lỗi không rõ'}`)
      } else {
        const res = body as UploadResult
        setSavedCount((n) => n + 1)
        setMessage({
          kind: 'ok',
          text:
            `Đã lưu ${res.session_id}: ${res.n_frames} khung, ${res.duration_s} s, ` +
            `${res.fps} fps, ${res.frames_with_person} khung có người.`,
        })
      }
      setUnsent((list) => list.filter((u) => u.session.session_id !== session.session_id))
    } catch (e) {
      const error = e instanceof Error ? e.message : String(e)
      markUnsent(session, error)
      setMessage({ kind: 'error', text: `Chưa lưu được ${session.session_id}: ${error}` })
    } finally {
      setUploading((n) => n - 1)
    }
  }

  function finish() {
    recordingRef.current = false
    setRecording(false)
    const frames = recorderRef.current?.take() ?? []
    recorderRef.current = null
    setCounts({ frames: frames.length, seen: frames.filter((f) => f.kp !== null).length })
    if (frames.length < 2) {
      setMessage({ kind: 'error', text: 'Chưa ghi được khung nào. Camera đã chạy chưa?' })
      return
    }
    const session = buildSession({
      exercise: EXERCISE,
      setErrors,
      startedAt: startedAtRef.current!,
      frameSize: frameSizeRef.current,
      frames,
      source: { version: MEDIAPIPE_VERSION, model: MODEL_NAME },
    })
    upload(session)
  }

  function toggleError(label: string) {
    setSetErrors((cur) => (cur.includes(label) ? cur.filter((x) => x !== label) : [...cur, label]))
  }

  return (
    <div className="capture">
      <CameraPose
        onFrame={handleFrame}
        onRunningChange={(running) => {
          setCameraOn(running)
          if (!running && recordingRef.current) {
            // Tắt camera giữa chừng: bỏ hiệp đang ghi (chưa bấm Xong thì chưa thành hiệp).
            recordingRef.current = false
            recorderRef.current = null
            setRecording(false)
            setMessage({ kind: 'error', text: 'Camera tắt giữa chừng, đã bỏ hiệp đang ghi.' })
          }
        }}
      />

      <section className="panel">
        <h2>Hiệp quay {savedCount > 0 && <small>(đã lưu {savedCount} hiệp)</small>}</h2>
        {labelsError && <p className="error">{labelsError}</p>}
        {errorLabels && (
          <fieldset disabled={recording}>
            <legend>Lỗi cố ý trong hiệp này (để trống = tập đúng)</legend>
            {errorLabels.map((label) => (
              <label key={label} className="check">
                <input type="checkbox" checked={setErrors.includes(label)} onChange={() => toggleError(label)} />
                {label}
              </label>
            ))}
          </fieldset>
        )}

        <div className="controls">
          {!recording ? (
            <button onClick={start} disabled={!cameraOn || !errorLabels}>
              Bắt đầu
            </button>
          ) : (
            <button className="stop" onClick={finish}>
              Xong
            </button>
          )}
        </div>

        {!cameraOn && <p className="hint">Bật camera trước, rồi mới bấm Bắt đầu.</p>}
        {recording && (
          <p>
            Đang ghi: {counts.frames} khung ({counts.seen} có người)
          </p>
        )}
        {uploading > 0 && <p>Đang gửi…</p>}
        {message && <p className={message.kind}>{message.text}</p>}

        {unsent.length > 0 && (
          <div className="unsent">
            <h3>Chưa gửi được ({unsent.length}) — đừng đóng trang</h3>
            <ul>
              {unsent.map(({ session, error }) => (
                <li key={session.session_id}>
                  <b>{session.session_id}</b> ({session.frames.length} khung): {error}{' '}
                  <button onClick={() => upload(session)} disabled={uploading > 0}>
                    Gửi lại
                  </button>{' '}
                  <button onClick={() => downloadJson(session)}>Tải JSON</button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
