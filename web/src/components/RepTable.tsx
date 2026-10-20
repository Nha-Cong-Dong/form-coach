// Bước 3c: bảng nhãn rep. Mỗi rep một hàng: tick từng lỗi, "không phải rep", ghi chú.
// Bấm vào hàng (ngoài ô nhập) → nhảy tới đầu rep đó trên người que / đồ thị.
import type { RepLabel, ReviewRep } from '../label/api'

interface Props {
  labels: RepLabel[]
  reps: ReviewRep[] // cùng thứ tự với labels, để hiện số đo
  errorLabels: string[]
  setErrors: string[] // lỗi cố ý của hiệp: tô đậm cột cho dễ nhìn
  currentIndex: number | null // rep đang phát
  onChange: (index: number, label: RepLabel) => void
  onJump: (index: number) => void
}

const deg = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v.toFixed(0)}°`)

export default function RepTable({ labels, reps, errorLabels, setErrors, currentIndex, onChange, onJump }: Props) {
  const toggleError = (lab: RepLabel, err: string) => {
    const errors = lab.errors.includes(err) ? lab.errors.filter((e) => e !== err) : [...lab.errors, err].sort()
    onChange(lab.rep_index, { ...lab, errors })
  }
  // Bỏ tick "là rep" thì xoá luôn lỗi: server không nhận rep valid = false có lỗi.
  const toggleValid = (lab: RepLabel) =>
    onChange(lab.rep_index, { ...lab, valid: !lab.valid, errors: lab.valid ? [] : lab.errors })

  return (
    <table className="reps">
      <thead>
        <tr>
          <th>Rep</th>
          <th>Thời gian</th>
          <th>Khuỷu min</th>
          <th>Thân min</th>
          <th>Là rep</th>
          {errorLabels.map((e) => (
            <th key={e} className={setErrors.includes(e) ? 'set-error' : ''}>
              {e}
            </th>
          ))}
          <th>Ghi chú</th>
        </tr>
      </thead>
      <tbody>
        {labels.map((lab) => {
          const f = reps[lab.rep_index]?.features ?? {}
          const classes = [lab.rep_index === currentIndex ? 'current' : '', lab.valid ? '' : 'invalid']
          return (
            <tr key={lab.rep_index} className={classes.join(' ')} onClick={() => onJump(lab.rep_index)}>
              <td>{lab.rep_index + 1}</td>
              <td>
                {lab.start_s.toFixed(1)}–{lab.end_s.toFixed(1)} s
              </td>
              <td>{deg(f.min_elbow_angle)}</td>
              <td>{deg(f.min_body_angle)}</td>
              {/* stopPropagation: tick ô không làm nhảy vị trí phát */}
              <td onClick={(e) => e.stopPropagation()}>
                <input type="checkbox" checked={lab.valid} onChange={() => toggleValid(lab)} />
              </td>
              {errorLabels.map((err) => (
                <td key={err} onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={lab.errors.includes(err)}
                    disabled={!lab.valid}
                    onChange={() => toggleError(lab, err)}
                  />
                </td>
              ))}
              <td onClick={(e) => e.stopPropagation()}>
                <input
                  type="text"
                  className="note"
                  value={lab.note}
                  placeholder="tuỳ chọn"
                  onChange={(e) => onChange(lab.rep_index, { ...lab, note: e.target.value })}
                />
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
