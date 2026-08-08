import type { ReactNode } from 'react'
import { num, pct, planColor } from '../lib/format'

export function Screen({
  title,
  subtitle,
  action,
  children,
}: {
  title: string
  subtitle?: ReactNode
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="px-3 pt-3 pb-28">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="truncate text-[19px] font-bold leading-tight">{title}</h1>
          {subtitle ? (
            <div className="mt-0.5 text-[13px] text-[var(--muted)]">{subtitle}</div>
          ) : null}
        </div>
        {action}
      </div>
      {children}
    </div>
  )
}

export function Card({
  children,
  className = '',
  onClick,
}: {
  children: ReactNode
  className?: string
  onClick?: () => void
}) {
  return (
    <div
      className={`card p-3 ${onClick ? 'cursor-pointer active:opacity-70' : ''} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  )
}

export function Section({
  title,
  action,
  children,
}: {
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="mb-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-[13px] font-bold uppercase tracking-wide text-[var(--muted)]">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  )
}

export function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: 'ok' | 'warn' | 'danger' | 'accent'
}) {
  const color =
    tone === 'ok'
      ? 'var(--ok)'
      : tone === 'warn'
        ? 'var(--warn)'
        : tone === 'danger'
          ? 'var(--danger)'
          : tone === 'accent'
            ? 'var(--accent)'
            : 'var(--text)'
  return (
    <div className="card p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--muted)]">
        {label}
      </div>
      <div className="mt-1 text-[20px] font-bold leading-tight" style={{ color }}>
        {value}
      </div>
      {hint ? <div className="mt-0.5 text-[12px] text-[var(--muted)]">{hint}</div> : null}
    </div>
  )
}

export function Progress({
  percent,
  height = 8,
}: {
  percent: number
  height?: number
}) {
  const clamped = Math.max(0, Math.min(100, percent))
  return (
    <div
      className="w-full overflow-hidden rounded-full"
      style={{ height, background: 'var(--bg-soft)' }}
    >
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${clamped}%`, background: planColor(percent) }}
      />
    </div>
  )
}

export function MetricBar({
  label,
  fact,
  target,
  percent,
  unit = '',
}: {
  label: string
  fact: number
  target: number
  percent: number
  unit?: string
}) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="mb-1 flex items-baseline justify-between text-[13px]">
        <span className="font-semibold">{label}</span>
        <span style={{ color: planColor(percent) }} className="font-bold">
          {pct(percent, 0)}
        </span>
      </div>
      <Progress percent={percent} />
      <div className="mt-1 text-[12px] text-[var(--muted)]">
        {num(fact, 0)}
        {unit} / {num(target, 0)}
        {unit}
      </div>
    </div>
  )
}

export function Chip({
  children,
  color,
}: {
  children: ReactNode
  color?: string
}) {
  return (
    <span
      className="chip"
      style={color ? { color, borderColor: color, background: 'transparent' } : undefined}
    >
      {children}
    </span>
  )
}

export function Empty({ text = 'Ma’lumot yo‘q' }: { text?: string }) {
  return (
    <div className="card p-6 text-center text-[14px] text-[var(--muted)]">{text}</div>
  )
}

export function Loading() {
  return (
    <div className="flex items-center justify-center p-10 text-[14px] text-[var(--muted)]">
      Yuklanmoqda…
    </div>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  const message =
    error instanceof Error ? error.message : 'Noma’lum xatolik yuz berdi'
  return (
    <div
      className="card p-4 text-[14px]"
      style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}
    >
      {message}
    </div>
  )
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string
  children: ReactNode
  hint?: string
}) {
  return (
    <div className="mb-3">
      <label className="label">{label}</label>
      {children}
      {hint ? <div className="mt-1 text-[12px] text-[var(--muted)]">{hint}</div> : null}
    </div>
  )
}

export function Sheet({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-end"
      style={{ background: 'rgba(0,0,0,.45)' }}
      onClick={onClose}
    >
      <div
        className="max-h-[88vh] w-full overflow-y-auto rounded-t-2xl p-4"
        style={{ background: 'var(--card)', paddingBottom: 'calc(16px + var(--safe-bottom))' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[17px] font-bold">{title}</h3>
          <button className="btn btn-sm" onClick={onClose}>
            Yopish
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string }[]
  active: string
  onChange: (key: string) => void
}) {
  return (
    <div className="scroll-x mb-3 flex gap-2">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className="chip"
          style={
            active === tab.key
              ? {
                  background: 'var(--accent)',
                  color: 'var(--accent-text)',
                  borderColor: 'transparent',
                }
              : undefined
          }
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export function Row({
  title,
  subtitle,
  right,
  rightSub,
  onClick,
}: {
  title: ReactNode
  subtitle?: ReactNode
  right?: ReactNode
  rightSub?: ReactNode
  onClick?: () => void
}) {
  return (
    <div
      className={`flex items-center justify-between gap-3 border-b border-[var(--border)] px-3 py-2.5 last:border-b-0 ${
        onClick ? 'cursor-pointer active:opacity-60' : ''
      }`}
      onClick={onClick}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate text-[14px] font-semibold">{title}</div>
        {subtitle ? (
          <div className="truncate text-[12px] text-[var(--muted)]">{subtitle}</div>
        ) : null}
      </div>
      {right !== undefined ? (
        <div className="shrink-0 text-right">
          <div className="text-[14px] font-bold">{right}</div>
          {rightSub ? (
            <div className="text-[12px] text-[var(--muted)]">{rightSub}</div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
