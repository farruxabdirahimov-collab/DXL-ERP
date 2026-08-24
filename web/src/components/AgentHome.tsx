import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAgentHome, useCheckIn, useNearbyDoctors } from '../api/hooks'
import { num, usd } from '../lib/format'
import { alertUser, getPosition, haptic } from '../lib/telegram'
import Countdown from './Countdown'
import { Card, Empty, Loading, Screen, Section, Sheet } from './ui'

/** Kunlik maqsad halqasi — SVG, kutubxonasiz. */
function Ring({ done, target }: { done: number; target: number }) {
  const size = 92
  const stroke = 9
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const pct = target > 0 ? Math.min(1, done / target) : 1
  const bajarildi = target === 0 || done >= target

  return (
    <svg width={size} height={size} className="shrink-0">
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="var(--bg-soft)" strokeWidth={stroke}
      />
      <circle
        cx={size / 2} cy={size / 2} r={r}
        fill="none"
        stroke={bajarildi ? 'var(--ok)' : 'var(--accent)'}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={c * (1 - pct)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text
        x="50%" y="46%" textAnchor="middle"
        fontSize="21" fontWeight="700" fill="var(--text)"
      >
        {done}
      </text>
      <text
        x="50%" y="66%" textAnchor="middle"
        fontSize="11" fill="var(--muted)"
      >
        / {target || '✓'}
      </text>
    </svg>
  )
}

export default function AgentHome() {
  const navigate = useNavigate()
  const { data, isLoading } = useAgentHome()
  const checkIn = useCheckIn()

  const [visitOpen, setVisitOpen] = useState(false)
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null)
  const [busy, setBusy] = useState(false)
  const nearby = useNearbyDoctors(coords?.lat, coords?.lon)

  if (isLoading) return <Loading />
  if (!data) return null

  const bajarildi = data.visits_target_today === 0 || data.visits_today >= data.visits_target_today

  /** «Tashrif» tugmasi: joylashuvni olib, eng yaqin vrachlarni ko'rsatadi. */
  async function tashrifBoshla() {
    setBusy(true)
    try {
      const p = await getPosition()
      if (!p) {
        alertUser('Joylashuv olinmadi — vrachni ro‘yxatdan tanlang')
        navigate('/visits')
        return
      }
      setCoords({ lat: p.lat, lon: p.lon })
      setVisitOpen(true)
    } finally {
      setBusy(false)
    }
  }

  async function qaydEt(doctorId: number) {
    try {
      await checkIn.mutateAsync({
        doctor_id: doctorId,
        lat: coords?.lat,
        lon: coords?.lon,
      })
      haptic('success')
      setVisitOpen(false)
      alertUser(`✅ Tashrif qayd etildi · +${usd(data!.per_visit_usd)}`)
    } catch (e: any) {
      alertUser(e?.message ?? 'Qayd etilmadi')
    }
  }

  return (
    <Screen title={`Salom, ${data.first_name}`} subtitle="Bugungi ishingiz">
      {/* 1. PUL — eng tepada, eng katta. Har amaldan keyin o'sadi. */}
      <Card className="mb-3 p-4 text-center">
        <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
          Bu oy topgan puling
        </div>
        <div className="my-1 text-[38px] font-bold leading-none text-[var(--accent)]">
          {usd(data.month_earned_usd)}
        </div>
        <div className="text-[14px] font-semibold text-[var(--ok)]">
          {Number(data.today_earned_usd) > 0
            ? `bugun +${usd(data.today_earned_usd)}`
            : 'bugun hali 0 — boshlang'}
        </div>
        {Number(data.month_pending_usd) > 0 ? (
          <div className="mt-1 text-[12px] text-[var(--muted)]">
            Tasdiq kutayotgani hisobga olinsa +{usd(data.month_pending_usd)}
          </div>
        ) : null}
      </Card>

      {/* 2. KUNLIK HALQA — 250 uzoq, 10 ta bugun bajariladi */}
      <Card className="mb-3 flex items-center gap-4 p-4">
        <Ring done={data.visits_today} target={data.visits_target_today} />
        <div className="min-w-0">
          <div className="text-[15px] font-semibold">
            {bajarildi ? 'Bugungi maqsad bajarildi 🎉' : 'Bugungi tashriflar'}
          </div>
          <div className="mt-0.5 text-[13px] text-[var(--muted)]">
            {bajarildi
              ? `Oyda ${num(data.visits_month)}/${num(data.visits_target_month)}`
              : `Yana ${num(data.visits_target_today - data.visits_today)} ta — ` +
                `${usd(
                  (data.visits_target_today - data.visits_today) *
                    Number(data.per_visit_usd),
                )} qoladi`}
          </div>
        </div>
      </Card>

      {/* 3. TEZ AMALLAR — ikki katta tugma */}
      <div className="mb-4 grid grid-cols-2 gap-2">
        <button
          className="btn btn-primary h-16 text-[15px]"
          disabled={busy}
          onClick={tashrifBoshla}
        >
          {busy ? 'Qidirilmoqda…' : '📍 Tashrif'}
        </button>
        <button
          className="btn h-16 text-[15px]"
          onClick={() => navigate('/new-order')}
        >
          🛒 Buyurtma
        </button>
      </div>

      {/* 4. SHOSHILINCH — bugun kimga qo'ng'iroq qilish kerak */}
      {data.urgent.length > 0 ? (
        <Section title={`🔴 Shoshilinch (${data.urgent.length})`}>
          {data.urgent.map((u: any) => (
            <Card key={u.contract_id} className="mb-2 p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="text-[14px] font-semibold">{u.doctor_name}</div>
                  <div className="text-[12px] text-[var(--muted)]">{u.reason}</div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-[16px] font-bold">{usd(u.remaining_usd)}</div>
                  <Countdown
                    deadline={u.deadline_at}
                    serverNow={u.server_now}
                    size="sm"
                  />
                </div>
              </div>
              <div className="mt-2 flex gap-2">
                <a className="btn btn-sm flex-1" href={`tel:${u.phone}`}>
                  📞 Qo‘ng‘iroq
                </a>
                <button
                  className="btn btn-sm flex-1"
                  onClick={() => navigate(`/doctors/${u.doctor_id}`)}
                >
                  Kartochka
                </button>
              </div>
            </Card>
          ))}
        </Section>
      ) : null}

      {/* Bir bosishli tashrif: eng yaqin vrachlar */}
      <Sheet
        open={visitOpen}
        title="Eng yaqin vrachlar"
        onClose={() => setVisitOpen(false)}
      >
        {nearby.isLoading ? <Loading /> : null}
        <Card className="p-0">
          {(nearby.data ?? []).map((d: any) => (
            <button
              key={d.id}
              className="flex w-full items-center justify-between gap-3 border-b border-[var(--border)] p-3 text-left last:border-b-0"
              disabled={checkIn.isPending}
              onClick={() => qaydEt(d.id)}
            >
              <div className="min-w-0">
                <div className="text-[14px] font-semibold">{d.full_name}</div>
                <div className="text-[12px] text-[var(--muted)]">
                  {d.clinic_name ?? '—'}
                </div>
              </div>
              <div className="shrink-0 text-[13px] font-semibold text-[var(--accent)]">
                {d.distance_m < 1000
                  ? `${num(d.distance_m)} m`
                  : `${(d.distance_m / 1000).toFixed(1)} km`}
              </div>
            </button>
          ))}
          {!nearby.isLoading && !nearby.data?.length ? (
            <Empty text="Yaqinda koordinatasi bor vrach topilmadi" />
          ) : null}
        </Card>
        <button className="btn mt-3 w-full" onClick={() => navigate('/visits')}>
          🔍 Boshqa vrachni tanlash
        </button>
      </Sheet>
    </Screen>
  )
}
