import { useNavigate } from 'react-router-dom'
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useCurrentUser } from '../App'
import {
  useDashboard,
  useFxRate,
  useMyPlan,
  useTasks,
  useTrend,
} from '../api/hooks'
import { num, shortDate, usd, uzs } from '../lib/format'
import {
  Card,
  ErrorBox,
  Loading,
  MetricBar,
  Row,
  Screen,
  Section,
  Stat,
} from '../components/ui'

const STATUS_LABELS: Record<string, string> = {
  new: 'Tasdiq kutmoqda',
  director_review: 'Direktor tasdig‘i',
  approved: 'Tasdiqlangan',
  picking: 'Yig‘ilmoqda',
  shipped: 'Yo‘lda',
}

export default function Dashboard() {
  const me = useCurrentUser()
  const navigate = useNavigate()
  const { data, isLoading, error } = useDashboard()
  const { data: trend } = useTrend(30)
  const { data: fx } = useFxRate()
  const { data: tasks } = useTasks()
  const isAgent = me.role === 'agent'
  const { data: plan } = useMyPlan()

  if (isLoading) return <Loading />
  if (error) return <ErrorBox error={error} />
  if (!data) return null

  const chartData = (trend ?? []).map((point) => ({
    date: point.date.slice(5),
    summa: Number(point.amount_usd),
  }))

  const pending = Object.entries(data.pending_orders ?? {})
  const scope = isAgent && data.my_month ? data.my_month : data.month

  return (
    <Screen
      title={`Salom, ${me.full_name.split(' ')[0]}!`}
      subtitle={`${me.role_label} · ${shortDate(data.date)}${
        fx ? ` · 1$ = ${num(fx.usd_uzs)} so'm` : ''
      }`}
    >
      <div className="mb-4 grid grid-cols-2 gap-2">
        <Stat
          label="Bugungi sotuv"
          value={usd(data.today.amount_usd)}
          hint={`${num(data.today.units)} dona · ${num(data.today.orders)} buyurtma`}
          tone="accent"
        />
        <Stat
          label="Bugun yig‘ilgan"
          value={usd(data.today.collected_usd)}
          hint={`${num(data.today.doctors)} vrach`}
          tone="ok"
        />
        <Stat
          label={isAgent ? 'Mening oyim' : 'Oy boshidan'}
          value={usd(scope.amount_usd)}
          hint={`${num(scope.units)} dona`}
        />
        <Stat
          label="Muddati o‘tgan qarz"
          value={usd(data.debt.overdue_usd)}
          hint={`Jami qarz: ${usd(data.debt.total_usd)}`}
          tone={Number(data.debt.overdue_usd) > 0 ? 'danger' : 'ok'}
        />
      </div>

      {isAgent && plan?.has_plan ? (
        <Section
          title="Oylik reja"
          action={
            <button className="btn btn-sm" onClick={() => navigate('/plan')}>
              Batafsil
            </button>
          }
        >
          <Card>
            <MetricBar
              label="💵 Sotuv summasi"
              fact={plan.amount.fact}
              target={plan.amount.target}
              percent={plan.amount.pct}
              unit="$"
            />
            <MetricBar
              label="📦 Sotilgan dona"
              fact={plan.units.fact}
              target={plan.units.target}
              percent={plan.units.pct}
            />
            <MetricBar
              label="💰 Yig‘ilgan pul"
              fact={plan.collection.fact}
              target={plan.collection.target}
              percent={plan.collection.pct}
              unit="$"
            />
            <div className="mt-1 text-[12px] text-[var(--muted)]">
              {plan.days_passed}/{plan.days_in_month} kun o‘tdi
              {plan.expected_pace_pct !== undefined
                ? ` · kutilgan temp ${plan.expected_pace_pct}%`
                : ''}
            </div>
          </Card>
        </Section>
      ) : null}

      {chartData.length > 0 ? (
        <Section title="Oxirgi 30 kun sotuvi">
          <Card className="pb-1 pl-0 pr-1">
            <div style={{ height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="sales" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: 'var(--muted)' }}
                    tickLine={false}
                    axisLine={false}
                    interval={5}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: 'var(--muted)' }}
                    tickLine={false}
                    axisLine={false}
                    width={44}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--card)',
                      border: '1px solid var(--border)',
                      borderRadius: 10,
                      fontSize: 12,
                      color: 'var(--text)',
                    }}
                    formatter={(value: number) => [usd(value), 'Sotuv']}
                  />
                  <Area
                    type="monotone"
                    dataKey="summa"
                    stroke="var(--accent)"
                    strokeWidth={2}
                    fill="url(#sales)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </Section>
      ) : null}

      {pending.length > 0 ? (
        <Section title="Jarayondagi buyurtmalar">
          <Card className="p-0">
            {pending.map(([status, count]) => (
              <Row
                key={status}
                title={STATUS_LABELS[status] ?? status}
                right={num(count)}
                onClick={() => navigate(`/orders?status=${status}`)}
              />
            ))}
          </Card>
        </Section>
      ) : null}

      <Section title="Ombor holati">
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Ombor qiymati" value={usd(data.stock_value_usd, 0)} />
          <Stat
            label="Kam qolgan"
            value={num(data.low_stock_count)}
            tone={data.low_stock_count > 0 ? 'warn' : 'ok'}
          />
          <Stat
            label="Tugagan"
            value={num(data.out_of_stock_count)}
            tone={data.out_of_stock_count > 0 ? 'danger' : 'ok'}
          />
        </div>
      </Section>

      {tasks && tasks.length > 0 ? (
        <Section
          title={`Vazifalar (${tasks.length})`}
          action={
            <button className="btn btn-sm" onClick={() => navigate('/tasks')}>
              Hammasi
            </button>
          }
        >
          <Card className="p-0">
            {tasks.slice(0, 4).map((task) => (
              <Row
                key={task.id}
                title={task.title}
                subtitle={`${task.kind_label ?? ''} · ${shortDate(task.due_date)}`}
                onClick={() => navigate('/tasks')}
              />
            ))}
          </Card>
        </Section>
      ) : null}

      {data.new_doctors_today > 0 ? (
        <div className="text-center text-[13px] text-[var(--muted)]">
          Bugun {num(data.new_doctors_today)} ta yangi vrach qo‘shildi
        </div>
      ) : null}
    </Screen>
  )
}
