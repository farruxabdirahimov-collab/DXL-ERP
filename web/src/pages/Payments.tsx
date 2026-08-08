import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCan } from '../App'
import { useCreatePayment, useDoctors, useFxRate, usePayments } from '../api/hooks'
import { dateTime, num, usd, uzs } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Row,
  Screen,
  Sheet,
  Stat,
} from '../components/ui'

const METHODS: Record<string, string> = {
  cash: 'Naqd',
  card: 'Karta',
  transfer: 'O‘tkazma',
}

export default function Payments() {
  const can = useCan()
  const navigate = useNavigate()
  const { data, isLoading, error } = usePayments({ limit: 100 })
  const { data: doctors } = useDoctors({ limit: 500 })
  const { data: fx } = useFxRate()
  const createPayment = useCreatePayment()

  const [open, setOpen] = useState(false)
  const [doctorId, setDoctorId] = useState<number | undefined>()
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('cash')
  const [note, setNote] = useState('')
  const [search, setSearch] = useState('')

  const todayTotal = (data ?? [])
    .filter((p) => new Date(p.paid_at).toDateString() === new Date().toDateString())
    .reduce((sum, p) => sum + Number(p.amount_uzs), 0)

  async function submit() {
    const value = Number(amount.replace(/\s/g, ''))
    if (!doctorId) {
      alertUser('Vrachni tanlang')
      return
    }
    if (!value || value <= 0) {
      alertUser('Summani kiriting')
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
      setOpen(false)
      setAmount('')
      setNote('')
      setDoctorId(undefined)
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  const filteredDoctors = (doctors ?? []).filter((d) =>
    search
      ? d.full_name.toLowerCase().includes(search.toLowerCase()) ||
        d.phone.includes(search)
      : true,
  )

  return (
    <Screen
      title="To‘lovlar"
      subtitle={fx ? `Kurs: 1$ = ${num(fx.usd_uzs)} so'm` : undefined}
      action={
        can('payments.create') ? (
          <button className="btn btn-sm btn-primary" onClick={() => setOpen(true)}>
            + To‘lov
          </button>
        ) : null
      }
    >
      <div className="mb-3 grid grid-cols-2 gap-2">
        <Stat label="Bugungi tushum" value={uzs(todayTotal)} tone="ok" />
        <Stat label="Yozuvlar" value={num(data?.length ?? 0)} />
      </div>

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}

      <Card className="p-0">
        {(data ?? []).map((payment) => (
          <Row
            key={payment.id}
            title={payment.doctor_name ?? `#${payment.doctor_id}`}
            subtitle={`${METHODS[payment.method] ?? payment.method} · ${dateTime(payment.paid_at)}${
              payment.order_number ? ` · ${payment.order_number}` : ''
            }`}
            right={uzs(payment.amount_uzs)}
            rightSub={usd(payment.amount_usd)}
            onClick={() => navigate(`/doctors/${payment.doctor_id}`)}
          />
        ))}
        {data?.length === 0 ? <Empty text="To‘lov yo‘q" /> : null}
      </Card>

      <Sheet open={open} title="Yangi to‘lov" onClose={() => setOpen(false)}>
        <Field label="Vrach">
          <input
            className="input mb-2"
            placeholder="Qidirish…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="select"
            value={doctorId ?? ''}
            onChange={(e) => setDoctorId(Number(e.target.value))}
          >
            <option value="">Tanlang</option>
            {filteredDoctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name} — qarz ${Number(d.debt_usd).toFixed(0)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Summa (so‘mda)">
          <input
            className="input text-right text-[18px] font-bold"
            inputMode="numeric"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </Field>
        {amount && fx ? (
          <div className="mb-3 text-[13px] text-[var(--muted)]">
            ≈ {usd(Number(amount.replace(/\s/g, '')) / Number(fx.usd_uzs))}
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
          <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <button
          className="btn btn-primary w-full"
          disabled={createPayment.isPending}
          onClick={submit}
        >
          {createPayment.isPending ? 'Saqlanmoqda…' : 'Tasdiqlash'}
        </button>
      </Sheet>
    </Screen>
  )
}
