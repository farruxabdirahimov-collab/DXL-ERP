import { useEffect, useState } from 'react'

/**
 * Teskari sanoq — bosqichli ko'rinish.
 *
 * 7 kundan ko'p  -> "12 kun qoldi"
 * 1-7 kun        -> "3 kun 4 soat"
 * 24 soatdan kam -> "18:42:15" jonli, soniyagacha
 *
 * Vaqt serverdan olinadi: `serverNow` va `deadline` farqi bir marta
 * hisoblanadi, keyin telefon o'zi sanaydi. Shunda telefon soati
 * o'zgartirilsa ham sanoq buzilmaydi va serverga har soniya so'rov ketmaydi.
 */
export function useRemainingSeconds(deadline: string, serverNow: string): number {
  const [seconds, setSeconds] = useState(() => initial(deadline, serverNow))

  useEffect(() => {
    setSeconds(initial(deadline, serverNow))
    const timer = setInterval(() => setSeconds((s) => s - 1), 1000)
    return () => clearInterval(timer)
  }, [deadline, serverNow])

  return seconds
}

function initial(deadline: string, serverNow: string): number {
  const ofset = Date.now() - new Date(serverNow).getTime()
  const hozir = Date.now() - ofset
  return Math.round((new Date(deadline).getTime() - hozir) / 1000)
}

export function formatRemaining(seconds: number): string {
  if (seconds <= 0) return 'Muddat tugadi'

  const kun = Math.floor(seconds / 86400)
  const soat = Math.floor((seconds % 86400) / 3600)

  if (seconds >= 7 * 86400) return `${kun} kun qoldi`
  if (seconds >= 86400) return `${kun} kun ${soat} soat`

  const daqiqa = Math.floor((seconds % 3600) / 60)
  const soniya = seconds % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(soat)}:${pad(daqiqa)}:${pad(soniya)}`
}

type Tone = 'ok' | 'warn' | 'danger' | 'over'

function toneFor(seconds: number): Tone {
  if (seconds <= 0) return 'over'
  if (seconds < 86400) return 'danger'
  if (seconds < 7 * 86400) return 'warn'
  return 'ok'
}

const TONE_STYLE: Record<Tone, string> = {
  ok: 'text-[var(--accent)]',
  warn: 'text-[var(--warn)]',
  danger: 'text-[var(--danger)] animate-pulse',
  over: 'text-[var(--muted)]',
}

export default function Countdown({
  deadline,
  serverNow,
  size = 'lg',
}: {
  deadline: string
  serverNow: string
  size?: 'lg' | 'sm'
}) {
  const seconds = useRemainingSeconds(deadline, serverNow)
  const tone = toneFor(seconds)

  return (
    <div
      className={`font-semibold tabular-nums ${TONE_STYLE[tone]} ${
        size === 'lg' ? 'text-[28px] leading-tight' : 'text-[13px]'
      }`}
    >
      {size === 'lg' ? <span className="mr-1">⏳</span> : null}
      {formatRemaining(seconds)}
    </div>
  )
}
