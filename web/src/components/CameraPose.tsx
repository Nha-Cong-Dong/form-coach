// Bước 9b(i): bật camera, chạy MediaPipe JS trên từng khung mới, vẽ khung xương lên video.
// Hiện fps đo được và visibility khuỷu hai bên để kiểm tra pose có ổn trên điện thoại không.
import { DrawingUtils, PoseLandmarker } from '@mediapipe/tasks-vision'
import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'
import { createPoseLandmarker } from '../pose/landmarker'
import type { Delegate } from '../pose/landmarker'
import { cssVar } from '../theme'

const LEFT_ELBOW = 13 // theo thứ tự 33 khớp MediaPipe (formcoach/pose/joints.py)
const RIGHT_ELBOW = 14

type Status = 'idle' | 'loading' | 'running' | 'error'

interface Stats {
  fps: number
  visLeft: number | null // visibility TB khuỷu trái trong ~1 s gần nhất; null = không thấy người
  visRight: number | null
  personRatio: number // tỉ lệ khung có người trong ~1 s gần nhất
}

/** Cách nhận khung mới: requestVideoFrameCallback (đúng nhịp camera) hoặc rAF (dự phòng). */
type LoopKind = 'rVFC' | 'rAF'

/** 'user' = camera trước (tự quay, nhìn được màn hình); 'environment' = camera sau (nét hơn). */
type Facing = 'user' | 'environment'
const FACING_LABEL: Record<Facing, string> = { user: 'trước', environment: 'sau' }

function mean(xs: number[]): number | null {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null
}

/** Kết quả của một khung camera, báo ra ngoài để ghi hiệp (bước 9b(ii)). */
export interface PoseFrame {
  ts: number // ms, cùng mốc với performance.now(), tăng ngặt
  landmarks: NormalizedLandmark[] | undefined // undefined = không thấy người
  width: number // kích thước khung video (pixel)
  height: number
}

interface Props {
  onFrame?: (frame: PoseFrame) => void
  onRunningChange?: (running: boolean) => void
}

