// Nút mặt trăng / mặt trời đổi chế độ sáng–tối (DESIGN.md: "Chế độ sáng / tối").
import { useEffect, useState } from 'react'
import { currentTheme, onSystemThemeChange, setTheme } from '../theme'

export default function ThemeToggle() {
  const [theme, setThemeState] = useState(currentTheme)

  // Chưa chọn tay mà máy đổi sáng/tối: cập nhật icon cho đúng.
  useEffect(() => onSystemThemeChange(() => setThemeState(currentTheme())), [])

  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      className="icon-button"
      aria-label={next === 'dark' ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'}
      onClick={() => {
        setTheme(next)
        setThemeState(next)
      }}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {next === 'dark' ? (
          <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
        ) : (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </>
        )}
      </svg>
    </button>
  )
}
