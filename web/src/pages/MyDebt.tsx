import { useState } from 'react'
import { useContracts, useMyDebt, useMyPurchases, usePayments } from '../api/hooks'
import { CATEGORY_LABELS, dateTime, num, shortDate, usd, uzs } from '../lib/format'
import Countdown from '../components/Countdown'
import {
  Card,
  Chip,
  Empty,
  ErrorBox,
  Loading,
  Progress,
  Row,
  Screen,
  Section,
  Stat,
  Tabs,
} from '../components/ui'

const METHODS: Record<string, string> = {
  cash: 'Naqd',
  card: 'Karta',
  transfer: 'O‘tkazma',
}

export default function MyDebt() {
  const [tab, setTab] = useState('debt')
  const { data, isLoading, error } = useMyDebt()
  const { data: payments } = usePayments({ limit: 100 })
  const { data: purchases } = useMyPurchases()
  const { data: contracts } = useContracts({ status: 'active' })

  if (isLoading) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!data) return null

  const overdue = Number(data.overdue_usd) > 0
  const paidTotal = (payments ?? []).reduce((sum, p) => sum + Number(p.amount_usd), 0)

  return (
    <Screen
      title="Mening hisobim"
      subtitle={
        purchases
          ? `${purchases.clinic_name ?? ''} · ${CATEGORY_LABELS[purchases.category] ?? ''}`
          : undefined
      }
    >
      <div className="mb-3 grid grid-cols-2 gap-2">
        <Stat
          label="Qarzim"
          value={usd(data.total_usd)}
          tone={overdue ? 'danger' : Number(data.total_usd) > 0 ? 'warn' : 'ok'}
        />
        <Stat
          label="Muddati o‘tgan"
          value={usd(data.overdue_usd)}
          tone={overdue ? 'danger' : 'ok'}
        />
      </div>

      {/* Teskari sanoq — vrachning asosiy harakati shu yerdan boshlanadi.
          Sovg'aning pul qiymati ko'rsatilmaydi, faqat nomi. */}
      {(contracts ?? []).map((c: any) => (
        <Card key={c.id} className="mb-3 p-4 text-center">
          <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
            {c.tariff_name} · {c.number}
          </div>

          <div className="my-3">
            <Countdown deadline={c.deadline_at} serverNow={c.server_now} />
          </div>

          <Progress percent={c.paid_pct} height={10} />
          <div className="mt-1 flex justify-between text-[12px] text-[var(--muted)]">
            <span>
              To‘langan {usd(c.paid_usd)} / {usd(c.package_price_usd)}
            </span>
            <span>{Math.round(c.paid_pct)}%</span>
          </div>

          {Number(c.remaining_usd) > 0 ? (
            <div className="mt-3 rounded-xl bg-[var(--bg-soft)] p-3">
              <div className="text-[13px] text-[var(--muted)]">
                Sovg‘ani olish uchun
              </div>
              <div className="text-[22px] font-bold">{usd(c.remaining_usd)}</div>
              {c.gift_name ? (
                <div className="mt-1 text-[14px]">🎁 {c.gift_name}</div>
              ) : null}
            </div>
          ) : (
            <div className="mt-3 text-[14px] font-semibold text-[var(--ok)]">
              ✅ To‘liq to‘landi
              {c.gift_name ? ` — sovg‘angiz: ${c.gift_name}` : ''}
            </div>
          )}
        </Card>
      ))}

      {overdue ? (
        <Card className="mb-3">
          <div className="text-[13px] font-semibold" style={{ color: 'var(--danger)' }}>
            ⚠️ Muddati o‘tgan qarzingiz bor
          </div>
          <div className="mt-1 text-[13px] text-[var(--muted)]">
            Yangi buyurtma berish uchun avval qarzni yopishingiz kerak bo‘lishi
            mumkin. Agentingiz bilan bog‘laning.
          </div>
        </Card>
      ) : null}

      <Tabs
        tabs={[
          { key: 'debt', label: 'Qarzim' },
          { key: 'payments', label: `To‘lovlarim (${payments?.length ?? 0})` },
          { key: 'purchases', label: 'Xaridlarim' },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === 'debt' ? (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <Stat label="Muddati kelmagan" value={usd(data.not_due_usd)} />
            <Stat
              label="Qarz limitim"
              value={usd(data.debt_limit_usd, 0)}
              hint={`To‘lov muddati: ${data.payment_term_days} kun`}
            />
          </div>
          <Section title="To‘lanmagan buyurtmalar">
            <Card className="p-0">
              {(data.orders ?? []).map((order: any) => (
                <Row
                  key={order.number}
                  title={order.number}
                  subtitle={`Yetkazilgan: ${shortDate(order.delivered_at)} · muddat: ${shortDate(order.due_date)}`}
                  right={
                    <span
                      style={{
                        color: order.overdue_days > 0 ? 'var(--danger)' : undefined,
                      }}
                    >
                      {usd(order.debt_usd)}
                    </span>
                  }
                  rightSub={
                    order.overdue_days > 0
                      ? `${order.overdue_days} kun kechikdi`
                      : `jami ${usd(order.total_usd)}`
                  }
                />
              ))}
              {!data.orders?.length ? <Empty text="Qarzingiz yo‘q 🎉" /> : null}
            </Card>
          </Section>
        </>
      ) : null}

      {tab === 'payments' ? (
        <>
          <div className="mb-3">
            <Stat label="Jami to‘laganman" value={usd(paidTotal)} tone="ok" />
          </div>
          <Card className="p-0">
            {(payments ?? []).map((payment) => (
              <Row
                key={payment.id}
                title={uzs(payment.amount_uzs)}
                subtitle={`${METHODS[payment.method] ?? payment.method} · ${dateTime(payment.paid_at)}${
                  payment.order_number ? ` · ${payment.order_number}` : ''
                }`}
                right={usd(payment.amount_usd)}
                rightSub={`kurs ${num(payment.fx_rate)}`}
              />
            ))}
            {!payments?.length ? <Empty text="To‘lov tarixi bo‘sh" /> : null}
          </Card>
        </>
      ) : null}

      {tab === 'purchases' && purchases ? (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2">
            <Stat
              label="Jami xarid"
              value={usd(purchases.total_usd)}
              hint={`${num(purchases.orders)} buyurtma`}
              tone="accent"
            />
            <Stat
              label="Shu oyda"
              value={usd(purchases.month_usd)}
              hint={`${num(purchases.units)} dona (jami)`}
            />
          </div>

          <Card className="mb-3">
            <div className="flex flex-wrap gap-1.5">
              <Chip>{CATEGORY_LABELS[purchases.category] ?? purchases.category}</Chip>
              <Chip>⭐ Sodiqlik {purchases.loyalty_score}/100</Chip>
              {purchases.last_order_at ? (
                <Chip>Oxirgi xarid: {shortDate(purchases.last_order_at)}</Chip>
              ) : null}
            </div>
          </Card>

          <Section title="Eng ko‘p olgan mahsulotlarim">
            <Card className="p-0">
              {purchases.top_products.map((product, index) => (
                <Row
                  key={product.sku}
                  title={`${index + 1}. ${product.name}`}
                  subtitle={product.sku}
                  right={`${num(product.qty)} dona`}
                  rightSub={usd(product.amount_usd)}
                />
              ))}
              {purchases.top_products.length === 0 ? (
                <Empty text="Hali xarid qilmagansiz" />
              ) : null}
            </Card>
          </Section>
        </>
      ) : null}
    </Screen>
  )
}
