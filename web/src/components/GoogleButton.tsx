// Nút "Tiếp tục với Google" (G2). Nút do Google vẽ (iframe, logo và chữ theo quy định của Google):
// chỉ chọn được kiểu sáng/tối, hình dạng, độ rộng, không tô theo token của DESIGN.md.
// Bấm → Google mở popup chọn tài khoản → trả ID token → `onCredential` (gửi lên server kiểm tra).
import { useEffect, useRef, useState } from 'react'
import { loadGoogleId } from '../auth/google'
import { currentTheme, onSystemThemeChange } from '../theme'

interface Props {
  clientId: string
  onCredential: (credential: string) => void
}

const MAX_WIDTH = 400 // giới hạn của Google

export default function GoogleButton({ clientId, onCredential }: Props) {
  const boxRef = useRef<HTMLDivElement>(null)
  const callbackRef = useRef(onCredential)
  const [failed, setFailed] = useState(false)
  const [theme, setThemeState] = useState(currentTheme)

  useEffect(() => {
    callbackRef.current = onCredential
  })

  // Đổi sáng/tối (nút mặt trăng, hoặc máy đổi) → vẽ lại nút cho hợp nền.
  useEffect(() => {
    const update = () => setThemeState(currentTheme())
    const observer = new MutationObserver(update)
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const stop = onSystemThemeChange(update)
    return () => {
      observer.disconnect()
      stop()
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    loadGoogleId()
      .then((id) => {
        const box = boxRef.current
        if (cancelled || !box) return
        id.initialize({
          client_id: clientId,
          callback: (response) => callbackRef.current(response.credential),
          context: 'signin',
        })
        box.replaceChildren()
        id.renderButton(box, {
          type: 'standard',
          theme: theme === 'dark' ? 'filled_black' : 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          logo_alignment: 'center',
          width: String(Math.min(MAX_WIDTH, Math.floor(box.clientWidth))),
          locale: 'vi',
        })
        setFailed(false)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [clientId, theme])

  return (
    <>
      <div ref={boxRef} className="google-button" />
      {failed && (
        <p className="field-hint">Không tải được nút Google (mạng hoặc trình chặn quảng cáo). Bạn vẫn đăng nhập bằng email được.</p>
      )}
    </>
  )
}
