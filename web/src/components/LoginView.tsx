// Màn đăng nhập / tạo tài khoản, theo canvas "Đăng nhập" (DESIGN.md). Điện thoại: một cột;
// máy tính (rộng ≥ 900px): thêm tấm giới thiệu nền tối bên trái.
import { useState } from 'react'
import type { FormEvent } from 'react'
import { AuthError, submitCredentials } from '../auth/api'
import type { AuthMode, User } from '../auth/api'
import { MIN_PASSWORD_LENGTH, hasErrors, validateCredentials } from '../auth/validate'
import type { FieldErrors } from '../auth/validate'
import ThemeToggle from './ThemeToggle'

interface Props {
  allowRegister: boolean // server tắt đăng ký (GET /api/auth/options) thì chỉ có đăng nhập
  onLoggedIn: (user: User) => void
  // Phiên hết hạn giữa chừng: vẽ đè lên app (các màn bên dưới vẫn giữ nguyên), kèm lời giải thích.
  overlay?: boolean
}

export default function LoginView({ allowRegister, onLoggedIn, overlay = false }: Props) {
  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  // Lỗi từng ô chỉ hiện sau lần bấm gửi đầu tiên, rồi cập nhật theo từng phím gõ.
  const [submitted, setSubmitted] = useState(false)
  const [serverField, setServerField] = useState<FieldErrors>({}) // vd email đã có tài khoản
  const [formError, setFormError] = useState<string | null>(null)

  const fieldErrors: FieldErrors = submitted
    ? { ...validateCredentials(mode, email, password, confirm), ...serverField }
    : {}

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitted(true)
    setServerField({})
    setFormError(null)
    // Ô "Nhập lại mật khẩu": chưa có "quên mật khẩu" (cần gửi email), gõ nhầm lúc tạo tài
    // khoản là bị khoá ngoài. Chỉ kiểm tra ở web, server không cần biết ô này.
    if (hasErrors(validateCredentials(mode, email, password, confirm))) return
    setBusy(true)
    try {
      onLoggedIn(await submitCredentials(mode, email, password))
    } catch (err) {
      if (err instanceof AuthError && err.field) setServerField({ [err.field]: err.message })
      else setFormError(err instanceof Error ? err.message : String(err))
      setBusy(false)
    }
  }

  const switchMode = (next: AuthMode) => {
    setMode(next)
    setSubmitted(false)
    setServerField({})
    setFormError(null)
  }

  // Thuộc tính cho ô có lỗi: viền đỏ (CSS theo aria-invalid) và trình đọc màn hình đọc lỗi.
  const invalid = (name: keyof FieldErrors) =>
    fieldErrors[name]
      ? { 'aria-invalid': true as const, 'aria-describedby': `login-${name}-error` }
      : {}
  const fieldError = (name: keyof FieldErrors) =>
    fieldErrors[name] && (
      <span id={`login-${name}-error`} className="field-error">
        {fieldErrors[name]}
      </span>
    )

  return (
    <div
      className={overlay ? 'login overlay' : 'login'}
      {...(overlay && { role: 'dialog', 'aria-modal': true, 'aria-labelledby': 'login-expired' })}
    >
      <header className="login-top">
        <span className="login-brand">
          <span className="login-logo small" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="5,19 12,6 19,19" />
              <path d="M9 12.8A4 4 0 0 0 15 12.8" />
            </svg>
          </span>
          Form Coach
        </span>
        <ThemeToggle />
      </header>

      <div className="login-body">
        {/* Người que ở đáy push-up, góc khuỷu 90°: nhìn là hiểu app đo gì (góc khớp từng rep). */}
        <section className="login-hero">
          <h2>Biết rep nào sai, sửa ngay hiệp sau.</h2>
          <svg viewBox="16 104 290 72" className="login-figure" role="img" aria-label="Người que ở đáy push-up, góc khuỷu 90 độ">
            <line x1="20" y1="166" x2="300" y2="166" strokeWidth="2" strokeDasharray="4 6" opacity="0.35" style={{ stroke: 'var(--color-skeleton-joint)' }} />
            <g fill="none" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" style={{ stroke: 'var(--color-skeleton-bone)' }}>
              <circle cx="50" cy="124" r="12" />
              <polyline points="60,131 73,138 170,146 225,153 285,159" />
              <polyline points="73,138 100,138 100,165" />
            </g>
            <path d="M 86 138 A 14 14 0 0 0 100 152" fill="none" strokeWidth="2" style={{ stroke: 'var(--color-skeleton-joint)' }} />
            <text x="62" y="160" style={{ fill: 'var(--color-skeleton-joint)', fontSize: 'var(--text-label)', fontWeight: 600 }}>
              90°
            </text>
            <g style={{ fill: 'var(--color-skeleton-joint)' }}>
              {[[73, 138], [100, 138], [100, 165], [170, 146], [225, 153], [285, 159]].map(([cx, cy]) => (
                <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="5" />
              ))}
            </g>
          </svg>
          <p className="login-hero-caption">Camera bắt khớp, app đo góc khuỷu và độ thẳng thân ở từng rep.</p>
        </section>

        <div className="login-column">
          <div className="login-intro">
            <span className="login-logo" aria-hidden="true">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="5,19 12,6 19,19" />
                <path d="M9 12.8A4 4 0 0 0 15 12.8" />
              </svg>
            </span>
            <h1>Form Coach</h1>
            <p>Biết rep nào sai, sửa ngay hiệp sau.</p>
          </div>

          {/* noValidate: tắt bong bóng báo lỗi của trình duyệt (mỗi trình duyệt một kiểu), tự
              báo dưới từng ô theo DESIGN.md. */}
          <form className="login-card" onSubmit={submit} noValidate>
            {overlay && (
              <p id="login-expired" className="form-notice">
                Phiên đăng nhập đã hết hạn. Đăng nhập lại để tiếp tục, những gì bạn đang làm vẫn được
                giữ nguyên.
              </p>
            )}
            {allowRegister ? (
              <div className="segmented" role="group" aria-label="Chọn đăng nhập hoặc tạo tài khoản">
                <button type="button" aria-pressed={mode === 'login'} onClick={() => switchMode('login')}>
                  Đăng nhập
                </button>
                <button type="button" aria-pressed={mode === 'register'} onClick={() => switchMode('register')}>
                  Tạo tài khoản
                </button>
              </div>
            ) : (
              <h2 className="login-card-title">Đăng nhập</h2>
            )}

            {formError && (
              <div className="form-alert" role="alert">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 7.5v5.5M12 16.5h.01" />
                </svg>
                {formError}
              </div>
            )}

            <div className="field">
              <label htmlFor="login-email">Email</label>
              {/* Tắt tự viết hoa / tự sửa của bàn phím điện thoại; server vẫn so email không
                  phân biệt hoa thường. */}
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                placeholder="ban@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  setServerField({})
                }}
                {...invalid('email')}
              />
              {fieldError('email')}
            </div>

            <div className="field">
              <label htmlFor="login-password">Mật khẩu</label>
              <div className="password">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  placeholder="Mật khẩu"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  {...invalid('password')}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword((v) => !v)}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
                    <circle cx="12" cy="12" r="3" />
                    {showPassword && <path d="M3 3l18 18" />}
                  </svg>
                </button>
              </div>
              {fieldError('password') ||
                (mode === 'register' && <span className="field-hint">Ít nhất {MIN_PASSWORD_LENGTH} ký tự.</span>)}
            </div>

            {mode === 'register' && (
              <div className="field">
                <label htmlFor="login-confirm">Nhập lại mật khẩu</label>
                {/* Theo nút hiện/ẩn của ô Mật khẩu ở trên. */}
                <input
                  id="login-confirm"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Nhập lại mật khẩu"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  {...invalid('confirm')}
                />
                {fieldError('confirm')}
              </div>
            )}

            <button type="submit" className="primary" disabled={busy}>
              {busy ? 'Đang gửi…' : mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}
            </button>
          </form>

          <p className="login-privacy">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="4" y="11" width="16" height="10" rx="2" />
              <path d="M8 11V7a4 4 0 0 1 8 0v4" />
            </svg>
            Video không rời khỏi máy bạn. Chỉ toạ độ các khớp được gửi lên server.
          </p>
        </div>
      </div>
    </div>
  )
}
