// Logic thuần cho đếm rep trực tiếp qua WebSocket /api/live (ARCHITECTURE §4), test bằng Node:
// web/scripts/check-live.ts. Không đếm gì ở đây: server (OnlineRepCounter) đếm.

export const MAX_SEND_FPS = 30 // giới hạn gửi: đủ cho bộ đếm, camera 60 fps không làm nghẽn mạng

/** Địa chỉ WebSocket cùng nguồn với trang: https → wss (Vite chuyển tiếp tới backend). */
export function liveUrl(loc: { protocol: string; host: string }): string {
  return `${loc.protocol === 'https:' ? 'wss' : 'ws'}://${loc.host}/api/live`
}

/** fps thật từ thời điểm các khung gần nhất (ms). Server cần fps đúng để đổi ngưỡng giây → khung. */
export class FpsMeter {
  private readonly times: number[] = []
  private readonly size: number

  constructor(size = 30) {
    this.size = size
  }

  push(tsMs: number): void {
    this.times.push(tsMs)
    if (this.times.length > this.size) this.times.shift()
  }

  /** Số khung mỗi giây trong cửa sổ; chưa đủ 2 khung → null. */
  get fps(): number | null {
    const n = this.times.length
    if (n < 2) return null
    const span = this.times[n - 1] - this.times[0]
    return span > 0 ? ((n - 1) * 1000) / span : null
  }
}

/** Có gửi khung này không: cách khung đã gửi trước ≥ 1/maxFps giây (chừa 10% cho dao động). */
export class SendThrottle {
  private last = -Infinity
  private readonly minGapMs: number

  constructor(maxFps = MAX_SEND_FPS) {
    this.minGapMs = (1000 / maxFps) * 0.9
  }

  shouldSend(tsMs: number): boolean {
    if (tsMs - this.last < this.minGapMs) return false
    this.last = tsMs
    return true
  }
}

const round4 = (v: number) => Math.round(v * 1e4) / 1e4

/** Một khung → JSON gửi server: 33 khớp [x, y, visibility] làm tròn 4 chữ số; không người → null. */
export function encodeFrame(
  tMs: number,
  landmarks: { x: number; y: number; visibility?: number }[] | undefined,
): string {
  const kp = landmarks
    ? landmarks.map((p) => [round4(p.x), round4(p.y), round4(p.visibility ?? 0)])
    : null
  return JSON.stringify({ t_ms: Math.round(tMs * 10) / 10, kp })
}

export type ServerMessage =
  | { type: 'count'; n_reps: number; phase: string }
  | { type: 'final'; n_reps: number }
  | { type: 'error'; detail: string }

/** Tin từ server; không đúng dạng → null (bỏ qua, không làm hỏng màn tập). */
export function parseServerMessage(raw: string): ServerMessage | null {
  try {
    const m: unknown = JSON.parse(raw)
    if (typeof m !== 'object' || m === null) return null
    const o = m as Record<string, unknown>
    if ((o.type === 'count' || o.type === 'final') && typeof o.n_reps === 'number') {
      return o.type === 'count'
        ? { type: 'count', n_reps: o.n_reps, phase: String(o.phase ?? '') }
        : { type: 'final', n_reps: o.n_reps }
    }
    if (o.type === 'error' && typeof o.detail === 'string') return { type: 'error', detail: o.detail }
    return null
  } catch {
    return null
  }
}
