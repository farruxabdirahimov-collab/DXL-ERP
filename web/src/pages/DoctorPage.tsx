import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useCan } from '../App'
import {
  useCheckIn,
  useCreatePayment,
  useDoctor,
  useDoctorDebt,
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
import { DoctorForm } from './Doctors'

export default function DoctorPage() {
  const { id } = useParams()
  const doctorId = Number(id)
  const navigate = useNavigate()
  const can = useCan()

  const { data: doctor, isLoading, error } = useDoctor(doctorId)
  const { data: debt } = useDoctorDebt(doctorId)
  const { data: orders } = useOrders({ doctor_id: doctorId, limit: 15 })
  const { data: fx } = useFxRate()

  const [payOpen, setPayOpen] = useState(false)
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
