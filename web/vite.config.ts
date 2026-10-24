import basicSsl from '@vitejs/plugin-basic-ssl'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // HTTPS tự ký: trình duyệt điện thoại chỉ cho dùng camera trên trang https (hoặc localhost).
    // Lần đầu mở sẽ có cảnh báo chứng chỉ, chấp nhận một lần là được.
    basicSsl(),
  ],
  server: {
    // Mở dev server ra mạng LAN để điện thoại cùng wifi/hotspot vào được.
    // Chỉ chạy trên mạng tin cậy (nhà, hotspot của mình), không dùng wifi công cộng.
    host: true,
    // Điện thoại gọi /api/... trên chính trang này; Vite chuyển tiếp về backend ở laptop.
    // Nhờ vậy backend chỉ cần nghe 127.0.0.1, không lộ ra mạng.
    // ws: true để chuyển tiếp cả WebSocket (/api/live, đếm rep trực tiếp); trang https thì trình
    // duyệt mở wss tới Vite, Vite nối ws thường tới backend trên chính máy này.
    // FORMCOACH_API: đổi địa chỉ backend (vd chạy thử trên cổng khác), mặc định cổng 8000.
    proxy: {
      '/api': { target: process.env.FORMCOACH_API ?? 'http://127.0.0.1:8000', ws: true },
    },
  },
})
