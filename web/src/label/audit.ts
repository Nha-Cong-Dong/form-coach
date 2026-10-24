// Logic thuần của màn kiểm tra độ nhất quán (gán lại mù), test bằng Node:
// web/scripts/check-audit.ts, chạy qua tests/test_web_audit.py.
// Định dạng khớp evaluation/relabel_consistency.py (audit_hash, parse_answers).

export interface AuditItem {
  sessionId: string
  repIndex: number
}

export interface AuditAnswer {
  valid: boolean // false = "không phải rep"
  errors: string[]
}

/** `#audit/<hiệp>~<rep>,...` → danh sách rep theo thứ tự hiện; sai dạng → null. */
export function parseAuditHash(hash: string): AuditItem[] | null {
  const m = hash.match(/^#audit\/(.+)$/)
  if (!m) return null
  const items: AuditItem[] = []
  for (const part of decodeURIComponent(m[1]).split(',')) {
    const pm = part.match(/^([A-Za-z0-9_-]{1,100})~(\d+)$/)
    if (!pm) return null
    items.push({ sessionId: pm[1], repIndex: Number(pm[2]) })
  }
  return items.length > 0 ? items : null
}

/** Một rep → một mục đáp án: "x" (không phải rep), "0" (không lỗi), hoặc số thứ tự lỗi ("13"). */
export function answerToken(answer: AuditAnswer, errorLabels: string[]): string {
  if (!answer.valid) return 'x'
  const digits = errorLabels
    .map((e, i) => (answer.errors.includes(e) ? String(i + 1) : ''))
    .join('')
  return digits || '0'
}

/** Chuỗi đáp án dán vào `python -m evaluation.relabel_consistency score --answers "..."`. */
export function answersString(answers: AuditAnswer[], errorLabels: string[]): string {
  return answers.map((a) => answerToken(a, errorLabels)).join(',')
}

export const emptyAnswer = (): AuditAnswer => ({ valid: true, errors: [] })

/** Đọc tiến độ đã lưu (đúng số rep); dữ liệu hỏng/khác mẫu → bắt đầu lại. */
export function parseSavedAnswers(raw: string | null, n: number): AuditAnswer[] | null {
  if (!raw) return null
  try {
    const value: unknown = JSON.parse(raw)
    if (!Array.isArray(value) || value.length !== n) return null
    const ok = value.every(
      (a) =>
        typeof a === 'object' &&
        a !== null &&
        typeof (a as AuditAnswer).valid === 'boolean' &&
        Array.isArray((a as AuditAnswer).errors),
    )
    return ok ? (value as AuditAnswer[]) : null
  } catch {
    return null
  }
}
