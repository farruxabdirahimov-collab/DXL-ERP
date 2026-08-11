import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useCan } from '../App'
import {
  useAgentsReport,
  useDailyPreview,
  useDeadStock,
  useLowStock,
  useOutOfStock,
  useSalesByType,
  useSalesReport,
  useSizeDemand,
  useTopProducts,
} from '../api/hooks'
import { api } from '../api/client'
import { monthStartISO, num, todayISO, usd } from '../lib/format'
import {
  Card,
  Empty,
  Loading,
  Row,
  Screen,
  Section,
  Stat,
  Tabs,
} from '../components/ui'

const TABS = [
  { key: 'sales', label: 'Sotuv' },
  { key: 'top', label: 'Ko‘p sotilgan' },
  { key: 'sizes', label: 'Razmerlar' },
  { key: 'least', label: 'Kam sotilgan' },
  { key: 'low', label: 'Kam qolgan' },
  { key: 'dead', label: 'O‘lik zaxira' },
  { key: 'agents', label: 'Agentlar' },
  { key: 'daily', label: 'Kunlik matn' },
]

export default function Reports() {
  const can = useCan()
  const [tab, setTab] = useState('sales')
  const [from, setFrom] = useState(monthStartISO())
  const [to, setTo] = useState(todayISO())

  const range = useMemo(() => ({ date_from: from, date_to: to }), [from, to])

  const sales = useSalesReport(range)
  const top = useTopProducts(range, false)
  const least = useTopProducts(range, true)
  const sizes = useSizeDemand(range)
  const types = useSalesByType(range)
  const low = useLowStock()
  const out = useOutOfStock()
  const dead = useDeadStock()
  const agents = useAgentsReport(range)
  const daily = useDailyPreview()

  const exportKind: Record<string, string> = {
    top: 'top',
    sizes: 'sizes',
    least: 'top',
    low: 'low',
    dead: 'dead',
    agents: 'agents',
  }

  return (
    <Screen title="Hisobotlar" subtitle="Sotuv, mahsulot va agentlar tahlili">
      <div className="mb-3 grid grid-cols-2 gap-2">
        <div>
          <label className="label">Dan</label>
          <input
            className="input"
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div>
          <label className="label">Gacha</label>
          <input
            className="input"
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </div>
      </div>

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {exportKind[tab] ? (
        <button
          className="btn btn-sm mb-3 w-full"
          onClick={() =>
            api.download('/reports/export.xlsx', {
              kind: exportKind[tab],
              date_from: from,
              date_to: to,
            })
          }
        >
          ⬇️ Excel’ga yuklash
        </button>
      ) : null}

      {tab === 'sales' ? (
        <>
          {sales.isLoading ? <Loading /> : null}
          {sales.data ? (
            <>
              <div className="mb-4 grid grid-cols-2 gap-2">
                <Stat
                  label="Sotuv summasi"
                  value={usd(sales.data.summary.amount_usd)}
                  tone="accent"
                />
                <Stat label="Sotilgan dona" value={num(sales.data.summary.units)} />
                <Stat label="Buyurtmalar" value={num(sales.data.summary.orders)} />
                <Stat
                  label="Yig‘ilgan pul"
                  value={usd(sales.data.summary.collected_usd)}
                  tone="ok"
                />
              </div>

              {Number(sales.data.summary.returns_count) > 0 ? (
                <Section title="Qaytarish hisobga olindi">
                  <Card className="p-0">
                    <Row
                      title="Jami sotildi"
                      subtitle={`${num(sales.data.summary.gross_units)} dona`}
                      right={usd(sales.data.summary.gross_amount_usd)}
                    />
                    <Row
                      title="Qaytarildi"
                      subtitle={`${num(sales.data.summary.returned_units)} dona · ${num(
                        sales.data.summary.returns_count,
                      )} ta hujjat`}
                      right={`− ${usd(sales.data.summary.returned_usd)}`}
                    />
                    <Row
                      title="Sof sotuv"
                      subtitle={`${num(sales.data.summary.units)} dona`}
                      right={usd(sales.data.summary.amount_usd)}
                    />
                  </Card>
                  <p className="mt-2 px-1 text-xs text-slate-500">
                    Yuqoridagi barcha raqamlar — sof sotuv. Qaytarilgan tovar
                    hech qaysi hisobotda sotilgan bo‘lib qolmaydi.
                  </p>
                </Section>
              ) : null}

              <Section title="Kategoriya bo‘yicha">
                <Card className="p-0">
                  {(sales.data.by_category ?? []).map((row: any) => (
                    <Row
                      key={row.category}
                      title={row.category}
                      subtitle={`${num(row.qty)} dona`}
                      right={usd(row.amount_usd)}
                    />
                  ))}
                  {!sales.data.by_category?.length ? <Empty /> : null}
                </Card>
              </Section>

              <Section title="Implant turi bo‘yicha">
                <Card className="p-0">
                  {(types.data ?? []).map((row) => (
                    <Row
                      key={row.implant_type}
                      title={row.implant_type}
                      subtitle={`${num(row.qty)} dona`}
                      right={usd(row.amount_usd)}
                    />
                  ))}
                  {!types.data?.length ? <Empty /> : null}
                </Card>
              </Section>
            </>
          ) : null}
        </>
      ) : null}

      {tab === 'top' || tab === 'least' ? (
        <ProductList
          loading={tab === 'top' ? top.isLoading : least.isLoading}
          rows={(tab === 'top' ? top.data : least.data) ?? []}
        />
      ) : null}

      {tab === 'sizes' ? (
        <>
          {sizes.isLoading ? <Loading /> : null}
          {sizes.data && sizes.data.length > 0 ? (
            <>
              <Card className="mb-3 pb-1 pl-0 pr-1">
                <div style={{ height: 220 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={sizes.data.slice(0, 12).map((s) => ({
                        size: s.size,
                        dona: s.qty,
                      }))}
                      margin={{ top: 8, right: 8, bottom: 30, left: 0 }}
                    >
                      <XAxis
                        dataKey="size"
                        tick={{ fontSize: 10, fill: 'var(--muted)' }}
                        angle={-45}
                        textAnchor="end"
                        height={50}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 10, fill: 'var(--muted)' }}
                        tickLine={false}
                        axisLine={false}
                        width={32}
                      />
                      <Tooltip
                        contentStyle={{
                          background: 'var(--card)',
                          border: '1px solid var(--border)',
                          borderRadius: 10,
                          fontSize: 12,
                          color: 'var(--text)',
                        }}
                        formatter={(value: number) => [`${value} dona`, 'Sotilgan']}
                      />
                      <Bar dataKey="dona" radius={[6, 6, 0, 0]}>
                        {sizes.data.slice(0, 12).map((_, index) => (
                          <Cell
                            key={index}
                            fill={index < 3 ? 'var(--accent)' : 'var(--muted)'}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Card>
              <Card className="p-0">
                {sizes.data.map((row, index) => (
                  <Row
                    key={row.size}
                    title={`${index + 1}. ${row.size} mm`}
                    subtitle={`Ø${row.diameter_mm} × ${row.length_mm} mm`}
                    right={`${num(row.qty)} dona`}
                    rightSub={usd(row.amount_usd)}
                  />
                ))}
              </Card>
            </>
          ) : (
            <Empty text="Bu davrda sotuv bo‘lmagan" />
          )}
        </>
      ) : null}

      {tab === 'low' ? (
        <>
          {out.data && out.data.length > 0 ? (
            <Section title={`❌ Tugagan (${out.data.length})`}>
              <Card className="p-0">
                {out.data.map((row) => (
                  <Row
                    key={row.product_id}
                    title={row.name}
                    subtitle={`${row.sku}${row.avg_daily ? ` · kunlik sarf ${row.avg_daily}` : ''}`}
                    right="0"
                    rightSub={`min ${num(row.min_stock)}`}
                  />
                ))}
              </Card>
            </Section>
          ) : null}
          <Section title={`🔔 Kam qolgan (${low.data?.length ?? 0})`}>
            <Card className="p-0">
              {(low.data ?? []).map((row) => (
                <Row
                  key={row.product_id}
                  title={row.name}
                  subtitle={`${row.sku} · min ${num(row.min_stock)}${
                    row.days_left != null ? ` · ~${row.days_left} kunga yetadi` : ''
                  }`}
                  right={
                    <span style={{ color: row.qty === 0 ? 'var(--danger)' : 'var(--warn)' }}>
                      {num(row.qty)}
                    </span>
                  }
                  rightSub={row.shortage ? `−${num(row.shortage)}` : undefined}
                />
              ))}
              {!low.data?.length ? <Empty text="Hammasi yetarli 👍" /> : null}
            </Card>
          </Section>
        </>
      ) : null}

      {tab === 'dead' ? (
        <>
          {dead.isLoading ? <Loading /> : null}
          <Card className="p-0">
            {(dead.data ?? []).map((row) => (
              <Row
                key={row.product_id}
                title={row.name}
                subtitle={`${row.sku}${
                  row.days_idle != null
                    ? ` · ${row.days_idle} kundan beri sotilmagan`
                    : ' · hech sotilmagan'
                }`}
                right={`${num(row.qty)} dona`}
                rightSub={usd(row.value_usd, 0)}
              />
            ))}
            {!dead.data?.length ? <Empty text="O‘lik zaxira yo‘q 👍" /> : null}
          </Card>
        </>
      ) : null}

      {tab === 'agents' ? (
        <>
          {agents.isLoading ? <Loading /> : null}
          <Card className="p-0">
            {(agents.data ?? []).map((row: any, index: number) => (
              <Row
                key={row.user_id}
                title={`${index + 1}. ${row.full_name}`}
                subtitle={`${num(row.doctors)} vrach · ${num(row.units)} dona · ${num(row.orders)} buyurtma`}
                right={usd(row.amount_usd)}
                rightSub={`yig‘ilgan ${usd(row.collected_usd)}`}
              />
            ))}
            {!agents.data?.length ? <Empty /> : null}
          </Card>
        </>
      ) : null}

      {tab === 'daily' ? (
        <>
          {daily.isLoading ? <Loading /> : null}
          <Card>
            <div className="mb-2 text-[12px] text-[var(--muted)]">
              Har kuni soat 21:00 da shu matn Telegram orqali yuboriladi:
            </div>
            {/* Telegram HTML teglarini olib tashlab, oddiy matn sifatida ko'rsatamiz */}
            <div className="whitespace-pre-wrap text-[13px] leading-relaxed">
              {(daily.data?.text ?? '').replace(/<\/?[a-z]+>/gi, '')}
            </div>
          </Card>
        </>
      ) : null}
    </Screen>
  )
}

function ProductList({ loading, rows }: { loading: boolean; rows: any[] }) {
  if (loading) return <Loading />
  if (!rows.length) return <Empty text="Bu davrda sotuv bo‘lmagan" />
  return (
    <Card className="p-0">
      {rows.map((row, index) => (
        <Row
          key={row.product_id}
          title={`${index + 1}. ${row.name}`}
          subtitle={`${row.sku}${row.size && row.size !== '—' ? ` · ${row.size} mm` : ''}${
            row.implant_type ? ` · ${row.implant_type}` : ''
          }`}
          right={`${num(row.qty)} dona`}
          rightSub={usd(row.amount_usd)}
        />
      ))}
    </Card>
  )
}
