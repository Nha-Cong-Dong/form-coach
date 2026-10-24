// Gọi API đăng nhập (ARCHITECTURE §4). Phiên đăng nhập là cookie HttpOnly do server đặt:
// JavaScript không đọc được nó, trình duyệt tự gửi kèm mọi request cùng nguồn (kể cả qua proxy
// /api của Vite), nên ở đây không lưu token nào.

export interface User {
  id: number
  email: string
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

/** Server có cho tạo tài khoản không. Không hỏi được thì coi như không (chỉ hiện đăng nhập). */
export async function fetchAllowRegister(): Promise<boolean> {
  try {
    const r = await fetch('/api/auth/options')
    if (!r.ok) return false
    const body: { allow_register?: unknown } = await r.json()
    return body.allow_register === true
  } catch {
    return false
  }
}

/** Câu báo theo mã HTTP, không hiện nguyên câu kỹ thuật của server (backend/auth.py). */
function messageFor(mode: AuthMode, status: number): AuthError {
  if (mode === 'login' && status === 401) return new AuthError('Email hoặc mật khẩu không chính xác.')
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
  throw messageFor(mode, r.status)
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
