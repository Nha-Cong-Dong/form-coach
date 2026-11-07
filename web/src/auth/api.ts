// Gọi API đăng nhập (ARCHITECTURE §4). Phiên đăng nhập là cookie HttpOnly do server đặt:
// JavaScript không đọc được nó, trình duyệt tự gửi kèm mọi request cùng nguồn (kể cả qua proxy
// /api của Vite), nên ở đây không lưu token nào.
import { googleMessage, lockoutMessage } from './validate'

export interface User {
  id: number
  email: string
  is_admin: boolean // email trong FORMCOACH_ADMIN_EMAILS: được dùng công cụ dữ liệu (D0)
}

export type AuthMode = 'login' | 'register'

/** Lỗi đã đổi sang câu cho người dùng; `field` = ô bị sai (hiện dưới ô), không có = lỗi chung. */
export class AuthError extends Error {
  field?: 'email' | 'password'

  constructor(message: string, field?: 'email' | 'password') {
    super(message)
    this.field = field
  }
}

const NETWORK = 'Không kết nối được máy chủ. Vui lòng thử lại.'
const serverError = (status: number) => `Máy chủ gặp lỗi (HTTP ${status}). Vui lòng thử lại sau.`

/** Người đang đăng nhập, hoặc null nếu chưa (401). Lỗi khác (backend tắt...) thì ném. */
export async function fetchMe(): Promise<User | null> {
  const r = await fetch('/api/auth/me')
  if (r.status === 401) return null
  if (!r.ok) throw new Error(r.status === 500 ? serverError(r.status) : NETWORK)
  return r.json()
}

export interface AuthOptions {
  allowRegister: boolean // tạo tài khoản bằng email
  googleClientId: string | null // có thì vẽ nút Google (không phải bí mật)
}

/** Cấu hình màn đăng nhập. Không hỏi được thì coi như tắt cả hai (chỉ hiện đăng nhập email). */
export async function fetchAuthOptions(): Promise<AuthOptions> {
  const off: AuthOptions = { allowRegister: false, googleClientId: null }
  try {
    const r = await fetch('/api/auth/options')
    if (!r.ok) return off
    const body: { allow_register?: unknown; google_client_id?: unknown } = await r.json()
    return {
      allowRegister: body.allow_register === true,
      googleClientId: typeof body.google_client_id === 'string' && body.google_client_id ? body.google_client_id : null,
    }
  } catch {
    return off
  }
}

/** Câu báo theo mã HTTP, không hiện nguyên câu kỹ thuật của server (backend/auth.py). */
function messageFor(mode: AuthMode, status: number, retryAfter: string | null): AuthError {
  if (mode === 'login' && status === 401) return new AuthError('Email hoặc mật khẩu không chính xác.')
  // 429: sai quá nhiều lần, server khoá email này một lúc (backend/auth.py, D0b).
  if (mode === 'login' && status === 429) return new AuthError(lockoutMessage(retryAfter))
  if (mode === 'register' && status === 409) return new AuthError('Email này đã được đăng ký.', 'email')
  if (mode === 'register' && status === 403) return new AuthError('Hiện chưa mở đăng ký tài khoản mới.')
  // 422: web đã kiểm tra email và độ dài mật khẩu trước khi gửi, nên hiếm khi tới đây.
  if (status === 422) return new AuthError('Thông tin chưa hợp lệ. Vui lòng kiểm tra lại.')
  // 500 là lỗi thật ở server; 502/504 qua proxy Vite thường là backend chưa chạy (mất kết nối).
  if (status === 500) return new AuthError(serverError(status))
  return new AuthError(NETWORK)
}

/** Đăng nhập hoặc tạo tài khoản; thành công thì server đặt cookie. Lỗi ném `AuthError`. */
export async function submitCredentials(mode: AuthMode, email: string, password: string): Promise<User> {
  let r: Response
  try {
    r = await fetch(`/api/auth/${mode}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
  } catch {
    throw new AuthError(NETWORK) // mất mạng, server không chạy
  }
  if (r.ok) return r.json()
  throw messageFor(mode, r.status, r.headers.get('Retry-After'))
}

/** Gửi ID token của nút Google; server kiểm tra rồi đặt cookie. Lỗi ném `AuthError`. */
export async function submitGoogle(credential: string): Promise<User> {
  let r: Response
  try {
    r = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    })
  } catch {
    throw new AuthError(NETWORK)
  }
  if (r.ok) return r.json()
  throw new AuthError(googleMessage(r.status))
}

/** Đăng xuất; lỗi (mất mạng, server lỗi) thì ném để web không báo đã đăng xuất khi chưa chắc. */
export async function logout(): Promise<void> {
  let r: Response
  try {
    r = await fetch('/api/auth/logout', { method: 'POST' })
  } catch {
    throw new Error('Không đăng xuất được: mất kết nối tới máy chủ. Vui lòng thử lại.')
  }
  if (!r.ok) throw new Error(`Không đăng xuất được: máy chủ gặp lỗi (HTTP ${r.status}). Vui lòng thử lại.`)
}
