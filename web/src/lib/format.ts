/** O'zbekcha formatlash yordamchilari. */

const MONTHS = [
  'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]

export function num(value: unknown, digits = 0): string {
  const n = Number(value ?? 0)
  if (!Number.isFinite(n)) return '0'
  return n.toLocaleString('ru-RU', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function usd(value: unknown, digits = 2): string {
  return `$${num(value, digits)}`
}

export function uzs(value: unknown): string {
  return `${num(value, 0)} so'm`
}

export function pct(value: unknown, digits = 0): string {
  return `${num(value, digits)}%`
}

export function shortDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`
}

export function longDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`
}

export function dateTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return `${shortDate(value)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function daysAgo(value?: string | null): number | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return Math.floor((Date.now() - d.getTime()) / 86_400_000)
}

export function todayISO(): string {
  return new Date().toISOString().slice(0, 10)
}

export function monthStartISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`
}

export function planColor(percent: number): string {
  if (percent >= 100) return 'var(--ok)'
  if (percent >= 80) return '#7bc043'
  if (percent >= 50) return 'var(--warn)'
  return 'var(--danger)'
}

export const STATUS_COLORS: Record<string, string> = {
  new: 'var(--warn)',
  director_review: 'var(--danger)',
  approved: 'var(--accent)',
  picking: 'var(--accent)',
  shipped: 'var(--accent)',
  delivered: 'var(--ok)',
  cancelled: 'var(--muted)',
  rejected: 'var(--muted)',
}

export const CATEGORY_LABELS: Record<string, string> = {
  A: 'A — yirik',
  B: 'B — o‘rta',
  C: 'C — kichik',
  new: 'Yangi',
}
