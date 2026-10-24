// Bước 3a: danh sách hiệp đã quay (mới nhất trước), chọn một hiệp để gán nhãn.
import { useCallback, useEffect, useState } from 'react'
import { listSessions } from '../label/api'
import type { SessionSummary } from '../label/api'

interface Props {
  onSelect: (sessionId: string) => void
}

/** "2026-10-20T10:14:01+07:00" → "2026-10-20 10:14:01". Cắt chuỗi, không đổi múi giờ:
 *  giờ ghi trong file đã là giờ máy lúc quay. */
function formatRecordedAt(iso: string | undefined): string {
  return iso ? iso.slice(0, 19).replace('T', ' ') : '?'
}

export default function SessionList({ onSelect }: Props) {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true) // lần mở đầu tiên tải ngay

  // Chỉ cập nhật state khi server trả lời (không gọi setState ngay trong effect).
  const fetchList = useCallback(() => {
    listSessions()
      .then((list) => {
        setSessions(list)
        setError('')
      })
      .catch((e) => setError(`Không lấy được danh sách hiệp (${e.message}). Backend đã chạy chưa?`))
      .finally(() => setLoading(false))
  }, [])

  useEffect(fetchList, [fetchList])

  const reload = () => {
    setLoading(true)
    fetchList()
  }

  return (
    <section className="session-list">
      <div className="controls">
        <button className="secondary" onClick={reload} disabled={loading}>
          {loading ? 'Đang tải…' : 'Tải lại'}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {sessions && sessions.length === 0 && <p>Chưa có hiệp nào trong data/sessions/.</p>}
      {sessions && sessions.length > 0 && (
        <table className="sessions">
          <thead>
            <tr>
              <th>Quay lúc</th>
              <th>Lỗi cố ý</th>
              <th>Dài</th>
              <th>Rep</th>
              <th>Nhãn rep</th>
              <th>Ghi chú</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) =>
              s.error ? (
                <tr key={s.session_id} className="broken">
                  <td>{s.session_id}</td>
                  <td colSpan={5} className="error">
                    File hỏng: {s.error}
                  </td>
                </tr>
              ) : (
                <tr key={s.session_id} className="pick" onClick={() => onSelect(s.session_id)}>
                  <td>{formatRecordedAt(s.recorded_at)}</td>
                  <td>
                    {s.capture_mode === 'train'
                      ? 'chế độ Tập (không kịch bản)'
                      : s.set_errors?.length
                        ? s.set_errors.join(', ')
                        : 'không (tập đúng)'}
                  </td>
                  <td>{s.duration_s} s</td>
                  <td>{s.n_reps}</td>
                  <td>
                    {s.labeled ? (
                      <span className="ok">đã gán</span>
                    ) : s.n_reps === 0 ? (
                      <span className="hint">không có rep</span>
                    ) : (
                      'chưa'
                    )}
                  </td>
                  <td className="notes-cell">{s.notes}</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}
