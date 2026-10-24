// Chế độ Quay dữ liệu (công cụ thu dataset, không thuộc app cuối): chọn tập lỗi cố ý của hiệp →
// Bắt đầu → tập → Xong → gửi file JSON (§2b) về server. Không có logic ML: chỉ ghi keypoint từng
// khung và gửi đi; server kiểm tra và lưu. Gửi và danh sách "chưa gửi": session/upload.ts.
import { useEffect, useRef, useState } from 'react'
import { MEDIAPIPE_VERSION, MODEL_NAME } from '../pose/landmarker'
import { FrameRecorder, buildSession, toKeypoints } from '../session/format'
import { useSessionUpload } from '../session/upload'
import CameraPose from './CameraPose'
import type { PoseFrame } from './CameraPose'
import UnsentList from './UnsentList'

const EXERCISE = 'pushup'

export default function CaptureView() {
  const [errorLabels, setErrorLabels] = useState<string[] | null>(null)
  const [labelsError, setLabelsError] = useState('')
  const [setErrors, setSetErrors] = useState<string[]>([])
  // Ghi chú điều kiện quay (D4). Giữ nguyên sau mỗi hiệp: cả buổi thường cùng điều kiện.
  const [notes, setNotes] = useState('')
  const [cameraOn, setCameraOn] = useState(false)
  // Khung camera đang DỌC (cao > rộng). Không cho ghi: người nằm ngang ngoài đời sẽ thành
  // dựng đứng trong hình, độ nghiêng thân bị lật 90° và bộ đếm không đếm được rep nào
  // (đã gặp ngày 2026-10-19 khi điện thoại khoá xoay màn hình).
  const [portrait, setPortrait] = useState(false)
  const [recording, setRecording] = useState(false)
  const [counts, setCounts] = useState({ frames: 0, seen: 0 })
  const { upload, uploading, message, setMessage, unsent, savedCount } = useSessionUpload()

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

  function handleFrame(f: PoseFrame) {
    frameSizeRef.current = [f.width, f.height]
    const isPortrait = f.height > f.width
    setPortrait((cur) => (cur === isPortrait ? cur : isPortrait)) // chỉ vẽ lại khi đổi chiều
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
      notes,
      captureMode: 'dataset',
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
        <label className="notes-field">
          Ghi chú buổi quay (tuỳ chọn, giữ cho các hiệp sau)
          <input
            type="text"
            value={notes}
            maxLength={1000}
            disabled={recording}
            placeholder="vd: tối, đèn trần, áo đen, cổ tay đau"
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>

        <div className="controls">
          {!recording ? (
            <button onClick={start} disabled={!cameraOn || !errorLabels || portrait}>
              Bắt đầu
            </button>
          ) : (
            <button className="stop" onClick={finish}>
              Xong
            </button>
          )}
        </div>

        {!cameraOn && <p className="hint">Bật camera trước, rồi mới bấm Bắt đầu.</p>}
        {cameraOn && portrait && (
          <p className="error">
            Khung hình đang DỌC nên chưa cho quay. Tắt khoá xoay màn hình, xoay điện thoại nằm
            ngang cho trang web xoay theo, rồi tắt và bật lại camera.
          </p>
        )}
        {recording && (
          <p>
            Đang ghi: {counts.frames} khung ({counts.seen} có người)
          </p>
        )}
        {uploading > 0 && <p>Đang gửi…</p>}
        {message && <p className={message.kind}>{message.text}</p>}

        <UnsentList unsent={unsent} uploading={uploading} onRetry={upload} />
      </section>
    </div>
  )
}
