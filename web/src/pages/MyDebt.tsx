import { useMyDebt } from '../api/hooks'
import { shortDate, usd } from '../lib/format'
import {
  Card,
  Empty,
  ErrorBox,
  Loading,
  Row,
  Screen,
  Section,
  Stat,
} from '../components/ui'

export default function MyDebt() {
  const { data, isLoading, error } = useMyDebt()

  if (isLoading) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!data) return null

  const overdue = Number(data.overdue_usd) > 0

  return (
    <Screen title="Mening hisobim" subtitle="Qarz va to‘lov muddatlari">
      <div className="mb-4 grid grid-cols-2 gap-2">
        <Stat
          label="Umumiy qarz"
          value={usd(data.total_usd)}
          tone={overdue ? 'danger' : Number(data.total_usd) > 0 ? 'warn' : 'ok'}
        />
        <Stat
          label="Muddati o‘tgan"
          value={usd(data.overdue_usd)}
          tone={overdue ? 'danger' : 'ok'}
        />
        <Stat label="Muddati kelmagan" value={usd(data.not_due_usd)} />
        <Stat
          label="Qarz limiti"
          value={usd(data.debt_limit_usd, 0)}
          hint={`To‘lov muddati: ${data.payment_term_days} kun`}
        />
      </div>

      {overdue ? (
        <Card className="mb-4">
          <div className="text-[13px] font-semibold" style={{ color: 'var(--danger)' }}>
            ⚠️ Muddati o‘tgan qarzingiz bor
          </div>
          <div className="mt-1 text-[13px] text-[var(--muted)]">
            Yangi buyurtma berish uchun avval qarzni yopishingiz kerak bo‘lishi mumkin.
            Agentingiz bilan bog‘laning.
          </div>
        </Card>
      ) : null}

      <Section title="To‘lanmagan buyurtmalar">
        <Card className="p-0">
          {(data.orders ?? []).map((order: any) => (
            <Row
              key={order.number}
              title={order.number}
              subtitle={`Yetkazilgan: ${shortDate(order.delivered_at)} · muddat: ${shortDate(order.due_date)}`}
              right={
                <span
                  style={{ color: order.overdue_days > 0 ? 'var(--danger)' : undefined }}
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
    </Screen>
  )
}
