export const num = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? '—' : v.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })
export const pct = (v: number | null | undefined, digits = 1) => (v === null || v === undefined ? '—' : `${num(v, digits)}%`)
export const round = (v: number | null | undefined) => (v === null || v === undefined ? null : Math.round(v))

export function downloadCsv(filename: string, rows: Array<Array<string | number | null | undefined>>) {
  // Prefix cells that start with a formula character so spreadsheets don't execute them.
  const cell = (v: string | number | null | undefined) => {
    let s = v === null || v === undefined ? '' : String(v)
    if (/^[=+\-@\t\r]/.test(s) && Number.isNaN(Number(s))) s = `'${s}`
    return `"${s.replaceAll('"', '""')}"`
  }
  const csv = rows.map(r => r.map(cell).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' }))
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const shortDept = (d: string) => d
  .replace('Artificial Intelligence and Machine Learning', 'AI & ML')
  .replace('Computer Science and Engineering', 'CSE')
  .replace('Electronics and Communication Engineering', 'ECE')
  .replace('Electrical and Electronics Engineering', 'EEE')
  .replace('Information Technology', 'IT')
  .replace('Mechanical Engineering', 'Mechanical')
  .replace('Civil Engineering', 'Civil')
