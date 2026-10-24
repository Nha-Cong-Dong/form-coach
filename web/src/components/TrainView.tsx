// Chế độ Tập theo canvas "3 · Tập": Chuẩn bị (máy dọc, chờ xoay ngang) → Sẵn sàng (camera, đã
// thấy toàn thân chưa) → đếm ngược 5 s → Đang ghi → Xong: gửi hiệp, sang trang kết quả.
// Lúc ghi: số rep trực tiếp từ server qua WebSocket /api/live (OnlineRepCounter, chỉ để hiển
// thị); không kết nối được thì vẫn ghi và hiện đồng hồ. Kết quả từng rep luôn từ phân tích cả
// hiệp sau khi gửi. Không có logic ML ở đây.
import { useEffect, useRef, useState } from 'react'
import { MEDIAPIPE_VERSION, MODEL_NAME } from '../pose/landmarker'
import { formatDuration } from '../results/format'
import { FrameRecorder, buildSession, toKeypoints } from '../session/format'
import { useSessionUpload } from '../session/upload'
import { FULL_BODY_RATIO, RollingRatio, bodyVisible } from '../train/body'
import { FpsMeter, MAX_SEND_FPS, SendThrottle, encodeFrame, liveUrl, parseServerMessage } from '../train/live'
import CameraPose from './CameraPose'
import type { PoseFrame } from './CameraPose'
import UnsentList from './UnsentList'

const EXERCISE = 'pushup'
const COUNTDOWN_S = 5 // bạn chọn 5 s (canvas ghi 3 s) để kịp đặt máy và vào tư thế

type Stage = 'prep' | 'ready' | 'countdown' | 'recording'
// off: chưa ghi · connecting: đang mở kết nối · live: đã nhận số từ server · failed: không được
type LiveStatus = 'off' | 'connecting' | 'live' | 'failed'

const landscapeQuery = () => window.matchMedia('(orientation: landscape)')

