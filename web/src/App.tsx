import { useEffect, useState } from 'react'
import CaptureView from './components/CaptureView'
import LabelView from './components/LabelView'
import QuickLabel from './components/QuickLabel'
import './App.css'

type Tab = 'capture' | 'label' | 'quick'

// Tab lưu trên URL (#label) để tải lại trang vẫn ở đúng màn; không cần thư viện router.
function tabFromHash(): Tab {
  if (window.location.hash === '#label') return 'label'
  return window.location.hash === '#quick' ? 'quick' : 'capture'
}

export default function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash)
  // Màn Gán nhãn chỉ gắn vào lần đầu mở tab (không tải danh sách hiệp khi chỉ đi quay), sau đó
  // giữ lại khi chuyển tab để không mất nhãn đang sửa dở.
  const [labelOpened, setLabelOpened] = useState(tab === 'label')
  const [quickOpened, setQuickOpened] = useState(tab === 'quick')

  useEffect(() => {
    const onHash = () => {
      const next = tabFromHash()
      setTab(next)
      if (next === 'label') setLabelOpened(true)
      if (next === 'quick') setQuickOpened(true)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <main>
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
      </nav>
      {/* Màn Quay chỉ bị ẩn, không bị gỡ: gỡ ra sẽ mất danh sách hiệp chưa gửi (nằm trong
          state của CaptureView) và tắt camera giữa chừng. */}
      <div hidden={tab !== 'capture'}>
        <h1>Form Coach — quay push-up</h1>
        <p className="hint">
          Đặt điện thoại nằm ngang, sát sàn, nhìn ngang hông; cả người nằm trong khung, chỉ một
          mình bạn.
        </p>
        <CaptureView />
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
    </main>
  )
}
