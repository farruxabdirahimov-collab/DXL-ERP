import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useCan, useCurrentUser } from '../App'
import { useCreateReturn, useOrder, useOrderAction } from '../api/hooks'
import { api } from '../api/client'
import { STATUS_COLORS, dateTime, num, shortDate, usd, uzs } from '../lib/format'
import { alertUser, confirmUser, haptic } from '../lib/telegram'
import {
  Card,
  Chip,
  ErrorBox,
  Loading,
  Row,
  Screen,
  Section,
  Sheet,
  Field,
} from '../components/ui'

export default function OrderPage() {
  const { id } = useParams()
  const orderId = Number(id)
  const navigate = useNavigate()
  const me = useCurrentUser()
  const can = useCan()

  const { data: order, isLoading, error } = useOrder(orderId)
  const action = useOrderAction()
  const [cancelOpen, setCancelOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [returnOpen, setReturnOpen] = useState(false)
  const [returnQty, setReturnQty] = useState<Record<number, number>>({})
  const [returnReason, setReturnReason] = useState('')
  const createReturn = useCreateReturn()

  if (isLoading) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!order) return null

  async function run(name: string, confirmText?: string) {
    if (confirmText && !(await confirmUser(confirmText))) return
    try {
      await action.mutateAsync({ id: orderId, action: name })
      haptic('success')
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  async function submitReturn() {
    const lines = Object.entries(returnQty)
      .filter(([, qty]) => qty > 0)
      .map(([productId, qty]) => ({ product_id: Number(productId), qty }))
    if (lines.length === 0) {
      alertUser('Nechta dona qaytarilayotganini kiriting')
      return
    }
    if (!returnReason.trim()) {
      alertUser('Qaytarish sababini yozing')
      return
    }
    try {
      const result = await createReturn.mutateAsync({
        doctor_id: order!.doctor_id,
        order_id: order!.id,
        reason: returnReason,
        lines,
      })
      haptic('success')
      alertUser(result.message ?? 'Qaytarish rasmiylashtirildi')
      setReturnOpen(false)
      setReturnQty({})
      setReturnReason('')
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  async function cancel() {
    try {
      await action.mutateAsync({
        id: orderId,
        action: 'cancel',
        body: { reason: reason || null },
      })
      haptic('success')
      setCancelOpen(false)
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  const canApprove =
    can('orders.approve') &&
    (order.status === 'new' ||
      (order.status === 'director_review' && can('orders.director')))
  const canFulfill = can('orders.fulfill')
  const isOpen = !['delivered', 'cancelled', 'rejected'].includes(order.status)

  return (
    <Screen
      title={order.number}
      subtitle={
        <>
          {order.doctor_name} · {dateTime(order.created_at)}
        </>
      }
      action={
        <button
          className="btn btn-sm"
          onClick={() => api.download(`/orders/${orderId}/invoice.pdf`)}
        >
          📄 PDF
        </button>
      }
    >
      <div className="mb-3 flex flex-wrap gap-1.5">
        <Chip color={STATUS_COLORS[order.status]}>
          {order.status_label ?? order.status}
        </Chip>
        <Chip>{order.source === 'doctor' ? 'Vrach bergan' : 'Agent kiritgan'}</Chip>
        {order.warehouse_name ? <Chip>📦 {order.warehouse_name}</Chip> : null}
        {order.agent_name ? <Chip>👤 {order.agent_name}</Chip> : null}
      </div>

      {order.needs_director && order.director_reason ? (
        <Card
          className="mb-3"
          // Direktor tasdig'i talab qilinishining sababi
        >
          <div className="text-[13px] font-semibold" style={{ color: 'var(--warn)' }}>
            ⚠️ Direktor tasdig‘i kerak
          </div>
          <div className="mt-1 text-[13px]">{order.director_reason}</div>
        </Card>
      ) : null}

      <Section title="Mahsulotlar">
        <Card className="p-0">
          {order.items.map((item) => (
            <Row
              key={item.id}
              title={item.product_name ?? `#${item.product_id}`}
              subtitle={`${item.sku ?? ''}${item.size && item.size !== '—' ? ` · ${item.size}` : ''} · ${num(item.qty)} × ${usd(item.price_usd)}${
                Number(item.discount_pct) > 0 ? ` · −${Number(item.discount_pct)}%` : ''
              }`}
              right={usd(item.line_total_usd)}
            />
          ))}
        </Card>
      </Section>

      <Section title="Hisob">
        <Card className="p-0">
          <Row title="Jami" right={usd(order.subtotal_usd)} />
          {Number(order.discount_usd) > 0 ? (
            <Row
              title={`Chegirma (${Number(order.discount_pct)}%)`}
              right={`−${usd(order.discount_usd)}`}
            />
          ) : null}
          <Row title="To‘lash uchun" right={usd(order.total_usd)} />
          <Row
            title="So‘mda"
            subtitle={`kurs ${num(order.fx_rate)}`}
            right={uzs(order.total_uzs ?? 0)}
          />
          {order.status === 'delivered' ? (
            <>
              <Row title="To‘langan" right={usd(order.paid_usd)} />
              {Number(order.returned_usd) > 0 ? (
                <Row title="Qaytarilgan" right={usd(order.returned_usd)} />
              ) : null}
              <Row
                title="Qolgan qarz"
                subtitle={`Muddat: ${shortDate(order.due_date)}`}
                right={
                  <span
                    style={{
                      color: Number(order.debt_usd) > 0 ? 'var(--danger)' : 'var(--ok)',
                    }}
                  >
                    {usd(order.debt_usd)}
                  </span>
                }
              />
            </>
          ) : null}
        </Card>
      </Section>

      {order.comment ? (
        <Section title="Izoh">
          <Card>
            <p className="text-[13px]">{order.comment}</p>
          </Card>
        </Section>
      ) : null}

      <div className="space-y-2">
        {canApprove ? (
          <button
            className="btn btn-primary w-full"
            disabled={action.isPending}
            onClick={() => run('approve')}
          >
            ✅ Tasdiqlash
          </button>
        ) : null}

        {canFulfill && order.status === 'approved' ? (
          <button className="btn w-full" onClick={() => run('picking')}>
            📦 Yig‘ishni boshlash
          </button>
        ) : null}

        {canFulfill && ['approved', 'picking'].includes(order.status) ? (
          <button className="btn w-full" onClick={() => run('ship')}>
            🚚 Jo‘natildi
          </button>
        ) : null}

        {canFulfill && ['approved', 'picking', 'shipped'].includes(order.status) ? (
          <button
            className="btn btn-primary w-full"
            onClick={() =>
              run(
                'deliver',
                'Yetkazilgan deb belgilaymizmi? Tovar ombordan yechiladi va vrachga qarz yoziladi.',
              )
            }
          >
            ✔️ Yetkazildi
          </button>
        ) : null}

        {order.status === 'delivered' && can('returns.create') ? (
          <button className="btn w-full" onClick={() => setReturnOpen(true)}>
            ↩️ Tovarni qaytarish (vozvrat)
          </button>
        ) : null}

        {isOpen ? (
          <button className="btn btn-danger w-full" onClick={() => setCancelOpen(true)}>
            ✕ Bekor qilish
          </button>
        ) : null}

        <button className="btn w-full" onClick={() => navigate('/orders')}>
          ← Ro‘yxatga qaytish
        </button>
      </div>

      <Sheet
        open={returnOpen}
        title="Tovarni qaytarish"
        onClose={() => setReturnOpen(false)}
      >
        <p className="mb-3 text-[13px] text-[var(--muted)]">
          Nechta dona qaytarilayotganini kiriting. Tovar omborga qaytadi,
          summa vrachning qarzidan ayiriladi va hisobotlardan chiqariladi.
        </p>

        <Card className="mb-3 p-0">
          {order.items.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-2 border-b border-[var(--border)] p-3 last:border-b-0"
            >
              <div className="min-w-0 flex-1">
                {/* Razmer nomning ichida — qisqartirmaymiz, ko'chirib yozamiz */}
                <div className="text-[13px] font-semibold leading-snug">
                  {item.product_name}
                </div>
                <div className="mt-0.5 text-[12px] text-[var(--muted)]">
                  Sotilgan: {item.qty} dona · {usd(item.price_usd)}
                </div>
              </div>
              <input
                className="input w-20 shrink-0 text-center"
                inputMode="numeric"
                placeholder="0"
                value={returnQty[item.product_id] ?? ''}
                onChange={(e) => {
                  const value = Math.min(item.qty, Math.max(0, Number(e.target.value) || 0))
                  setReturnQty({ ...returnQty, [item.product_id]: value })
                }}
              />
            </div>
          ))}
        </Card>

        <Field label="Sabab (majburiy)" hint="Masalan: qadoq shikastlangan, razmer mos kelmadi">
          <textarea
            className="textarea"
            rows={2}
            value={returnReason}
            onChange={(e) => setReturnReason(e.target.value)}
          />
        </Field>

        <button
          className="btn btn-primary w-full"
          disabled={createReturn.isPending}
          onClick={submitReturn}
        >
          {createReturn.isPending ? 'Rasmiylashtirilmoqda…' : '↩️ Qaytarishni tasdiqlash'}
        </button>
      </Sheet>

      <Sheet
        open={cancelOpen}
        title="Buyurtmani bekor qilish"
        onClose={() => setCancelOpen(false)}
      >
        <Field label="Sabab">
          <textarea
            className="textarea"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>
        <button className="btn btn-danger w-full" onClick={cancel}>
          Bekor qilishni tasdiqlash
        </button>
      </Sheet>
    </Screen>
  )
}
