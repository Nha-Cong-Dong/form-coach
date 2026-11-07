// Nạp thư viện nút "Sign in with Google" (Google Identity Services, GIS) bằng thẻ <script>, theo
// hướng dẫn của Google; không có gói npm chính thức. Chỉ nạp khi server bật Google (có Client ID).
// Tham số theo https://developers.google.com/identity/gsi/web/reference/js-reference (đọc 2026-11-07).

const GIS_SRC = 'https://accounts.google.com/gsi/client'

/** Phần của `window.google.accounts.id` mà app dùng. */
export interface GoogleId {
  initialize(config: {
    client_id: string
    callback: (response: { credential: string }) => void
    context?: 'signin' | 'signup' | 'use'
    cancel_on_tap_outside?: boolean
  }): void
  renderButton(
    parent: HTMLElement,
    options: {
      type?: 'standard' | 'icon'
      theme?: 'outline' | 'filled_blue' | 'filled_black'
      size?: 'large' | 'medium' | 'small'
      text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
      shape?: 'rectangular' | 'pill' | 'circle' | 'square'
      logo_alignment?: 'left' | 'center'
      width?: string // px, tối đa 400
      locale?: string
    },
  ): void
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleId } }
  }
}

let loading: Promise<GoogleId> | null = null

/** Nạp GIS một lần cho cả trang; lỗi (mất mạng, bị chặn) thì lần sau thử lại. */
export function loadGoogleId(): Promise<GoogleId> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id)
  if (!loading) {
    loading = new Promise<GoogleId>((resolve, reject) => {
      const script = document.createElement('script')
      script.src = GIS_SRC
      script.async = true
      script.onload = () => {
        const id = window.google?.accounts?.id
        if (id) resolve(id)
        else reject(new Error('thư viện Google không có google.accounts.id'))
      }
      script.onerror = () => reject(new Error('không tải được thư viện Google'))
      document.head.appendChild(script)
    }).catch((e) => {
      loading = null
      throw e
    })
  }
  return loading
}