export default function TrainView() {
  const [landscape, setLandscape] = useState(() => landscapeQuery().matches)
  // Luôn mở ở Chuẩn bị: không tự bật camera ngay khi mở app (vd laptop vốn đã nằm ngang).
  const [stage, setStage] = useState<Stage>('prep')
  const [cameraOn, setCameraOn] = useState(false)
  const [framePortrait, setFramePortrait] = useState(false)
  const [fullBody, setFullBody] = useState(false)
  const [countdown, setCountdown] = useState(COUNTDOWN_S)
  const [elapsed, setElapsed] = useState({ s: 0, seen: 0 })
  const [live, setLive] = useState<{ status: LiveStatus; reps: number | null }>({ status: 'off', reps: null })
  const { upload, uploading, message, setMessage, unsent } = useSessionUpload()
  const wsRef = useRef<WebSocket | null>(null)
  const fpsRef = useRef(new FpsMeter()) // đo từ lúc Sẵn sàng: khi bắt đầu ghi đã có fps thật
  const throttleRef = useRef(new SendThrottle())

  const recorderRef = useRef<FrameRecorder | null>(null)
  const startedAtRef = useRef<{ date: Date; perf: number } | null>(null)
  const frameSizeRef = useRef<[number, number]>([0, 0])
  const ratioRef = useRef(new RollingRatio(30)) // ~1 s ở 30 fps
  const lastUpdate = useRef(0)

  // Theo dõi hướng màn hình: xoay ngang ở màn Chuẩn bị → tự sang Sẵn sàng; xoay dọc lại khi
  // đang Sẵn sàng → về Chuẩn bị (camera tắt). Đang đếm ngược / đang ghi thì không đổi màn.
  // Chỉ tự chuyển khi máy VỪA xoay (sự kiện đổi hướng), không phải khi đã nằm ngang từ trước.
  useEffect(() => {
    const q = landscapeQuery()
    const onChange = () => {
      setLandscape(q.matches)
      setStage((s) => (s === 'prep' && q.matches ? 'ready' : s === 'ready' && !q.matches ? 'prep' : s))
    }
    q.addEventListener('change', onChange)
    return () => q.removeEventListener('change', onChange)
  }, [])

  // Đếm ngược rồi bắt đầu ghi.
  useEffect(() => {
    if (stage !== 'countdown') return
    const timer = window.setTimeout(() => {
      if (countdown > 1) {
        setCountdown(countdown - 1)
        return
      }
      recorderRef.current = new FrameRecorder()
      startedAtRef.current = { date: new Date(), perf: performance.now() }
      setElapsed({ s: 0, seen: 0 })
      setStage('recording')
    }, 1000)
    return () => window.clearTimeout(timer)
  }, [stage, countdown])

  // Rời màn Tập giữa chừng (gỡ component): đóng kết nối.
  useEffect(() => () => closeLive(), [])

  /** Mở WebSocket đếm trực tiếp. Lỗi ở đây không chặn việc ghi hiệp (ghi nằm ở trình duyệt). */
  function openLive() {
    closeLive()
    throttleRef.current = new SendThrottle()
    setLive({ status: 'connecting', reps: null })
    let ws: WebSocket
    try {
      ws = new WebSocket(liveUrl(window.location))
    } catch {
      setLive({ status: 'failed', reps: null })
      return
    }
    wsRef.current = ws
    ws.onopen = () => {
      // fps thật (camera điện thoại thường 13–30): server đổi ngưỡng giây → số khung theo nó.
      const fps = Math.min(fpsRef.current.fps ?? MAX_SEND_FPS, MAX_SEND_FPS)
      ws.send(JSON.stringify({ type: 'start', exercise: EXERCISE, fps, frame_size: frameSizeRef.current }))
    }
    ws.onmessage = (e) => {
      const msg = parseServerMessage(String(e.data))
      if (msg?.type === 'count') setLive({ status: 'live', reps: msg.n_reps })
    }
    // Rớt hoặc bị từ chối (vd chưa đăng nhập: uvicorn trả 403) → quay về hiện đồng hồ.
    ws.onclose = () => {
      if (wsRef.current === ws) setLive((cur) => ({ ...cur, status: 'failed' }))
    }
  }

  /** Báo server kết thúc (nếu còn mở) rồi đóng. Không chờ "final": kết quả lấy từ cả hiệp. */
  function closeLive() {
    const ws = wsRef.current
    wsRef.current = null
    if (!ws) return
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'stop' }))
    ws.close()
  }

  function handleFrame(f: PoseFrame) {
    frameSizeRef.current = [f.width, f.height]
    const portraitNow = f.height > f.width
    setFramePortrait((cur) => (cur === portraitNow ? cur : portraitNow))
    const ok = ratioRef.current.push(bodyVisible(f.landmarks)) >= FULL_BODY_RATIO
    setFullBody((cur) => (cur === ok ? cur : ok))
    fpsRef.current.push(f.ts)
    const recorder = recorderRef.current
    if (!recorder) return
    recorder.add(f.ts, toKeypoints(f.landmarks))
    const ws = wsRef.current
    if (ws?.readyState === WebSocket.OPEN && throttleRef.current.shouldSend(f.ts)) {
      ws.send(encodeFrame(f.ts, f.landmarks))
    }
    if (f.ts - lastUpdate.current > 250) {
      lastUpdate.current = f.ts
      const s = (performance.now() - (startedAtRef.current?.perf ?? 0)) / 1000
      setElapsed({ s, seen: recorder.seenCount })
    }
  }

  function startCountdown() {
    setMessage(null)
    setCountdown(COUNTDOWN_S)
    setStage('countdown')
    // Mở kết nối ngay từ đếm ngược: 5 s đủ để xong, vào ghi là có số. Khung chỉ gửi khi đang ghi
    // (handleFrame), nên lúc đang vào tư thế không bị đếm.
    openLive()
  }

  function cancel() {
    if (stage === 'recording' && !window.confirm('Huỷ hiệp đang ghi?')) return
    recorderRef.current = null
    closeLive()
    setLive({ status: 'off', reps: null })
    setStage('prep') // tắt camera; máy vẫn ngang thì bấm Tiếp tục để quay lại
  }

  function finish() {
    const frames = recorderRef.current?.take() ?? []
    recorderRef.current = null
    closeLive()
    setLive({ status: 'off', reps: null })
    // Về Chuẩn bị: camera tắt (CameraPose gỡ ra) trong lúc xem kết quả.
    setStage('prep')
    if (frames.length < 2) {
      setMessage({ kind: 'error', text: 'Chưa ghi được khung nào. Camera đã chạy chưa?' })
      return
    }
    upload(
      buildSession({
        exercise: EXERCISE,
        setErrors: [],
        notes: '',
        captureMode: 'train', // không có kịch bản lỗi: đánh giá mặc định bỏ qua (evaluation/split.py)
        startedAt: startedAtRef.current!.date,
        frameSize: frameSizeRef.current,
        frames,
        source: { version: MEDIAPIPE_VERSION, model: MODEL_NAME },
      }),
    )
  }

  if (stage === 'prep') {
    return (
      <div className="train-prep">
        <header className="result-head">
          <h1>Chuẩn bị tập</h1>
          <span>Push-up · 3 bước, khoảng một phút</span>
        </header>

        {uploading > 0 && <p className="form-notice">Đang gửi hiệp vừa tập…</p>}
        {message?.kind === 'error' && (
          <div className="form-alert" role="alert">
            {message.text}
          </div>
        )}
        <UnsentList unsent={unsent} uploading={uploading} onRetry={upload} />

        <section className="card">
          <svg width="100%" viewBox="0 0 310 172" role="img" aria-label="Nhìn từ trên xuống: điện thoại nằm ngang đặt sát sàn ở cạnh người tập, ngang hông, hướng vào thân người" style={{ display: 'block' }}>
            <polygon points="155,132 52,22 258,22" fillOpacity="0.12" strokeWidth="1.5" strokeDasharray="4 4" style={{ fill: 'var(--color-accent)', stroke: 'var(--color-accent)' }} />
            <rect x="62" y="34" width="170" height="30" rx="15" fill="none" strokeWidth="2.5" style={{ stroke: 'var(--color-ink)' }} />
            <circle cx="250" cy="49" r="13" fill="none" strokeWidth="2.5" style={{ stroke: 'var(--color-ink)' }} />
            <line x1="108" y1="64" x2="108" y2="78" strokeWidth="2.5" strokeLinecap="round" style={{ stroke: 'var(--color-ink)' }} />
            <rect x="123" y="132" width="64" height="28" rx="6" style={{ fill: 'var(--color-ink)' }} />
            <circle cx="177" cy="146" r="4" style={{ fill: 'var(--color-card)' }} />
          </svg>
          <div className="prep-caption">
            <span>Nhìn từ trên xuống</span>
            <span>Máy ngang hông, hướng vào thân người</span>
          </div>
        </section>

        <section className="card">
          <ol className="steps">
            <li>
              <b>Đặt máy ngang, sát sàn</b>
              <span>Ngang hông, chỉ một mình bạn trong khung.</span>
            </li>
            <li>
              <b>Tắt khoá xoay màn hình</b>
              <span>Nếu khoá xoay đang bật, màn hình sẽ không chuyển sang ngang.</span>
            </li>
            <li>
              <b>Vào tư thế</b>
              <span>Cả người nằm trong khung, đủ sáng, quần áo ôm.</span>
            </li>
          </ol>
        </section>

        <div className="prep-wait">
          {landscape ? (
            // Máy đã nằm ngang sẵn (laptop, hoặc đã xoay trước khi mở): bấm để bật camera.
            <button type="button" className="primary" onClick={() => setStage('ready')}>
              Tiếp tục
            </button>
          ) : (
            <>
              <span className="chip" role="status">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <rect x="2" y="7" width="20" height="10" rx="2" />
                  <path d="M6 4.5A7 7 0 0 1 12 2" />
                </svg>
                Đang chờ máy xoay ngang
              </span>
              <span className="caption">Màn hình sẽ tự chuyển khi máy ở hướng ngang.</span>
            </>
          )}
        </div>
      </div>
    )
  }

  // Sẵn sàng / đếm ngược / đang ghi: phủ toàn màn hình, nền tối cố định (DESIGN.md: stage).
  const canStart = cameraOn && !framePortrait
  return (
    <div className="train-stage">
      <div className="train-camera">
        <CameraPose compact autoStart onFrame={handleFrame} onRunningChange={setCameraOn} />
        {stage === 'countdown' && (
          <div className="countdown" aria-live="assertive">
            {countdown > 0 ? countdown : ''}
          </div>
        )}
      </div>

      <aside className="train-panel">
        <div className="train-panel-top">
          {stage === 'recording' ? (
            <span className="pill live">
              <i aria-hidden="true" />
              Đang ghi
            </span>
          ) : (
            <span className="pill">Push-up</span>
          )}
          <button type="button" className="icon-button" aria-label="Huỷ" onClick={cancel}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        {stage === 'ready' && (
          <>
            <h1>Sẵn sàng</h1>
            <p className="muted">Đặt máy ngang, thấp, sát sàn, quay từ bên hông. Cả người nằm trong khung.</p>
            <p className={fullBody ? 'body-check ok' : 'body-check'} role="status">
              {fullBody ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
              ) : null}
              {!cameraOn ? 'Đang bật camera…' : fullBody ? 'Đã thấy toàn thân' : 'Chưa thấy toàn thân: lùi máy ra xa hơn'}
            </p>
            {framePortrait && <p className="body-check">Khung hình đang dọc: tắt khoá xoay rồi quay lại màn này.</p>}
            <div className="train-actions">
              <button type="button" className="primary" onClick={startCountdown} disabled={!canStart}>
                Bắt đầu
              </button>
              <span className="muted caption">Đếm ngược {COUNTDOWN_S} giây để vào tư thế.</span>
            </div>
          </>
        )}

        {stage === 'countdown' && (
          <>
            <h1>Vào tư thế</h1>
            <p className="muted">Bắt đầu ghi sau {countdown} giây.</p>
          </>
        )}

        {stage === 'recording' && (
          <>
            {live.status === 'live' && live.reps !== null ? (
              <>
                {/* aria-live: trình đọc màn hình đọc số mới khi tăng. */}
                <span className="counter" role="status" aria-live="polite" aria-label={`${live.reps} rep`}>
                  {live.reps}
                </span>
                <span className="counter-unit">rep</span>
                <span className="muted">
                  {formatDuration(elapsed.s)} · {elapsed.seen} khung có người
                </span>
              </>
            ) : (
              <>
                <span className="counter" role="timer" aria-label={`Đã tập ${Math.round(elapsed.s)} giây`}>
                  {formatDuration(elapsed.s)}
                </span>
                <span className="muted">
                  {live.status === 'failed'
                    ? 'Không đếm trực tiếp được; số rep sẽ có ở trang kết quả.'
                    : 'Đang kết nối bộ đếm…'}
                </span>
              </>
            )}
            <div className="train-actions">
              <button type="button" className="finish" onClick={finish}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <rect x="4" y="4" width="16" height="16" rx="3" />
                </svg>
                Xong
              </button>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}
