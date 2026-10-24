// Danh sách hiệp chưa gửi được: gửi lại hoặc tải JSON về máy (dùng chung Tập / Quay dữ liệu).
import { downloadJson } from '../session/upload'
import type { Unsent } from '../session/upload'
import type { SessionFile } from '../session/format'

interface Props {
  unsent: Unsent[]
  uploading: number
  onRetry: (session: SessionFile) => void
}

export default function UnsentList({ unsent, uploading, onRetry }: Props) {
  if (unsent.length === 0) return null
  return (
    <div className="unsent">
      <h3>Chưa gửi được ({unsent.length}) — đừng đóng trang</h3>
      <ul>
        {unsent.map(({ session, error }) => (
          <li key={session.session_id}>
            <b>{session.session_id}</b> ({session.frames.length} khung): {error}{' '}
            <button onClick={() => onRetry(session)} disabled={uploading > 0}>
              Gửi lại
            </button>{' '}
            <button onClick={() => downloadJson(session)}>Tải JSON</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
