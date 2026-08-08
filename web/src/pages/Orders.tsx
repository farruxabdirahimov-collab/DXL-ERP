import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useCan, useCurrentUser } from '../App'
import { useOrders } from '../api/hooks'
import type { OrderStatus } from '../api/types'
import { STATUS_COLORS, shortDate, usd } from '../lib/format'
import { Card, Chip, Empty, ErrorBox, Loading, Screen, Tabs } from '../components/ui'

const TABS: { key: string; label: string; status?: OrderStatus }[] = [
  { key: 'open', label: 'Jarayonda' },
  { key: 'new', label: 'Tasdiq kutmoqda', status: 'new' },
  { key: 'director_review', label: 'Direktor tasdig‘i', status: 'director_review' },
  { key: 'approved', label: 'Tasdiqlangan', status: 'approved' },
  { key: 'delivered', label: 'Yetkazilgan', status: 'delivered' },
  { key: 'all', label: 'Hammasi' },
]

export default function Orders() {
  const navigate = useNavigate()
  const me = useCurrentUser()
  const can = useCan()
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState(searchParams.get('status') ?? 'open')

  const params = useMemo(() => {
    const found = TABS.find((t) => t.key === tab)
    if (tab === 'open') return { only_open: true }
    if (tab === 'all') return {}
    return { status: found?.status }
  }, [tab])

  const { data, isLoading, error } = useOrders(params)

  return (
    <Screen
      title={me.role === 'doctor' ? 'Buyurtmalarim' : 'Buyurtmalar'}
      subtitle={data ? `${data.length} ta` : undefined}
      action={
        can('orders.create') ? (
          <button
            className="btn btn-sm btn-primary"
            onClick={() => navigate('/new-order')}
          >
            + Yangi
          </button>
        ) : null
      }
    >
      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data && data.length === 0 ? <Empty text="Buyurtma yo‘q" /> : null}

      <div className="space-y-2">
        {(data ?? []).map((order) => (
          <Card key={order.id} onClick={() => navigate(`/orders/${order.id}`)}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[14px] font-semibold">{order.number}</div>
                <div className="truncate text-[12px] text-[var(--muted)]">
                  {order.doctor_name ?? '—'}
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <Chip color={STATUS_COLORS[order.status]}>
                    {order.status_label ?? order.status}
                  </Chip>
                  {order.needs_director && order.status === 'director_review' ? (
                    <Chip color="var(--danger)">⚠️ {order.director_reason}</Chip>
                  ) : null}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-[15px] font-bold">{usd(order.total_usd)}</div>
                <div className="text-[11px] text-[var(--muted)]">
                  {shortDate(order.created_at)}
                </div>
                {Number(order.debt_usd) > 0 && order.status === 'delivered' ? (
                  <div className="text-[11px]" style={{ color: 'var(--warn)' }}>
                    qarz {usd(order.debt_usd)}
                  </div>
                ) : null}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </Screen>
  )
}
