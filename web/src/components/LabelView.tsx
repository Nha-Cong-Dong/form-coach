// Màn hình gán nhãn: danh sách hiệp ↔ một hiệp đang gán nhãn.
import { useState } from 'react'
import ReviewView from './ReviewView'
import SessionList from './SessionList'

export default function LabelView() {
  const [selected, setSelected] = useState<string | null>(null)

  // Quay lại danh sách thì SessionList được gắn lại và tải lại: cột "Nhãn" cập nhật sau khi lưu.
  if (selected === null) return <SessionList onSelect={setSelected} />
  return <ReviewView sessionId={selected} onBack={() => setSelected(null)} />
}
