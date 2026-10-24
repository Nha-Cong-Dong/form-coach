import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Font Inter nằm trong app (không tải từ Google), chỉ các độ đậm DESIGN.md dùng.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import './theme.css'
import './index.css'
import App from './App.tsx'
import { applyTheme, storedTheme } from './theme'

// Đặt chế độ đã chọn trước khi vẽ lần đầu, để không nháy sáng rồi mới tối.
applyTheme(storedTheme())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
