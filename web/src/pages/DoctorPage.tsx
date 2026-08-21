import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useCan } from '../App'
import {
  useCheckIn,
  useCreatePayment,
  useContracts,
  useCreateContract,
  useDoctor,
  useDoctorDebt,
  useDoctorHistory,
  useTariffs,
  useFxRate,
  useOrders,
} from '../api/hooks'
import { api } from '../api/client'
import { CATEGORY_LABELS, num, shortDate, usd, uzs } from '../lib/format'
import { alertUser, getPosition, haptic } from '../lib/telegram'
import {
  Card,
  Chip,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Row,
  Screen,
  Section,
  Sheet,
  Stat,
} from '../components/ui'
import Countdown from '../components/Countdown'
import { DoctorForm } from './Doctors'

export default function DoctorPage() {
  const { id } = useParams()
  const doctorId = Number(id)
  const navigate = useNavigate()
  const can = useCan()

  const { data: doctor, isLoading, error } = useDoctor(doctorId)
  const { data: debt } = useDoctorDebt(doctorId)
  const { data: history } = useDoctorHistory(doctorId)
  const { data: contracts } = useContracts({ doctor_id: doctorId })
  const { data: tariffs } = useTariffs()
  const createContract = useCreateContract()
  const { data: orders } = useOrders({ doctor_id: doctorId, limit: 15 })
  const { data: fx } = useFxRate()

  const [payOpen, setPayOpen] = useState(false)
  const [contractOpen, setContractOpen] = useState(false)
  const [tariffId, setTariffId] = useState<number | undefined>()
  const [editOpen, setEditOpen] = useState(false)
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('cash')
  const [note, setNote] = useState('')

  const createPayment = useCreatePayment()
  const checkIn = useCheckIn()

  if (isLoading) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!doctor) return null

  const overdue = Number(doctor.overdue_usd) > 0
  const limitLeft = Number(doctor.debt_limit_usd) - Number(doctor.debt_usd)

  async function submitPayment() {
    const value = Number(amount.replace(/\s/g, ''))
    if (!value || value <= 0) {
      alertUser('To‘lov summasini kiriting (so‘mda)')
      return
    }
    try {
      const result = await createPayment.mutateAsync({
        doctor_id: doctorId,
        amount_uzs: value,
        method,
        note: note || null,
      })
      haptic('success')
      alertUser(result.message ?? 'To‘lov qabul qilindi')
      setPayOpen(false)
      setAmount('')
      setNote('')
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  async function doCheckIn() {
    const position = await getPosition()
    try {
      await checkIn.mutateAsync({
        doctor_id: doctorId,
        lat: position?.lat ?? null,
        lon: position?.lon ?? null,
        result: 'no_order',
      })
      haptic('success')
      alertUser(
        position
          ? 'Tashrif qayd etildi (joylashuv bilan)'
          : 'Tashrif qayd etildi (joylashuvsiz)',
      )
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  return (
    <Screen
      title={doctor.full_name}
      subtitle={
        <>
          {doctor.clinic_name ?? '—'}
          {doctor.specialty ? ` · ${doctor.specialty}` : ''}
        </>
      }
      action={
        can('doctors.edit') ? (
          <button className="btn btn-sm" onClick={() => setEditOpen(true)}>
            ✏️
          </button>
        ) : null
      }
    >
      <div className="mb-3 flex flex-wrap gap-1.5">
        <Chip>{CATEGORY_LABELS[doctor.category] ?? doctor.category}</Chip>
        <Chip>⭐ Sodiqlik {doctor.loyalty_score}/100</Chip>
        {doctor.agent_name ? <Chip>👤 {doctor.agent_name}</Chip> : null}
        {doctor.birth_date ? <Chip>🎂 {shortDate(doctor.birth_date)}</Chip> : null}
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2">
        <Stat
          label="Qarz"
          value={usd(doctor.debt_usd)}
          hint={`Limit: ${usd(doctor.debt_limit_usd, 0)}`}
          tone={overdue ? 'danger' : Number(doctor.debt_usd) > 0 ? 'warn' : 'ok'}
        />
        <Stat
          label="Muddati o‘tgan"
          value={usd(doctor.overdue_usd)}
          hint={overdue ? `${doctor.overdue_days} kun kechikkan` : 'Kechikish yo‘q'}
          tone={overdue ? 'danger' : 'ok'}
        />
        <Stat
          label="12 oylik xarid"
          value={usd(doctor.purchased_12m_usd, 0)}
          hint={`${num(doctor.orders_12m)} buyurtma`}
        />
        <Stat
          label="Limitdan qolgan"
          value={usd(limitLeft, 0)}
          hint={`To‘lov muddati: ${doctor.payment_term_days} kun`}
          tone={limitLeft <= 0 ? 'danger' : 'accent'}
        />
      </div>

      <div className="mb-4 grid grid-cols-2 gap-2">
        {can('payments.create') ? (
          <button className="btn btn-primary" onClick={() => setPayOpen(true)}>
            💰 To‘lov kiritish
          </button>
        ) : null}
        {can('orders.create') ? (
          <button
            className="btn"
            onClick={() => navigate(`/new-order?doctor=${doctorId}`)}
          >
            🛒 Buyurtma
          </button>
        ) : null}
        {can('visits.own') || can('visits.all') ? (
          <button className="btn" onClick={doCheckIn} disabled={checkIn.isPending}>
            📍 Tashrif qayd etish
          </button>
        ) : null}
        <a className="btn" href={`tel:${doctor.phone}`}>
          📞 {doctor.phone}
        </a>
      </div>

      {doctor.address ? (
        <Section title="Manzil">
          <Card>
            <div className="text-[14px]">{doctor.address}</div>
            <div className="mt-1 text-[12px] text-[var(--muted)]">
              {[doctor.region, doctor.district].filter(Boolean).join(', ')}
            </div>
            {doctor.lat && doctor.lon ? (
              <a
                className="btn btn-sm mt-2 w-full"
                href={`https://maps.google.com/?q=${doctor.lat},${doctor.lon}`}
                target="_blank"
                rel="noreferrer"
              >
                🗺 Xaritada ochish
              </a>
            ) : null}
          </Card>
        </Section>
      ) : null}

      {debt?.orders?.length ? (
        <Section
          title="To‘lanmagan buyurtmalar"
          action={
            <button
              className="btn btn-sm"
              onClick={() => api.download('/reports/export.xlsx', { kind: 'debts' })}
            >
              ⬇️
            </button>
          }
        >
          <Card className="p-0">
            {debt.orders.map((order: any) => (
              <Row
                key={order.number}
                title={order.number}
                subtitle={`Muddat: ${shortDate(order.due_date)}${
                  order.overdue_days > 0 ? ` · ${order.overdue_days} kun kechikdi` : ''
                }`}
                right={
                  <span
                    style={{ color: order.overdue_days > 0 ? 'var(--danger)' : undefined }}
                  >
                    {usd(order.debt_usd)}
                  </span>
                }
                rightSub={`jami ${usd(order.total_usd)}`}
              />
            ))}
          </Card>
        </Section>
      ) : null}

      {/* Taklif-shartnoma: amaldagisi sanoq bilan, yo'q bo'lsa tuzish tugmasi */}
      {can('contracts.view') ? (
        <Section title="Taklif-shartnoma">
          {(contracts ?? [])
            .filter((c: any) => c.status === 'active')
            .map((c: any) => (
              <Card key={c.id} className="mb-2 p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[14px] font-semibold">{c.tariff_name}</div>
                    <div className="text-[12px] text-[var(--muted)]">
                      {c.number} · {num(c.package_qty)} dona ·{' '}
                      {usd(c.package_price_usd)}
                    </div>
                  </div>
                  <Countdown
                    deadline={c.deadline_at}
                    serverNow={c.server_now}
                    size="sm"
                  />
                </div>
                <div className="mt-2 flex justify-between text-[12px] text-[var(--muted)]">
                  <span>To‘langan {usd(c.paid_usd)}</span>
                  <span>{usd(c.remaining_usd)} qoldi</span>
                </div>
                {c.gift_name ? (
                  <div className="mt-1 text-[13px]">
                    🎁 {c.gift_name} — {c.gift_status_label}
                  </div>
                ) : null}
              </Card>
            ))}

          {!(contracts ?? []).some((c: any) => c.status === 'active') ? (
            can('contracts.create') ? (
              <button
                className="btn btn-primary w-full"
                onClick={() => setContractOpen(true)}
              >
                📝 Shartnoma tuzish
              </button>
            ) : (
              <Empty text="Amaldagi shartnoma yo‘q" />
            )
          ) : null}
        </Section>
      ) : null}

      {history && history.summary.orders_count > 0 ? (
        <>
          <Section title="Mini hisobot">
            <div className="grid grid-cols-2 gap-2">
              <Stat
                label="Xarid qildi (sof)"
                value={usd(history.summary.net_usd)}
                tone="accent"
              />
              <Stat label="To‘lov qildi" value={usd(history.summary.paid_usd)} tone="ok" />
              <Stat
                label="Olgan implant"
                value={`${num(history.summary.net_units)} dona`}
              />
              <Stat
                label="Qaytargan"
                value={`${num(history.summary.returned_units)} dona`}
                tone={history.summary.returned_units > 0 ? 'warn' : undefined}
              />
            </div>
            {history.summary.returned_units > 0 ? (
              <p className="mt-2 px-1 text-xs text-slate-500">
                Jami {usd(history.summary.bought_usd)} olgan, {usd(history.summary.returned_usd)}{' '}
                qaytargan — yuqoridagi «sof» raqam shu ayirma.
              </p>
            ) : null}
          </Section>

          <Section title="Qaysi razmerlarni oladi">
            <Card className="p-0">
              {history.sizes.map((row: any) => (
                <Row
                  key={`${row.size}-${row.implant_type ?? ''}`}
                  title={row.size}
                  subtitle={
                    row.returned_qty
                      ? `${row.implant_type ?? 'Implant'} · olgan ${num(
                          row.bought_qty,
                        )}, qaytargan ${num(row.returned_qty)}`
                      : (row.implant_type ?? 'Implant')
                  }
                  right={`${num(row.net_qty)} dona`}
                  rightSub={usd(row.amount_usd)}
                />
              ))}
            </Card>
          </Section>

          <Section title="Tranzaksiyalar tarixi">
            <Card className="p-0">
              {history.timeline.map((e: any, index: number) => (
                <Row
                  key={`${e.kind}-${e.number}-${index}`}
                  title={
                    <span>
                      <span className="mr-1">
                        {e.kind === 'order' ? '🛒' : e.kind === 'return' ? '↩️' : '💰'}
                      </span>
                      {e.number}
                    </span>
                  }
                  subtitle={
                    [
                      shortDate(e.at),
                      e.lines?.length
                        ? e.lines
                            .map((l: any) => `${l.size} × ${l.qty}`)
                            .join(', ')
                        : null,
                      e.note,
                    ]
                      .filter(Boolean)
                      .join(' · ')
                  }
                  right={`${e.kind === 'order' ? '' : '− '}${usd(e.amount_usd)}`}
                  onClick={e.order_id ? () => navigate(`/orders/${e.order_id}`) : undefined}
                />
              ))}
            </Card>
          </Section>
        </>
      ) : null}

      <Section title="Buyurtmalar tarixi">
        <Card className="p-0">
          {(orders ?? []).map((order) => (
            <Row
              key={order.id}
              title={order.number}
              subtitle={`${order.status_label ?? order.status} · ${shortDate(order.created_at)}`}
              right={usd(order.total_usd)}
              rightSub={`${order.items.length} pozitsiya`}
              onClick={() => navigate(`/orders/${order.id}`)}
            />
          ))}
          {!orders?.length ? <Empty text="Buyurtma yo‘q" /> : null}
        </Card>
      </Section>

      {doctor.notes ? (
        <Section title="Izoh">
          <Card>
            <p className="text-[13px]">{doctor.notes}</p>
          </Card>
        </Section>
      ) : null}

      {/* To'lov oynasi */}
      <Sheet
        open={contractOpen}
        title="Shartnoma tuzish"
        onClose={() => setContractOpen(false)}
      >
        <p className="mb-3 text-[13px] text-[var(--muted)]">
          Teskari sanoq <b>hozirdan</b> boshlanadi. Vrach muddat ichida to‘liq
          to‘lasa sovg‘ani oladi.
        </p>
        <Field label="Tarifni tanlang">
          <select
            className="select"
            value={tariffId ?? ''}
            onChange={(e) => setTariffId(Number(e.target.value) || undefined)}
          >
            <option value="">— tanlang —</option>
            {(tariffs ?? []).map((t: any) => (
              <option key={t.id} value={t.id}>
                {t.name} · {num(t.package_qty)} dona · {usd(t.package_price_usd)} ·{' '}
                {t.term_days} kun
              </option>
            ))}
          </select>
        </Field>
        {tariffId ? (
          <Card className="mb-3 p-3 text-[13px]">
            {(() => {
              const t = (tariffs ?? []).find((x: any) => x.id === tariffId)
              if (!t) return null
              return (
                <>
                  <div className="flex justify-between py-0.5">
                    <span className="text-[var(--muted)]">Dona narxi</span>
                    <b>{usd(t.unit_price_usd)}</b>
                  </div>
                  <div className="flex justify-between py-0.5">
                    <span className="text-[var(--muted)]">To‘lov muddati</span>
                    <b>{t.term_days} kun</b>
                  </div>
                  {t.gift_name ? (
                    <div className="flex justify-between py-0.5">
                      <span className="text-[var(--muted)]">Sovg‘a</span>
                      <b>🎁 {t.gift_name}</b>
                    </div>
                  ) : null}
                </>
              )
            })()}
          </Card>
        ) : null}
        <button
          className="btn btn-primary w-full"
          disabled={!tariffId || createContract.isPending}
          onClick={async () => {
            try {
              const r = await createContract.mutateAsync({
                doctor_id: doctorId,
                tariff_id: tariffId,
              })
              haptic('success')
              setContractOpen(false)
              alertUser(`Shartnoma tuzildi: ${r.number}`)
            } catch (e: any) {
              alertUser(e?.message ?? 'Tuzilmadi')
            }
          }}
        >
          {createContract.isPending ? 'Tuzilmoqda…' : 'Shartnomani tuzish'}
        </button>
      </Sheet>

      <Sheet open={payOpen} title="To‘lov kiritish" onClose={() => setPayOpen(false)}>
        <div className="mb-3 text-[13px] text-[var(--muted)]">
          {doctor.full_name} · qarz {usd(doctor.debt_usd)}
          {fx ? ` · kurs 1$ = ${num(fx.usd_uzs)} so'm` : ''}
        </div>
        <Field label="Summa (so‘mda)">
          <input
            className="input text-right text-[18px] font-bold"
            inputMode="numeric"
            placeholder="0"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
        {amount && fx ? (
          <div className="mb-3 text-[13px] text-[var(--muted)]">
            ≈ {usd(Number(amount.replace(/\s/g, '')) / Number(fx.usd_uzs))} qarzni yopadi
          </div>
        ) : null}
        <Field label="To‘lov turi">
          <select
            className="select"
            value={method}
            onChange={(e) => setMethod(e.target.value)}
          >
            <option value="cash">Naqd</option>
            <option value="card">Karta</option>
            <option value="transfer">O‘tkazma</option>
          </select>
        </Field>
        <Field label="Izoh">
          <input
            className="input"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>
        <button
          className="btn btn-primary w-full"
          disabled={createPayment.isPending}
          onClick={submitPayment}
        >
          {createPayment.isPending ? 'Saqlanmoqda…' : 'To‘lovni tasdiqlash'}
        </button>
      </Sheet>

      <DoctorForm open={editOpen} initial={doctor} onClose={() => setEditOpen(false)} />
    </Screen>
  )
}
