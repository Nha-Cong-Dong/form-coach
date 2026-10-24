// Đọc lỗi HTTP của backend, dùng chung cho mọi file gọi API.

/** Thông báo `detail` của FastAPI, hoặc chuỗi rỗng nếu body không phải JSON. */
export async function errorDetail(r: Response): Promise<string> {
  try {
    const body: { detail?: unknown } = await r.json()
    if (body.detail === undefined) return ''
    return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
  } catch {
    return '' // body không phải JSON (vd backend chưa chạy, Vite trả 502): chỉ có mã HTTP
  }
}

/** Sự kiện phát khi một API cần đăng nhập trả 401 (phiên hết hạn / đã đăng xuất ở tab khác). */
export const UNAUTHORIZED_EVENT = 'formcoach:unauthorized'

/** Lỗi HTTP kèm thông báo `detail` của FastAPI, để hiện cho người dùng biết sai ở đâu.
 *  401: báo cho App hiện màn đăng nhập đè lên (không gỡ màn đang dùng, không mất dữ liệu). */
export async function failure(r: Response): Promise<Error> {
  if (r.status === 401) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  const detail = await errorDetail(r)
  return new Error(detail ? `HTTP ${r.status}: ${detail}` : `HTTP ${r.status}`)
}
