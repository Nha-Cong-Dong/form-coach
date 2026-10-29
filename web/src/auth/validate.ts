// Kiểm tra form đăng nhập / tạo tài khoản trên web, trước khi gửi (hàm thuần, có test:
// web/scripts/check-auth-validate.ts). Server vẫn kiểm tra lại; đây là để báo lỗi ngay dưới ô.

export const MIN_PASSWORD_LENGTH = 8 // khớp backend/auth.py

export interface FieldErrors {
  email?: string
  password?: string
  confirm?: string
}

// Như server (_check_email): một @, hai bên không rỗng, tên miền có dấu chấm ở giữa, không khoảng trắng.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@.]+$/

export function validateCredentials(
  mode: 'login' | 'register',
  email: string,
  password: string,
  confirm: string,
): FieldErrors {
  const errors: FieldErrors = {}
  if (!email) errors.email = 'Vui lòng nhập email.'
  else if (!EMAIL_RE.test(email)) errors.email = 'Email không hợp lệ.'

  if (!password) errors.password = 'Vui lòng nhập mật khẩu.'
  else if (mode === 'register' && password.length < MIN_PASSWORD_LENGTH)
    errors.password = `Mật khẩu phải có ít nhất ${MIN_PASSWORD_LENGTH} ký tự.`

  if (mode === 'register') {
    if (!confirm) errors.confirm = 'Vui lòng nhập lại mật khẩu.'
    else if (confirm !== password) errors.confirm = 'Mật khẩu nhập lại không khớp.'
  }
  return errors
}

export const hasErrors = (errors: FieldErrors): boolean => Object.keys(errors).length > 0

/** Câu báo khi server khoá đăng nhập (429). `retryAfter` = header Retry-After (giây), làm tròn
 *  lên theo phút; thiếu hoặc lạ thì không nói số phút. */
export function lockoutMessage(retryAfter: string | null): string {
  const seconds = Number(retryAfter)
  if (!retryAfter || !Number.isFinite(seconds) || seconds <= 0)
    return 'Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau ít phút.'
  return `Bạn đã nhập sai quá nhiều lần. Vui lòng thử lại sau ${Math.ceil(seconds / 60)} phút.`
}
