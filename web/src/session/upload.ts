// Gửi hiệp lên server, dùng chung cho chế độ Tập và Quay dữ liệu.
//
// Một hiệp đã tập thì không quay lại được, nên hiệp gửi thất bại KHÔNG bao giờ bị bỏ âm thầm:
// nó nằm trong danh sách "chờ gửi" (kể cả khi quay hiệp mới) cho tới khi gửi được hoặc tải về.
import { useEffect, useState } from 'react'
import { failure } from '../http'
import { resultHash } from '../results/api'
import type { SessionFile } from './format'

export interface UploadResult {
  session_id: string
  n_frames: number
  duration_s: number
  fps: number
  frames_with_person: number
}

export interface Unsent {
  session: SessionFile
  error: string
}

export type UploadMessage = { kind: 'ok' | 'error'; text: string }

/** Tải file JSON xuống máy: dự phòng khi gửi server thất bại (chép tay vào data/sessions/). */
export function downloadJson(session: SessionFile) {
  const blob = new Blob([JSON.stringify(session)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${session.session_id}.json`
  a.click()
  URL.revokeObjectURL(url)
}

/** Gửi hiệp; thành công thì chuyển sang trang kết quả (`#result/...`). */
export function useSessionUpload() {
  const [uploading, setUploading] = useState(0) // số hiệp đang gửi
  const [message, setMessage] = useState<UploadMessage | null>(null)
  const [unsent, setUnsent] = useState<Unsent[]>([])
  const [savedCount, setSavedCount] = useState(0) // số hiệp đã lưu trong lần mở trang này

  // Còn hiệp chưa gửi mà đóng / tải lại trang → trình duyệt hỏi lại trước khi mất dữ liệu.
  useEffect(() => {
    if (unsent.length === 0) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [unsent.length])

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
      if (r.status === 409) {
        // Đã có trên server (vd lần gửi trước thành công nhưng mất phản hồi): coi như đã lưu.
        setMessage({ kind: 'ok', text: `${session.session_id} đã có trên server từ trước.` })
      } else if (!r.ok) {
        throw await failure(r) // đọc `detail` chung với các màn khác (http.ts)
      } else {
        const res = (await r.json()) as UploadResult
        setSavedCount((n) => n + 1)
        setMessage({
          kind: 'ok',
          text:
            `Đã lưu ${res.session_id}: ${res.n_frames} khung, ${res.duration_s} s, ` +
            `${res.fps} fps, ${res.frames_with_person} khung có người.`,
        })
        // Sang trang kết quả. Màn Quay chỉ bị ẩn (App), danh sách chưa gửi giữ nguyên;
        // "Hiệp tiếp theo" quay lại đây.
        window.location.hash = resultHash(session.exercise, res.session_id)
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

  return { upload, uploading, message, setMessage, unsent, savedCount }
}
