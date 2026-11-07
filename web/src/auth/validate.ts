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

/** Câu báo cho đăng nhập Google theo mã HTTP (backend/auth.py `google`). */
export function googleMessage(status: number): string {
  if (status === 401) return 'Đăng nhập Google không thành công. Vui lòng thử lại.'
  if (status === 403) return 'Email Google của bạn chưa được xác minh, nên chưa dùng được để đăng nhập.'
  if (status === 409) return 'Email này đã gắn với một tài khoản Google khác.'
  if (status === 404) return 'Đăng nhập bằng Google hiện chưa bật.'
  if (status === 422) return 'Thông tin Google gửi về không hợp lệ. Vui lòng thử lại.'
  if (status === 500) return 'Máy chủ gặp lỗi (HTTP 500). Vui lòng thử lại sau.'
  return 'Không kết nối được máy chủ. Vui lòng thử lại.' // 502/504 qua proxy: thường là backend chưa chạy
}
