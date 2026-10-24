// "Đã thấy toàn thân" cho màn Sẵn sàng (hàm thuần, có test: web/scripts/check-train.ts).
// Chỉ để nhắc người dùng căn khung; không ảnh hưởng dữ liệu gửi đi (server tự cắt rep).

// Chỉ số khớp MediaPipe (33 khớp, formcoach/pose/joints.py): vai, cổ tay, hông, cổ chân.
const SIDES = {
  left: [11, 15, 23, 27],
  right: [12, 16, 24, 28],
} as const

export const MIN_VISIBILITY = 0.5

/** Một khung thấy đủ vai, cổ tay, hông, cổ chân của ít nhất một bên (quay ngang hông). */
export function bodyVisible(
  landmarks: { visibility?: number }[] | undefined,
  minVisibility: number = MIN_VISIBILITY,
): boolean {
  if (!landmarks) return false
  return Object.values(SIDES).some((idx) =>
    idx.every((i) => (landmarks[i]?.visibility ?? 0) >= minVisibility),
  )
}

/** Tỉ lệ khung thấy toàn thân trong cửa sổ gần nhất; đủ cao mới báo "Đã thấy toàn thân". */
export class RollingRatio {
  private readonly values: boolean[] = []
  private readonly size: number

  constructor(size: number) {
    this.size = size
  }

  push(value: boolean): number {
    this.values.push(value)
    if (this.values.length > this.size) this.values.shift()
    return this.values.filter(Boolean).length / this.values.length
  }
}

export const FULL_BODY_RATIO = 0.7 // ≥ 70% khung trong ~1 s gần nhất
