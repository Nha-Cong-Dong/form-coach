// Chế độ sáng/tối và đọc token màu cho canvas. Màu nằm ở theme.css (chép từ DESIGN.md);
// file này chỉ bật/tắt thuộc tính data-theme trên <html> và nhớ lựa chọn trong trình duyệt.

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'formcoach-theme'
const darkQuery = () => window.matchMedia('(prefers-color-scheme: dark)')

/** Lựa chọn người dùng đã bấm, hoặc null nếu chưa chọn (theo máy). */
export function storedTheme(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null // chế độ riêng tư hoặc bị chặn lưu trữ: theo máy
  }
}

/** Đặt data-theme trên <html>; null = bỏ thuộc tính, theo cài đặt của máy. */
export function applyTheme(theme: Theme | null): void {
  if (theme) document.documentElement.dataset.theme = theme
  else delete document.documentElement.dataset.theme
}

/** Chế độ đang hiển thị (đã chọn tay, hoặc theo máy). */
export function currentTheme(): Theme {
  return storedTheme() ?? (darkQuery().matches ? 'dark' : 'light')
}

/** Chọn tay một chế độ, nhớ cho lần mở sau. */
export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // không lưu được thì chỉ đổi cho lần mở này
  }
  applyTheme(theme)
}

/** Theo dõi khi máy đổi sáng/tối (chỉ có tác dụng khi chưa chọn tay). Trả hàm huỷ. */
export function onSystemThemeChange(callback: () => void): () => void {
  const q = darkQuery()
  q.addEventListener('change', callback)
  return () => q.removeEventListener('change', callback)
}

/** Giá trị một token CSS (vd 'color-stage'), cho canvas: canvas không hiểu `var(--...)`. */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim()
}
