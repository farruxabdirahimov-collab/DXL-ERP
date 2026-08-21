import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCan, useCurrentUser } from '../App'
import { useAtRisk, useContractAction, useContracts } from '../api/hooks'
import { num, shortDate, usd } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import Countdown from '../components/Countdown'
import {
  Card,
  Empty,
  ErrorBox,
  Loading,
  Progress,
  Screen,
  Section,
  Tabs,
} from '../components/ui'

const TABS = [
  { key: 'risk', label: 'Xavf ostida' },
  { key: 'active', label: 'Amalda' },
  { key: 'all', label: 'Hammasi' },
]

export default function Contracts() {
  const me = useCurrentUser()
  const can = useCan()
  const navigate = useNavigate()
  const [tab, setTab] = useState(me.role === 'doctor' ? 'active' : 'risk')

  const risk = useAtRisk(3)
  const active = useContracts({ status: 'active' })
  const all = useContracts({ limit: 100 })
  const action = useContractAction()

  const rows =
    tab === 'risk' ? (risk.data?.contracts ?? []) : tab === 'active' ? (active.data ?? []) : (all.data ?? [])
  const loading = tab === 'risk' ? risk.isLoading : tab === 'active' ? active.isLoading : all.isLoading
  const error = risk.error ?? active.error ?? all.error

  async function sovgaBerish(id: number) {
    try {
      const r = await action.mutateAsync({ id, action: 'gift' })
      haptic('success')
      alertUser(r.message ?? 'Sovg‘a berildi')
    } catch (e: any) {
      alertUser(e?.message ?? 'Bajarilmadi')
    }
  }

  return (
    <Screen title="Shartnomalar" subtitle="Taklif paketlari va muddatlar">
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      {error ? <ErrorBox error={error} /> : null}
      {loading ? <Loading /> : null}

      {/* Direktor va agent uchun bitta raqam: qancha pul xavf ostida */}
      {tab === 'risk' && risk.data && rows.length > 0 ? (
        <Card className="mb-3 p-3">
          <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
            3 kun ichida kelishi kerak
          </div>
          <div className="text-[26px] font-bold text-[var(--danger)]">
            {usd(risk.data.total_usd)}
          </div>
          {risk.data.gift_at_risk_usd != null ? (
            <div className="text-[12px] text-[var(--muted)]">
              Kelmasa {usd(risk.data.gift_at_risk_usd)} lik sovg‘a yo‘qoladi
            </div>
          ) : null}
        </Card>
      ) : null}

      <Section title={tab === 'risk' ? 'Shoshilinch' : 'Ro‘yxat'}>
        {rows.map((c: any) => (
          <Card key={c.id} className="mb-2 p-3">
            <div className="mb-2 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-[14px] font-semibold leading-snug">
                  {c.doctor_name ?? c.tariff_name}
                </div>
                <div className="text-[12px] text-[var(--muted)]">
                  {c.number} · {c.tariff_name} · {num(c.package_qty)} dona
                </div>
              </div>
              <div className="shrink-0 text-right">
                {c.status === 'active' ? (
                  <Countdown
                    deadline={c.deadline_at}
                    serverNow={c.server_now}
                    size="sm"
                  />
                ) : (
                  <span className="text-[12px] text-[var(--muted)]">
                    {c.status_label}
                  </span>
                )}
              </div>
            </div>

            <Progress percent={c.paid_pct} />
            <div className="mt-1 flex justify-between text-[12px] text-[var(--muted)]">
              <span>
                {usd(c.paid_usd)} / {usd(c.package_price_usd)}
              </span>
              <span>
                {c.remaining_usd > 0 ? `${usd(c.remaining_usd)} qoldi` : 'To‘liq to‘langan'}
              </span>
            </div>

            {c.gift_name ? (
              <div className="mt-2 flex items-center justify-between border-t border-[var(--border)] pt-2 text-[13px]">
                <span>🎁 {c.gift_name}</span>
                <span
                  className={
                    c.gift_status === 'earned'
                      ? 'font-semibold text-[var(--ok)]'
                      : c.gift_status === 'lost'
                        ? 'text-[var(--muted)]'
                        : 'text-[var(--muted)]'
                  }
                >
                  {c.gift_status_label}
                </span>
              </div>
            ) : null}

            {c.gift_note ? (
              <p className="mt-1 text-[12px] text-[var(--muted)]">{c.gift_note}</p>
            ) : null}

            <div className="mt-2 flex gap-2">
              {c.doctor_id && me.role !== 'doctor' ? (
                <button
                  className="btn btn-sm flex-1"
                  onClick={() => navigate(`/doctors/${c.doctor_id}`)}
                >
                  Vrach kartochkasi
                </button>
              ) : null}
              {c.gift_status === 'earned' && can('gifts.issue') ? (
                <button
                  className="btn btn-sm btn-primary flex-1"
                  onClick={() => sovgaBerish(c.id)}
                >
                  🎁 Sovg‘ani berdim
                </button>
              ) : null}
            </div>
          </Card>
        ))}
        {!loading && !rows.length ? (
          <Empty
            text={
              tab === 'risk'
                ? 'Yaqin kunlarda muddati tugaydigan shartnoma yo‘q'
                : 'Shartnoma yo‘q'
            }
          />
        ) : null}
      </Section>
    </Screen>
  )
}
