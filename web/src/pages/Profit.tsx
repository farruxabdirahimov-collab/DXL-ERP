import { useState } from 'react'
import { useCan } from '../App'
import {
  useCostStatus,
  useExpenseCategories,
  useExpenses,
  useProfit,
  useProfitAction,
} from '../api/hooks'
import { num, pct, shortDate, usd } from '../lib/format'
import { alertUser, confirmUser, haptic } from '../lib/telegram'
import {
  Card,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Row,
  Screen,
  Section,
  Stat,
  Sheet,
  Tabs,
} from '../components/ui'

const TABS = [
  { key: 'report', label: 'Foyda-zarar' },
  { key: 'expenses', label: 'Xarajatlar' },
  { key: 'cost', label: 'Tannarx' },
]

/** Hisobotdagi bitta qator — chapda nom, o'ngda summa. */
function Line({
  label,
  value,
  negative,
  bold,
  hint,
}: {
  label: string
  value: string
  negative?: boolean
  bold?: boolean
  hint?: string
}) {
  return (
    <div
      className={`flex items-baseline justify-between gap-3 py-1.5 ${
        bold ? 'border-t border-[var(--border)] pt-2.5 text-[15px] font-bold' : 'text-[14px]'
      }`}
    >
      <span className={bold ? '' : 'text-[var(--muted)]'}>
        {label}
        {hint ? (
          <span className="ml-1 text-[11px] text-[var(--muted)]">{hint}</span>
        ) : null}
      </span>
      <span className="shrink-0 tabular-nums">
        {negative ? '− ' : ''}
        {value}
      </span>
    </div>
  )
}

