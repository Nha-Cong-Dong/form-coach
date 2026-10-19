# web/ — trang quay dữ liệu

Trang React + TypeScript (Vite) chạy trên điện thoại: bật camera, MediaPipe JS vẽ khung xương
realtime, chọn lỗi cố ý của hiệp, bấm Bắt đầu/Xong để gửi keypoint về backend
(`data/sessions/<bài>/<session_id>.json`). Không chứa logic ML; định dạng file ở
`src/session/format.ts` (xem `docs/ARCHITECTURE.md` §2b).

```bash
npm install                     # lần đầu / khi package.json đổi (Node 24 qua nvm)
npm run dev                     # https://localhost:5173 và https://<IP-laptop>:5173 (cần backend ở :8000)
npm run dev -- --host 127.0.0.1 # chỉ laptop (mạng không tin cậy)
npm run build && npm run lint   # kiểm tra TypeScript + oxlint
```

- `predev` / `prebuild` tự chép wasm của MediaPipe và model `../assets/pose_landmarker_full.task`
  vào `public/` (bị gitignore).
- HTTPS tự ký vì trình duyệt chỉ cho dùng camera trên https; lần đầu chấp nhận cảnh báo chứng chỉ.
- Quay: điện thoại nằm ngang (tắt khoá xoay), sát sàn, ngang hông, chỉ một người trong khung.
