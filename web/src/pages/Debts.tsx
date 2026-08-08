import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useCan } from '../App'
import { useDebtAging, useDebts } from '../api/hooks'
import { api } from '../api/client'
import { num, shortDate, usd } from '../lib/format'
import {
  Card,
  Chip,
  Empty,
  ErrorBox,
  Loading,
  Row,
  Screen,
  Section,
  Stat,
  Tabs,
} from '../components/ui'

const AGING_COLORS: Record<string, string> = {
  'muddati kelmagan': '#12a150',
  '0-30 kun': '#7bc043',
  '31-60 kun': '#f59e0b',
  '61-90 kun': '#f97316',
  '90+ kun': '#e5484d',
}

export default function Debts() {
  const navigate = useNavigate()
  const can = useCan()
  const [tab, setTab] = useState('all')
  const { data, isLoading, error } = useDebts(tab === 'overdue')
  const { data: aging } = useDebtAging()

  const total = (data ?? []).reduce((sum, r) => sum + Number(r.debt_usd), 0)
  const overdue = (data ?? []).reduce((sum, r) => sum + Number(r.overdue_usd), 0)

  const pieData = Object.entries(aging ?? {})
    .map(([name, value]) => ({ name, value: Number(value) }))
    .filter((d) => d.value > 0)

  return (
    <Screen
      title="Qarzdorlik"
      subtitle={`${data?.length ?? 0} ta vrach`}
      action={
        <button
          className="btn btn-sm"
          onClick={() => api.download('/reports/export.xlsx', { kind: 'debts' })}
        >
          ⬇️ Excel
        </button>
      }
    >
      <div className="mb-3 grid grid-cols-2 gap-2">
        <Stat label="Umumiy qarz" value={usd(total)} tone="warn" />
        <Stat
          label="Muddati o‘tgan"
          value={usd(overdue)}
          tone={overdue > 0 ? 'danger' : 'ok'}
        />
      </div>

      {can('reports.finance') && pieData.length > 0 ? (
        <Section title="Qarz yoshi">
          <Card>
            <div style={{ height: 180 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={44}
                    outerRadius={72}
                    paddingAngle={2}
                  >
                    {pieData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={AGING_COLORS[entry.name] ?? 'var(--accent)'}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: 'var(--card)',
                      border: '1px solid var(--border)',
                      borderRadius: 10,
                      fontSize: 12,
                      color: 'var(--text)',
                    }}
                    formatter={(value: number, name: string) => [usd(value), name]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 space-y-1">
              {pieData.map((entry) => (
                <div
                  key={entry.name}
                  className="flex items-center justify-between text-[13px]"
                >
                  <span className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: AGING_COLORS[entry.name] ?? 'var(--accent)' }}
                    />
                    {entry.name}
                  </span>
                  <span className="font-semibold">{usd(entry.value)}</span>
                </div>
              ))}
            </div>
          </Card>
        </Section>
      ) : null}

      <Tabs
        tabs={[
          { key: 'all', label: 'Barcha qarzdorlar' },
          { key: 'overdue', label: 'Muddati o‘tganlar' },
        ]}
        active={tab}
        onChange={setTab}
      />

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data?.length === 0 ? <Empty text="Qarzdor yo‘q 🎉" /> : null}

      <div className="space-y-2">
        {(data ?? []).map((row) => (
          <Card key={row.doctor_id} onClick={() => navigate(`/doctors/${row.doctor_id}`)}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="truncate text-[14px] font-semibold">{row.full_name}</div>
                <div className="truncate text-[12px] text-[var(--muted)]">
                  {row.clinic_name ?? row.phone}
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <Chip>{num(row.open_orders)} buyurtma</Chip>
                  {row.oldest_due_date ? (
                    <Chip color={row.overdue_days > 0 ? 'var(--danger)' : undefined}>
                      muddat {shortDate(row.oldest_due_date)}
                    </Chip>
                  ) : null}
                  {row.overdue_days > 0 ? (
                    <Chip color="var(--danger)">{row.overdue_days} kun kechikdi</Chip>
                  ) : null}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="text-[15px] font-bold">{usd(row.debt_usd)}</div>
                {Number(row.overdue_usd) > 0 ? (
                  <div className="text-[12px]" style={{ color: 'var(--danger)' }}>
                    {usd(row.overdue_usd)} muddati o‘tgan
                  </div>
                ) : (
                  <div className="text-[12px] text-[var(--muted)]">
                    limit {usd(row.debt_limit_usd, 0)}
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </Screen>
  )
}
