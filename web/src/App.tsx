import { useEffect, useState } from 'react'
import { fetchAllowRegister, fetchMe, logout } from './auth/api'
import type { User } from './auth/api'
import AuditLabel from './components/AuditLabel'
import CaptureView from './components/CaptureView'
import { parseAuditHash } from './label/audit'
import LabelView from './components/LabelView'
import LoginView from './components/LoginView'
import QuickLabel from './components/QuickLabel'
import ResultView from './components/ResultView'
import ThemeToggle from './components/ThemeToggle'
import TrainView from './components/TrainView'
import { UNAUTHORIZED_EVENT } from './http'
import './App.css'

type Tab = 'capture' | 'label' | 'quick' | 'result' | 'audit'

// Tab lưu trên URL (#label) để tải lại trang vẫn ở đúng màn; không cần thư viện router.
function tabFromHash(): Tab {
  if (window.location.hash.startsWith('#result/')) return 'result'
  // Gán lại mù: chỉ mở bằng link do `python -m evaluation.relabel_consistency sample` in ra.
  if (window.location.hash.startsWith('#audit/')) return 'audit'
  if (window.location.hash === '#label') return 'label'
  return window.location.hash === '#quick' ? 'quick' : 'capture'
}

/** `#result/<exercise>/<session_id>` → hai phần, hoặc null nếu hash không đúng dạng. */
function resultFromHash(): { exercise: string; sessionId: string } | null {
  const m = window.location.hash.match(/^#result\/([^/]+)\/(.+)$/)
  return m ? { exercise: m[1], sessionId: decodeURIComponent(m[2]) } : null
}

/** Màn gán lại mù: đọc danh sách rep từ hash; link sai thì báo. */
function AuditRoute() {
  const hash = window.location.hash
  const items = parseAuditHash(hash)
  if (!items) return <p className="error">Link kiểm tra không hợp lệ. Chạy lại lệnh sample và mở link nó in ra.</p>
  return <AuditLabel key={hash} items={items} storageKey={`formcoach.audit.${hash}`} />
}

export default function App() {
  // undefined = đang hỏi server, null = chưa đăng nhập.
  const [user, setUser] = useState<User | null | undefined>(undefined)
  const [signOutError, setSignOutError] = useState<string | null>(null)
  const [allowRegister, setAllowRegister] = useState(false)
  // Phiên hết hạn giữa chừng (một API trả 401): hiện màn đăng nhập ĐÈ LÊN, giữ nguyên các màn
  // bên dưới để không mất hiệp chưa gửi (nằm trong state của CaptureView).
  const [sessionExpired, setSessionExpired] = useState(false)
  const [tab, setTab] = useState<Tab>(tabFromHash)
  const [resultTarget, setResultTarget] = useState(resultFromHash)
  const [captureMode, setCaptureMode] = useState<'train' | 'data'>('train')
  // Màn Gán nhãn chỉ gắn vào lần đầu mở tab (không tải danh sách hiệp khi chỉ đi quay), sau đó
  // giữ lại khi chuyển tab để không mất nhãn đang sửa dở.
  const [labelOpened, setLabelOpened] = useState(tab === 'label')
  const [quickOpened, setQuickOpened] = useState(tab === 'quick')

  useEffect(() => {
    const onHash = () => {
      const next = tabFromHash()
      setTab(next)
      setResultTarget(resultFromHash())
      if (next === 'label') setLabelOpened(true)
      if (next === 'quick') setQuickOpened(true)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    // Hỏi cả hai trước khi vẽ, để nút "Tạo tài khoản" không hiện ra rồi biến mất.
    // Không hỏi được server: vẫn hiện màn đăng nhập; lỗi kết nối hiện trong form khi bấm gửi
    // (không giữ một dòng báo lỗi cũ, dễ mâu thuẫn khi server chạy lại).
    const me = fetchMe().catch(() => null)
    Promise.all([fetchAllowRegister(), me]).then(([allowed, u]) => {
      setAllowRegister(allowed)
      setUser(u)
    })
  }, [])

  useEffect(() => {
    const onUnauthorized = () => setSessionExpired(true)
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  // Cổng đăng nhập: chưa biết thì không vẽ gì (tránh nháy màn đăng nhập khi đã đăng nhập),
  // chưa đăng nhập thì chỉ có màn đăng nhập. Mọi màn bên dưới đều cần cookie phiên.
  if (user === undefined) return null
  if (user === null) {
    return <LoginView allowRegister={allowRegister} onLoggedIn={setUser} />
  }

  const signOut = async () => {
    // Đăng xuất gỡ màn Quay: hiệp chưa gửi được (giữ trong bộ nhớ trang) sẽ mất.
    if (!window.confirm('Đăng xuất? Hiệp chưa gửi được (nếu có) sẽ mất.')) return
    setSignOutError(null)
    try {
      await logout()
      setUser(null)
    } catch (e) {
      // Chưa chắc server đã xoá phiên: ở lại, báo để bấm lại.
      setSignOutError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <>
    {sessionExpired && (
      <LoginView
        overlay
        allowRegister={false}
        onLoggedIn={(u) => {
          setUser(u)
          setSessionExpired(false)
        }}
      />
    )}
    <main inert={sessionExpired}>
      <nav className="tabs">
        <a href="#capture" className={tab === 'capture' ? 'active' : ''}>
          Quay
        </a>
        <a href="#label" className={tab === 'label' ? 'active' : ''}>
          Gán nhãn
        </a>
        <a href="#quick" className={tab === 'quick' ? 'active' : ''}>
          Gán nhanh
        </a>
        <ThemeToggle />
        <button type="button" className="text-button" onClick={signOut} title={user.email}>
          Đăng xuất
        </button>
      </nav>
      {signOutError && (
        <div className="form-alert" role="alert">
          {signOutError}
        </div>
      )}
      {/* Màn Quay chỉ bị ẩn, không bị gỡ: gỡ ra sẽ mất danh sách hiệp chưa gửi (nằm trong
          state của CaptureView) và tắt camera giữa chừng. */}
      <div hidden={tab !== 'capture'}>
        {/* Tập (app) và Quay dữ liệu (công cụ thu dataset) như canvas. Cả hai luôn gắn, chỉ ẩn
            cái không chọn: đổi chế độ không làm mất hiệp chưa gửi của chế độ kia. */}
        <div className="segmented capture-mode" role="group" aria-label="Chế độ">
          <button type="button" aria-pressed={captureMode === 'train'} onClick={() => setCaptureMode('train')}>
            Tập
          </button>
          <button type="button" aria-pressed={captureMode === 'data'} onClick={() => setCaptureMode('data')}>
            Quay dữ liệu
          </button>
        </div>
        <div hidden={captureMode !== 'train'}>
          <TrainView />
        </div>
        <div hidden={captureMode !== 'data'}>
          <h1>Form Coach — quay dữ liệu push-up</h1>
          <p className="hint">
            Đặt điện thoại nằm ngang, sát sàn, nhìn ngang hông; cả người nằm trong khung, chỉ một
            mình bạn.
          </p>
          <CaptureView />
        </div>
      </div>
      {labelOpened && (
        <div hidden={tab !== 'label'}>
          <h1>Form Coach — gán nhãn rep</h1>
          <LabelView />
        </div>
      )}
      {quickOpened && (
        <div hidden={tab !== 'quick'}>
          <h1>Form Coach — gán nhãn nhanh (v2)</h1>
          <QuickLabel />
        </div>
      )}
      {tab === 'audit' && <AuditRoute />}
      {/* Trang kết quả gắn theo hiệp (key): đổi hiệp thì tải lại từ đầu. */}
      {tab === 'result' && resultTarget && (
        <ResultView
          key={`${resultTarget.exercise}/${resultTarget.sessionId}`}
          exercise={resultTarget.exercise}
          sessionId={resultTarget.sessionId}
        />
      )}
    </main>
    </>
  )
}
