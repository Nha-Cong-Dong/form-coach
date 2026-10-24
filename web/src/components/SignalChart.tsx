// Đồ thị góc theo thời gian bằng SVG (không thêm thư viện): tô vùng từng rep, vạch vị trí đang
// phát, bấm vào đồ thị để nhảy tới thời điểm đó.
import { useMemo } from 'react'
import type { MouseEvent } from 'react'
import type { ReviewRep } from '../label/api'

export interface Series {
  name: string
  values: (number | null)[]
  color: string
}

interface Props {
  times: number[]
  series: Series[]
  reps: ReviewRep[]
  thresholds: { value: number; label: string }[]
  cursorS: number
  onSeek: (timeS: number) => void
}

const W = 900
const H = 220
const PAD = { left: 36, right: 8, top: 8, bottom: 20 }
const Y_MAX = 185 // góc 0–185°, như `analyze --plot`

/** Chuỗi lệnh path SVG; ngắt nét ở chỗ None (khung không thấy người). */
function pathOf(times: number[], values: (number | null)[], x: (t: number) => number, y: (v: number) => number) {
  let d = ''
  let pen = false
  values.forEach((v, i) => {
    if (v === null) {
      pen = false
      return
    }
    d += `${pen ? 'L' : 'M'}${x(times[i]).toFixed(1)},${y(v).toFixed(1)}`
    pen = true
  })
  return d
}

const y = (v: number) => PAD.top + (1 - v / Y_MAX) * (H - PAD.top - PAD.bottom)

/** Hàm đổi thời gian (s) → toạ độ x của SVG, theo độ dài hiệp. */
function xScale(tEnd: number) {
  return (t: number) => PAD.left + (t / tEnd) * (W - PAD.left - PAD.right)
}

export default function SignalChart({ times, series, reps, thresholds, cursorS, onSeek }: Props) {
  const tEnd = times[times.length - 1] || 1
  const x = xScale(tEnd)

  // Đường đồ thị chỉ tính lại khi đổi hiệp, không phải mỗi khung phát.
  const paths = useMemo(() => {
    const sx = xScale(times[times.length - 1] || 1)
    return series.map((s) => ({ ...s, d: pathOf(times, s.values, sx, y) }))
  }, [times, series])

  const handleClick = (e: MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - box.left) / box.width) * W // đổi từ pixel màn hình về toạ độ SVG
    const t = ((px - PAD.left) / (W - PAD.left - PAD.right)) * tEnd
    onSeek(Math.min(Math.max(t, 0), tEnd))
  }

  const ticks = Array.from({ length: Math.floor(tEnd / 5) + 1 }, (_, k) => k * 5)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" onClick={handleClick}>
      {reps.map((r) => (
        <g key={r.index}>
          <rect
            x={x(r.start_s)}
            y={PAD.top}
            width={x(r.end_s) - x(r.start_s)}
            height={H - PAD.top - PAD.bottom}
            style={{ fill: 'var(--color-accent)' }}
            opacity={0.12}
          />
          <text x={(x(r.start_s) + x(r.end_s)) / 2} y={PAD.top + 14} textAnchor="middle" fontSize={13} style={{ fill: 'var(--color-accent)' }}>
            {r.index + 1}
          </text>
        </g>
      ))}
      {[0, 45, 90, 135, 180].map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} style={{ stroke: 'var(--color-line)' }} />
          <text x={PAD.left - 4} y={y(v) + 4} textAnchor="end" fontSize={11} style={{ fill: 'var(--color-ink2)' }}>
            {v}°
          </text>
        </g>
      ))}
      {ticks.map((t) => (
        <text key={t} x={x(t)} y={H - 4} textAnchor="middle" fontSize={11} style={{ fill: 'var(--color-ink2)' }}>
          {t}s
        </text>
      ))}
      {thresholds.map((th) => (
        <g key={th.label}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(th.value)} y2={y(th.value)} strokeDasharray="5 4" style={{ stroke: 'var(--color-accent)' }} />
          <text x={W - PAD.right - 4} y={y(th.value) - 4} textAnchor="end" fontSize={11} style={{ fill: 'var(--color-accent)' }}>
            {th.label}
          </text>
        </g>
      ))}
      {paths.map((p) => (
        <path key={p.name} d={p.d} fill="none" strokeWidth={1.8} style={{ stroke: p.color }} />
      ))}
      <line x1={x(cursorS)} x2={x(cursorS)} y1={PAD.top} y2={H - PAD.bottom} strokeWidth={1.5} style={{ stroke: 'var(--color-ink)' }} />
      <g>
        {series.map((s, k) => (
          <text key={s.name} x={PAD.left + 8 + k * 130} y={H - PAD.bottom - 6} fontSize={12} style={{ fill: s.color }}>
            ━ {s.name}
          </text>
        ))}
      </g>
    </svg>
  )
}
