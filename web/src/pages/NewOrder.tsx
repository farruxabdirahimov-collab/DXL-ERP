import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useCurrentUser } from '../App'
import {
  useCreateOrder,
  useDoctors,
  useFxRate,
  useProducts,
} from '../api/hooks'
import { num, usd, uzs } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Empty,
  Field,
  Loading,
  Row,
  Screen,
  Section,
  Sheet,
} from '../components/ui'

interface CartLine {
  product_id: number
  name: string
  sku: string
  price: number
  available: number
  qty: number
}

export default function NewOrder() {
  const me = useCurrentUser()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const isDoctor = me.role === 'doctor'
  const [doctorId, setDoctorId] = useState<number | undefined>(
    searchParams.get('doctor') ? Number(searchParams.get('doctor')) : undefined,
  )
  const [search, setSearch] = useState('')
  const [cart, setCart] = useState<CartLine[]>([])
  const [discount, setDiscount] = useState('0')
  const [comment, setComment] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)

  const { data: doctors } = useDoctors({ limit: 500 })
  const { data: products, isLoading } = useProducts({
    search: search || undefined,
    in_stock: true,
    limit: 60,
  })
  const { data: fx } = useFxRate()
  const createOrder = useCreateOrder()

  const doctor = doctors?.find((d) => d.id === doctorId)

  const subtotal = useMemo(
    () => cart.reduce((sum, line) => sum + line.price * line.qty, 0),
    [cart],
  )
  const discountPct = Number(discount) || 0
  const total = subtotal * (1 - discountPct / 100)

  function add(product: {
    id: number
    name: string
    sku: string
    price_usd: string
    available: number
  }) {
    setCart((prev) => {
      const existing = prev.find((l) => l.product_id === product.id)
      if (existing) {
        return prev.map((l) =>
          l.product_id === product.id ? { ...l, qty: l.qty + 1 } : l,
        )
      }
      return [
        ...prev,
        {
          product_id: product.id,
          name: product.name,
          sku: product.sku,
          price: Number(product.price_usd),
          available: product.available,
          qty: 1,
        },
      ]
    })
    haptic('light')
  }

  function setQty(productId: number, qty: number) {
    setCart((prev) =>
      qty <= 0
        ? prev.filter((l) => l.product_id !== productId)
        : prev.map((l) => (l.product_id === productId ? { ...l, qty } : l)),
    )
  }

  async function submit() {
    if (!isDoctor && !doctorId) {
      alertUser('Vrachni tanlang')
      return
    }
    if (cart.length === 0) {
      alertUser('Savat bo‘sh')
      return
    }
    try {
      const order = await createOrder.mutateAsync({
        doctor_id: isDoctor ? undefined : doctorId,
        discount_pct: discountPct,
        comment: comment || null,
        lines: cart.map((l) => ({ product_id: l.product_id, qty: l.qty })),
      })
      haptic('success')
      navigate(`/orders/${order.id}`)
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Buyurtma yaratilmadi')
    }
  }

  return (
    <Screen
      title="Yangi buyurtma"
      subtitle={
        doctor
          ? `${doctor.full_name} · qarz ${usd(doctor.debt_usd)} / limit ${usd(doctor.debt_limit_usd, 0)}`
          : isDoctor
            ? me.full_name
            : 'Vrachni tanlang'
      }
    >
      {!isDoctor ? (
        <Field label="Vrach">
          <button
            className="input flex items-center justify-between text-left"
            onClick={() => setPickerOpen(true)}
          >
            <span>{doctor ? doctor.full_name : 'Tanlash…'}</span>
            <span className="text-[var(--muted)]">▾</span>
          </button>
        </Field>
      ) : null}

      {doctor && Number(doctor.overdue_usd) > 0 ? (
        <Card className="mb-3" >
          <div className="text-[13px] font-semibold" style={{ color: 'var(--danger)' }}>
            ⚠️ Bu vrachning muddati o‘tgan qarzi bor: {usd(doctor.overdue_usd)}
          </div>
          <div className="mt-1 text-[12px] text-[var(--muted)]">
            Buyurtma direktor tasdig‘iga yuboriladi.
          </div>
        </Card>
      ) : null}

      <Field label="Mahsulot qidirish">
        <input
          className="input"
          placeholder="Nomi, razmer yoki SKU…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Field>

      {isLoading ? <Loading /> : null}

      {search ? (
        <Card className="mb-3 max-h-72 overflow-y-auto p-0">
          {(products ?? []).map((product) => (
            <Row
              key={product.id}
              title={product.name}
              subtitle={`${product.sku} · bo‘sh ${num(product.available)} dona`}
              right={usd(product.price_usd)}
              rightSub="qo‘shish +"
              onClick={() => add(product)}
            />
          ))}
          {products?.length === 0 ? <Empty text="Topilmadi" /> : null}
        </Card>
      ) : null}

      <Section title={`Savat (${cart.length})`}>
        {cart.length === 0 ? (
          <Empty text="Savat bo‘sh — mahsulot qidirib qo‘shing" />
        ) : (
          <Card className="p-0">
            {cart.map((line) => (
              <div
                key={line.product_id}
                className="border-b border-[var(--border)] p-3 last:border-b-0"
              >
                <div className="mb-2 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-semibold">{line.name}</div>
                    <div className="text-[12px] text-[var(--muted)]">
                      {line.sku} · {usd(line.price)} × {line.qty}
                    </div>
                  </div>
                  <div className="text-[14px] font-bold">{usd(line.price * line.qty)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    className="btn btn-sm"
                    onClick={() => setQty(line.product_id, line.qty - 1)}
                  >
                    −
                  </button>
                  <input
                    className="input w-20 shrink-0 text-center"
                    inputMode="numeric"
                    value={line.qty}
                    onChange={(e) => setQty(line.product_id, Number(e.target.value))}
                  />
                  <button
                    className="btn btn-sm"
                    onClick={() => setQty(line.product_id, line.qty + 1)}
                  >
                    +
                  </button>
                  <span className="ml-auto text-[12px] text-[var(--muted)]">
                    bo‘sh: {num(line.available)}
                  </span>
                </div>
              </div>
            ))}
          </Card>
        )}
      </Section>

      {!isDoctor ? (
        <Field label="Chegirma (%)" hint="Limitdan oshsa direktor tasdiqlaydi">
          <input
            className="input"
            inputMode="decimal"
            value={discount}
            onChange={(e) => setDiscount(e.target.value)}
          />
        </Field>
      ) : null}

      <Field label="Izoh">
        <textarea
          className="textarea"
          rows={2}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
      </Field>

      <Card className="mb-3">
        <div className="flex items-center justify-between text-[14px]">
          <span className="text-[var(--muted)]">Jami</span>
          <span>{usd(subtotal)}</span>
        </div>
        {discountPct > 0 ? (
          <div className="mt-1 flex items-center justify-between text-[14px]">
            <span className="text-[var(--muted)]">Chegirma {discountPct}%</span>
            <span>−{usd(subtotal - total)}</span>
          </div>
        ) : null}
        <div className="mt-2 flex items-center justify-between border-t border-[var(--border)] pt-2 text-[17px] font-bold">
          <span>To‘lash uchun</span>
          <span>{usd(total)}</span>
        </div>
        {fx ? (
          <div className="mt-1 text-right text-[12px] text-[var(--muted)]">
            ≈ {uzs(total * Number(fx.usd_uzs))}
          </div>
        ) : null}
      </Card>

      <button
        className="btn btn-primary w-full"
        disabled={createOrder.isPending || cart.length === 0}
        onClick={submit}
      >
        {createOrder.isPending ? 'Yuborilmoqda…' : 'Buyurtmani yuborish'}
      </button>

      <Sheet open={pickerOpen} title="Vrachni tanlang" onClose={() => setPickerOpen(false)}>
        <Card className="max-h-[60vh] overflow-y-auto p-0">
          {(doctors ?? []).map((d) => (
            <Row
              key={d.id}
              title={d.full_name}
              subtitle={`${d.clinic_name ?? d.phone} · qarz ${usd(d.debt_usd)}`}
              onClick={() => {
                setDoctorId(d.id)
                setPickerOpen(false)
              }}
            />
          ))}
        </Card>
      </Sheet>
    </Screen>
  )
}
