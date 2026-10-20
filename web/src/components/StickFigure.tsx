// Vẽ người que của MỘT khung lên canvas, từ keypoint server gửi (không chạy MediaPipe ở đây).
// Đây đúng là thứ model nhìn thấy: nếu người que trông sai thì đặc trưng cũng sai.
import { useEffect, useRef } from 'react'

interface Props {
  joints: string[]
  points: ([number, number] | null)[] // theo thứ tự `joints`, toạ độ chuẩn hoá 0–1
  frameSize: [number, number] // [rộng, cao] pixel của khung gốc, để giữ đúng tỉ lệ
}

// Cặp khớp nối thành xương, viết không có bên; mỗi cặp vẽ cho cả trái và phải.
const BONES: [string, string][] = [
  ['ear', 'shoulder'],
  ['shoulder', 'elbow'],
  ['elbow', 'wrist'],
  ['shoulder', 'hip'],
  ['hip', 'knee'],
  ['knee', 'ankle'],
]
// Cùng màu với đồ thị của `analyze --plot`: trái cam, phải xanh.
const SIDES = [
  ['left', '#f97316'],
  ['right', '#3b82f6'],
] as const

const WIDTH = 640

export default function StickFigure({ joints, points, frameSize }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const height = Math.round((WIDTH * frameSize[1]) / frameSize[0])

  useEffect(() => {
    const ctx = canvasRef.current?.getContext('2d')
    if (!ctx) return
    ctx.fillStyle = '#111'
    ctx.fillRect(0, 0, WIDTH, height)

    const at = (name: string): [number, number] | null => {
      const p = points[joints.indexOf(name)]
      return p ? [p[0] * WIDTH, p[1] * height] : null
    }
    const line = (a: [number, number] | null, b: [number, number] | null) => {
      if (!a || !b) return
      ctx.beginPath()
      ctx.moveTo(a[0], a[1])
      ctx.lineTo(b[0], b[1])
      ctx.stroke()
    }

    ctx.lineWidth = 4
    ctx.lineCap = 'round'
    for (const [side, color] of SIDES) {
      ctx.strokeStyle = color
      for (const [a, b] of BONES) line(at(`${side}_${a}`), at(`${side}_${b}`))
    }
    ctx.strokeStyle = '#9ca3af'
    line(at('left_shoulder'), at('right_shoulder'))
    line(at('left_hip'), at('right_hip'))

    ctx.fillStyle = '#e5e7eb'
    for (const name of joints) {
      const p = at(name)
      if (!p) continue
      ctx.beginPath()
      ctx.arc(p[0], p[1], 4, 0, 2 * Math.PI)
      ctx.fill()
    }
    if (points.every((p) => p === null)) {
      ctx.fillStyle = '#9ca3af'
      ctx.font = '16px system-ui'
      ctx.fillText('Không thấy người ở khung này', 16, 28)
    }
  }, [joints, points, height])

  return <canvas ref={canvasRef} width={WIDTH} height={height} className="stick" />
}