export default function CameraPose({ onFrame, onRunningChange }: Props) {
  // Giữ callback mới nhất trong ref: effect camera không phải chạy lại (tắt/bật camera)
  // mỗi khi component cha vẽ lại và truyền vào một hàm mới.
  const onFrameRef = useRef(onFrame)
  const onRunningChangeRef = useRef(onRunningChange)
  useEffect(() => {
    onFrameRef.current = onFrame
    onRunningChangeRef.current = onRunningChange
  })

  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [active, setActive] = useState(false) // người dùng muốn bật camera
  const [facing, setFacing] = useState<Facing>('user')
  const [actualFacing, setActualFacing] = useState<string>('') // camera trình duyệt thật sự đưa
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState('')
  const [delegate, setDelegate] = useState<Delegate | null>(null)
  const [loopKind, setLoopKind] = useState<LoopKind | null>(null)
  const [size, setSize] = useState<{ w: number; h: number } | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)

  // Chạy khi active bật; hàm return ở cuối chạy khi active tắt (hoặc rời trang) để dọn dẹp.
  useEffect(() => {
    if (!active) return
    const video = videoRef.current!
    const canvas = canvasRef.current!
    let cancelled = false
    let stream: MediaStream | null = null
    let landmarker: PoseLandmarker | null = null
    let frameHandle = 0
    let usingRVFC = false

    async function start() {
      try {
        if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
          throw new Error('Trình duyệt chỉ cho dùng camera trên trang https hoặc localhost.')
        }
        // "ideal": xin camera trước/sau theo lựa chọn; máy không có (laptop) thì trình duyệt tự chọn webcam.
        stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 720 } },
        })
        setActualFacing(stream.getVideoTracks()[0]?.getSettings().facingMode ?? 'không rõ')
        const loaded = await createPoseLandmarker()
        if (cancelled) {
          loaded.landmarker.close()
          return
        }
        landmarker = loaded.landmarker
        setDelegate(loaded.delegate)

        video.srcObject = stream
        await video.play()
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        setSize({ w: video.videoWidth, h: video.videoHeight })
        const ctx = canvas.getContext('2d')!
        const drawer = new DrawingUtils(ctx)

        // Thống kê trên cửa sổ trượt ~1 s.
        const window1s: { t: number; left: number | null; right: number | null }[] = []
        let lastTs = -1
        let lastVideoTime = -1
        let lastStatsUpdate = 0
        // Màu khung xương đọc một lần (không đổi theo sáng/tối), không đọc lại mỗi khung hình.
        const bone = cssVar('color-skeleton-bone')
        const joint = cssVar('color-skeleton-joint')

        const onFrame = () => {
          if (cancelled || !landmarker) return
          // rAF có thể gọi nhiều lần cho cùng một khung camera: bỏ khung trùng.
          if (video.currentTime !== lastVideoTime) {
            lastVideoTime = video.currentTime
            // VIDEO mode bắt buộc timestamp (ms) tăng ngặt.
            const ts = Math.max(performance.now(), lastTs + 1)
            lastTs = ts
            const result = landmarker.detectForVideo(video, ts)
            const pose: NormalizedLandmark[] | undefined = result.landmarks[0]

            onFrameRef.current?.({ ts, landmarks: pose, width: video.videoWidth, height: video.videoHeight })

            ctx.clearRect(0, 0, canvas.width, canvas.height)
            if (pose) {
              drawer.drawConnectors(pose, PoseLandmarker.POSE_CONNECTIONS, { color: bone, lineWidth: 3 })
              drawer.drawLandmarks(pose, { color: joint, radius: 4 })
            }

            window1s.push({
              t: ts,
              left: pose ? pose[LEFT_ELBOW].visibility : null,
              right: pose ? pose[RIGHT_ELBOW].visibility : null,
            })
            while (window1s.length && ts - window1s[0].t > 1000) window1s.shift()
            if (ts - lastStatsUpdate > 500) {
              lastStatsUpdate = ts
              const seen = window1s.filter((f) => f.left !== null)
              setStats({
                fps: window1s.length > 1 ? (1000 * (window1s.length - 1)) / (ts - window1s[0].t) : 0,
                visLeft: mean(seen.map((f) => f.left!)),
                visRight: mean(seen.map((f) => f.right!)),
                personRatio: window1s.length ? seen.length / window1s.length : 0,
              })
            }
          }
          frameHandle = usingRVFC ? video.requestVideoFrameCallback(onFrame) : requestAnimationFrame(onFrame)
        }

        usingRVFC = 'requestVideoFrameCallback' in HTMLVideoElement.prototype
        setLoopKind(usingRVFC ? 'rVFC' : 'rAF')
        frameHandle = usingRVFC ? video.requestVideoFrameCallback(onFrame) : requestAnimationFrame(onFrame)
        setStatus('running')
        onRunningChangeRef.current?.(true)
      } catch (err) {
        if (cancelled) return
        setError(err instanceof Error ? `${err.name}: ${err.message}` : String(err))
        setStatus('error')
        setActive(false)
      }
    }

    start()
    // Dọn dẹp khi rời trang hoặc bấm Tắt: dừng vòng lặp, tắt camera, giải phóng model.
    return () => {
      cancelled = true
      if (usingRVFC) video.cancelVideoFrameCallback(frameHandle)
      else cancelAnimationFrame(frameHandle)
      stream?.getTracks().forEach((t) => t.stop())
      landmarker?.close()
      setStatus((s) => (s === 'error' ? s : 'idle'))
      onRunningChangeRef.current?.(false)
    }
  }, [active, facing]) // đổi camera khi đang bật → dọn dẹp rồi mở lại với camera mới

  const portrait = size !== null && size.h > size.w
  // Camera trước: lật NGANG phần hiển thị (cả video lẫn khung xương) cho giống soi gương như app
  // camera. Chỉ là CSS: MediaPipe vẫn chạy trên ảnh gốc, keypoint gửi đi không bị lật.
  const mirrored = actualFacing === 'user'
  const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(2))

  return (
    <div className="camera-pose">
      <div className={mirrored ? 'stage mirrored' : 'stage'}>
        <video ref={videoRef} playsInline muted />
        <canvas ref={canvasRef} />
      </div>

      <div className="controls">
        {!active ? (
          <button
            onClick={() => {
              setError('')
              setStatus('loading')
              setActive(true)
            }}
          >
            Bật camera
          </button>
        ) : (
          <button onClick={() => setActive(false)} disabled={status === 'loading'}>
            {status === 'loading' ? 'Đang tải model…' : 'Tắt camera'}
          </button>
        )}{' '}
        <button
          className="secondary"
          onClick={() => setFacing((f) => (f === 'user' ? 'environment' : 'user'))}
          disabled={status === 'loading'}
        >
          Dùng camera {FACING_LABEL[facing === 'user' ? 'environment' : 'user']}
        </button>
      </div>

      {error && <p className="error">{error}</p>}
      {portrait && <p className="warn">Đang quay DỌC. Xoay ngang điện thoại để thấy hết thân khi hít đất.</p>}

      {status === 'running' && (
        <table className="stats">
          <tbody>
            <tr><th>Camera</th><td>chọn: {FACING_LABEL[facing]} / thực tế: {actualFacing}</td></tr>
            <tr><th>Độ phân giải</th><td>{size ? `${size.w}×${size.h}` : '—'}</td></tr>
            <tr><th>fps xử lý</th><td>{stats ? stats.fps.toFixed(1) : '—'}</td></tr>
            <tr><th>Khung có người</th><td>{stats ? `${Math.round(stats.personRatio * 100)}%` : '—'}</td></tr>
            <tr><th>Visibility khuỷu trái / phải</th><td>{stats ? `${fmt(stats.visLeft)} / ${fmt(stats.visRight)}` : '—'}</td></tr>
            <tr><th>Chạy trên / nhận khung bằng</th><td>{delegate} / {loopKind}</td></tr>
          </tbody>
        </table>
      )}
    </div>
  )
}
