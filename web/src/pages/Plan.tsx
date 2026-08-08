import { useState } from 'react'
import { useCan, useCurrentUser } from '../App'
import { useAgents, useAllPlans, useLeaderboard, useMyPlan, useSetPlan } from '../api/hooks'
import { num, pct, planColor, usd } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Empty,
  ErrorBox,
  Field,
  Loading,
  MetricBar,
  Progress,
  Screen,
  Section,
  Sheet,
  Stat,
  Tabs,
} from '../components/ui'

export default function Plan() {
  const me = useCurrentUser()
  const can = useCan()
  const canEdit = can('plans.edit')
  const [tab, setTab] = useState(me.role === 'agent' ? 'my' : 'board')
  const [editing, setEditing] = useState<{ user_id: number; full_name: string } | null>(
    null,
  )

  const myPlan = useMyPlan()
  const board = useLeaderboard()
  const all = useAllPlans()

  const tabs = [
    ...(me.role === 'agent' ? [{ key: 'my', label: 'Mening rejam' }] : []),
    { key: 'board', label: 'Reyting' },
    ...(canEdit ? [{ key: 'edit', label: 'Reja qo‘yish' }] : []),
  ]

  return (
    <Screen title="Oylik reja" subtitle="Sotuv · dona · yig‘ilgan pul">
      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === 'my' ? (
        <>
          {myPlan.isLoading ? <Loading /> : null}
          {myPlan.error ? <ErrorBox error={myPlan.error} /> : null}
          {myPlan.data && !myPlan.data.has_plan ? (
            <Empty text="Bu oyga reja belgilanmagan. Direktoringizdan so‘rang." />
          ) : null}
          {myPlan.data?.has_plan ? (
            <>
              <div className="mb-3 grid grid-cols-2 gap-2">
                <Stat
                  label="Umumiy bajarilish"
                  value={pct(myPlan.data.overall_pct, 0)}
                  hint={`${myPlan.data.days_passed}/${myPlan.data.days_in_month} kun`}
                  tone={myPlan.data.overall_pct >= 80 ? 'ok' : 'warn'}
                />
                <Stat
                  label="Kutilgan temp"
                  value={pct(myPlan.data.expected_pace_pct ?? 0, 0)}
                  hint={
                    (myPlan.data.expected_pace_pct ?? 0) > myPlan.data.overall_pct + 5
                      ? 'Rejadan orqadasiz'
                      : 'Yaxshi ketyapsiz'
                  }
                />
              </div>
              <Card>
                <MetricBar
                  label="💵 Sotuv summasi ($)"
                  fact={myPlan.data.amount.fact}
                  target={myPlan.data.amount.target}
                  percent={myPlan.data.amount.pct}
                />
                <MetricBar
                  label="📦 Sotilgan dona"
                  fact={myPlan.data.units.fact}
                  target={myPlan.data.units.target}
                  percent={myPlan.data.units.pct}
                />
                <MetricBar
                  label="💰 Yig‘ilgan pul ($)"
                  fact={myPlan.data.collection.fact}
                  target={myPlan.data.collection.target}
                  percent={myPlan.data.collection.pct}
                />
              </Card>
            </>
          ) : null}
        </>
      ) : null}

      {tab === 'board' ? (
        <>
          {board.isLoading ? <Loading /> : null}
          <div className="space-y-2">
            {(board.data ?? []).map((row, index) => (
              <Card key={row.user_id}>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-semibold">
                      {index === 0 ? '🥇 ' : index === 1 ? '🥈 ' : index === 2 ? '🥉 ' : `${index + 1}. `}
                      {row.full_name}
                      {row.user_id === me.id ? ' (siz)' : ''}
                    </div>
                    <div className="text-[12px] text-[var(--muted)]">
                      {usd(row.amount.fact)} · {num(row.units.fact)} dona · yig‘ilgan{' '}
                      {usd(row.collection.fact)}
                    </div>
                  </div>
                  <div
                    className="shrink-0 text-[17px] font-bold"
                    style={{ color: planColor(row.overall_pct) }}
                  >
                    {pct(row.overall_pct, 0)}
                  </div>
                </div>
                <Progress percent={row.overall_pct} />
              </Card>
            ))}
            {board.data?.length === 0 ? <Empty text="Agent yo‘q" /> : null}
          </div>
        </>
      ) : null}

      {tab === 'edit' && canEdit ? (
        <>
          {all.isLoading ? <Loading /> : null}
          <div className="space-y-2">
            {(all.data ?? []).map((row) => (
              <Card
                key={row.user_id}
                onClick={() =>
                  setEditing({ user_id: row.user_id, full_name: row.full_name })
                }
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-semibold">
                      {row.full_name}
                    </div>
                    <div className="text-[12px] text-[var(--muted)]">
                      Reja: {usd(row.target_amount_usd ?? 0, 0)} ·{' '}
                      {num(row.target_units ?? 0)} dona · yig‘ish{' '}
                      {usd(row.target_collection_usd ?? 0, 0)}
                    </div>
                  </div>
                  <div
                    className="shrink-0 text-[15px] font-bold"
                    style={{ color: planColor(row.overall_pct) }}
                  >
                    {pct(row.overall_pct, 0)}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      ) : null}

      <PlanEditor
        target={editing}
        onClose={() => setEditing(null)}
      />
    </Screen>
  )
}

function PlanEditor({
  target,
  onClose,
}: {
  target: { user_id: number; full_name: string } | null
  onClose: () => void
}) {
  const setPlan = useSetPlan()
  const now = new Date()
  const [amount, setAmount] = useState('')
  const [units, setUnits] = useState('')
  const [collection, setCollection] = useState('')
  const [month, setMonth] = useState(String(now.getMonth() + 1))
  const [year, setYear] = useState(String(now.getFullYear()))

  async function submit() {
    if (!target) return
    try {
      const result = await setPlan.mutateAsync({
        user_id: target.user_id,
        year: Number(year),
        month: Number(month),
        target_amount_usd: Number(amount) || 0,
        target_units: Number(units) || 0,
        target_collection_usd: Number(collection) || 0,
      })
      haptic('success')
      alertUser(result.message ?? 'Reja saqlandi')
      onClose()
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  return (
    <Sheet
      open={Boolean(target)}
      title={target ? `${target.full_name} rejasi` : ''}
      onClose={onClose}
    >
      <div className="grid grid-cols-2 gap-2">
        <Field label="Oy">
          <select
            className="select"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          >
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {m}-oy
              </option>
            ))}
          </select>
        </Field>
        <Field label="Yil">
          <input
            className="input"
            inputMode="numeric"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
        </Field>
      </div>
      <Field label="Sotuv summasi rejasi (USD)">
        <input
          className="input"
          inputMode="decimal"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </Field>
      <Field label="Sotilgan dona rejasi">
        <input
          className="input"
          inputMode="numeric"
          value={units}
          onChange={(e) => setUnits(e.target.value)}
        />
      </Field>
      <Field
        label="Yig‘iladigan pul rejasi (USD)"
        hint="Vrachlardan undiriladigan qarz summasi"
      >
        <input
          className="input"
          inputMode="decimal"
          value={collection}
          onChange={(e) => setCollection(e.target.value)}
        />
      </Field>
      <button className="btn btn-primary w-full" disabled={setPlan.isPending} onClick={submit}>
        {setPlan.isPending ? 'Saqlanmoqda…' : 'Rejani saqlash'}
      </button>
    </Sheet>
  )
}