export default function Profit() {
  const can = useCan()
  const canEditCost = can('products.edit')
  const [tab, setTab] = useState('report')

  const report = useProfit()
  const costs = useCostStatus()
  const expenses = useExpenses()
  const { data: categories } = useExpenseCategories()
  const action = useProfitAction()

  const [costOpen, setCostOpen] = useState<{ id: number | null; name: string } | null>(
    null,
  )
  const [costValue, setCostValue] = useState('')
  const [overwrite, setOverwrite] = useState(false)

  const [expOpen, setExpOpen] = useState(false)
  const [form, setForm] = useState<Record<string, string>>({ category: 'rent' })
  const [monthly, setMonthly] = useState(true)
  const set = (k: string, v: string) => setForm({ ...form, [k]: v })

  async function ishga(args: Parameters<typeof action.mutateAsync>[0], ok = 'Bajarildi') {
    try {
      const r = await action.mutateAsync(args)
      haptic('success')
      alertUser(r.message ?? ok)
      return true
    } catch (e: any) {
      alertUser(e?.message ?? 'Bajarilmadi')
      return false
    }
  }

  const r = report.data

  return (
    <Screen title="Foyda-zarar" subtitle="Faqat rahbariyat va buxgalteriya">
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      {report.error ? <ErrorBox error={report.error} /> : null}

      {tab === 'report' ? (
        <>
          {report.isLoading ? <Loading /> : null}
          {r ? (
            <>
              {/* Tannarxsiz hisobot yolg'on chiqadi — birinchi navbatda shu */}
              {r.cost_missing ? (
                <Card className="mb-3 border-[var(--danger)] p-3">
                  <div className="text-[13px] font-semibold text-[var(--danger)]">
                    ⚠️ Tannarx kiritilmagan
                  </div>
                  <div className="mt-1 text-[12px] text-[var(--muted)]">
                    Tannarxsiz foyda haqiqiydan yuqori chiqadi. «Tannarx» bo‘limiga
                    o‘tib, bitta raqam bilan to‘ldiring.
                  </div>
                </Card>
              ) : null}

              <div className="mb-3 grid grid-cols-2 gap-2">
                <Stat
                  label="Sof foyda"
                  value={usd(r.net_profit_usd)}
                  hint={pct(r.net_margin_pct, 1)}
                  tone={Number(r.net_profit_usd) >= 0 ? 'ok' : 'danger'}
                />
                <Stat
                  label="Yalpi foyda"
                  value={usd(r.gross_profit_usd)}
                  hint={pct(r.gross_margin_pct, 1)}
                />
              </div>

              <Section title={`${r.month}/${r.year} hisoboti`}>
                <Card>
                  <Line label="Sotuv (sof)" value={usd(r.revenue_usd)} />
                  {Number(r.returned_usd) > 0 ? (
                    <Line
                      label="Qaytarilgan"
                      value={usd(r.returned_usd)}
                      hint="sotuvdan ayirilgan"
                    />
                  ) : null}
                  <Line label="Sotilgan tovar tannarxi" value={usd(r.cogs_usd)} negative />
                  <Line
                    label="YALPI FOYDA"
                    value={`${usd(r.gross_profit_usd)}  ·  ${pct(r.gross_margin_pct, 1)}`}
                    bold
                  />
                </Card>
              </Section>

              <Section title="Xarajatlar">
                <Card>
                  {(r.expenses ?? []).map((e: any) => (
                    <Line
                      key={e.category}
                      label={e.label}
                      value={usd(e.amount_usd)}
                      negative
                    />
                  ))}
                  {Number(r.writeoff_usd) > 0 ? (
                    <Line
                      label="Spisaniye (yaroqsiz tovar)"
                      value={usd(r.writeoff_usd)}
                      negative
                    />
                  ) : null}
                  {Number(r.gift_usd) > 0 ? (
                    <Line label="Sovg‘alar" value={usd(r.gift_usd)} negative />
                  ) : null}
                  {!r.expenses?.length &&
                  !Number(r.writeoff_usd) &&
                  !Number(r.gift_usd) ? (
                    <div className="py-2 text-[13px] text-[var(--muted)]">
                      Xarajat kiritilmagan
                    </div>
                  ) : null}
                  <Line
                    label="SOF FOYDA"
                    value={`${usd(r.net_profit_usd)}  ·  ${pct(r.net_margin_pct, 1)}`}
                    bold
                  />
                </Card>
              </Section>

              {/* Hisobda foyda bor, lekin pul qo'lga tekkanmi */}
              <Section title="Pul qayerda">
                <Card>
                  <Line label="Yig‘ilgan pul" value={usd(r.collected_usd)} />
                  <Line
                    label="Hali kelmagan (qarzda)"
                    value={usd(r.uncollected_usd)}
                    hint="sotildi, pul kelmadi"
                  />
                </Card>
              </Section>
            </>
          ) : null}
        </>
      ) : null}

      {tab === 'expenses' ? (
        <>
          <button className="btn btn-primary mb-3 w-full" onClick={() => setExpOpen(true)}>
            + Xarajat qo‘shish
          </button>
          <Card className="mb-3 p-3 text-[13px] text-[var(--muted)]">
            Ijara va oylik kabi <b>har oy takrorlanadigan</b> xarajatni bir marta
            kiriting — keyingi oylarda o‘zi hisobga olinadi.
          </Card>
          <Card className="p-0">
            {(expenses.data ?? []).map((e: any) => (
              <Row
                key={e.id}
                title={`${e.is_monthly ? '🔁 ' : ''}${e.label}`}
                subtitle={
                  e.is_monthly
                    ? `Har oy · ${shortDate(e.spent_on)} dan`
                    : shortDate(e.spent_on)
                }
                right={usd(e.amount_usd)}
                onClick={async () => {
                  if (!(await confirmUser(`«${e.label}» o‘chirilsinmi?`))) return
                  await ishga({ path: `/profit/expenses/${e.id}`, method: 'del' })
                }}
              />
            ))}
            {!expenses.isLoading && !expenses.data?.length ? (
              <Empty text="Xarajat kiritilmagan" />
            ) : null}
          </Card>
        </>
      ) : null}

      {tab === 'cost' ? (
        <>
          {costs.isLoading ? <Loading /> : null}
          <Card className="mb-3 p-3 text-[13px] text-[var(--muted)]">
            Implantlar razmeridan qat‘i nazar bir xil narxda — shuning uchun
            kategoriyani bosing va <b>bitta raqam</b> kiriting. Istisno bo‘lgan
            mahsulotni Katalogdan alohida tahrirlaysiz.
          </Card>
          {costs.data?.missing_total ? (
            <Card className="mb-3 border-[var(--warn)] p-3 text-[13px]">
              <b className="text-[var(--warn)]">
                {num(costs.data.missing_total)} ta mahsulotda tannarx yo‘q
              </b>
            </Card>
          ) : null}
          <Card className="p-0">
            {(costs.data?.categories ?? []).map((c: any) => (
              <Row
                key={c.category_id}
                title={c.name}
                subtitle={
                  c.missing
                    ? `${num(c.missing)} tasida tannarx yo‘q · jami ${num(c.products)} ta`
                    : `${num(c.products)} ta mahsulot`
                }
                right={c.same_cost != null ? usd(c.same_cost) : '—'}
                rightSub={c.missing ? 'to‘ldirish' : undefined}
                onClick={
                  canEditCost
                    ? () => {
                        setCostOpen({ id: c.category_id, name: c.name })
                        setCostValue(c.same_cost != null ? String(c.same_cost) : '')
                        setOverwrite(false)
                      }
                    : undefined
                }
              />
            ))}
          </Card>
        </>
      ) : null}

      <Sheet
        open={Boolean(costOpen)}
        title={costOpen ? `${costOpen.name} — tannarx` : ''}
        onClose={() => setCostOpen(null)}
      >
        <Field label="Bitta dona tannarxi ($)" hint="Bizga qanchaga tushadi">
          <input
            className="input"
            inputMode="decimal"
            value={costValue}
            onChange={(e) => setCostValue(e.target.value)}
          />
        </Field>
        <label className="mb-3 flex items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            checked={overwrite}
            onChange={(e) => setOverwrite(e.target.checked)}
          />
          Tannarxi borlarni ham qayta yozish
        </label>
        <button
          className="btn btn-primary w-full"
          disabled={!costValue || action.isPending}
          onClick={async () => {
            const ok = await ishga({
              path: '/profit/bulk-cost',
              body: {
                category_id: costOpen?.id,
                cost_usd: costValue,
                overwrite,
              },
            })
            if (ok) setCostOpen(null)
          }}
        >
          {action.isPending ? 'Saqlanmoqda…' : 'Qo‘yish'}
        </button>
      </Sheet>

      <Sheet open={expOpen} title="Xarajat qo‘shish" onClose={() => setExpOpen(false)}>
        <Field label="Turi">
          <select
            className="select"
            value={form.category}
            onChange={(e) => set('category', e.target.value)}
          >
            {(categories ?? []).map((c: any) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Summa ($)">
          <input
            className="input"
            inputMode="decimal"
            value={form.amount ?? ''}
            onChange={(e) => set('amount', e.target.value)}
          />
        </Field>
        <label className="mb-3 flex items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            checked={monthly}
            onChange={(e) => setMonthly(e.target.checked)}
          />
          Har oy takrorlanadi (ijara, oylik)
        </label>
        <button
          className="btn btn-primary w-full"
          disabled={!form.amount || action.isPending}
          onClick={async () => {
            const ok = await ishga({
              path: '/profit/expenses',
              body: {
                category: form.category,
                amount_usd: form.amount,
                spent_on: new Date().toISOString().slice(0, 10),
                is_monthly: monthly,
              },
            })
            if (ok) {
              setExpOpen(false)
              setForm({ category: 'rent' })
            }
          }}
        >
          {action.isPending ? 'Saqlanmoqda…' : 'Qo‘shish'}
        </button>
      </Sheet>
    </Screen>
  )
}
