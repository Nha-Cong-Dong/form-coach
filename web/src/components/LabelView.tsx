// Màn hình gán nhãn: danh sách hiệp ↔ một hiệp đang gán nhãn.
import { useState } from 'react'
import type { CaptureMode } from '../session/format'
import ReviewView from './ReviewView'
import SessionList from './SessionList'

export default function LabelView() {
  const [selected, setSelected] = useState<{ id: string; mode: CaptureMode } | null>(null)

  // Quay lại danh sách thì SessionList được gắn lại và tải lại: cột "Nhãn" cập nhật sau khi lưu.
  if (selected === null) return <SessionList onSelect={(id, mode) => setSelected({ id, mode })} />
  return (
    <ReviewView
      sessionId={selected.id}
      // Hiệp Tập không có lỗi cố ý: nhãn "tốt" điền sẵn không có căn cứ, phải duyệt từng rep (D0c).
      needsReview={selected.mode === 'train'}
      onBack={() => setSelected(null)}
    />
  )
}
