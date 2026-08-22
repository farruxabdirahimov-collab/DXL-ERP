import { useState } from 'react'
import { useCan, useCurrentUser } from '../App'
import {
  useAgents,
  useAllPlans,
  useCompanyPlan,
  useLeaderboard,
  useMyPlan,
  usePlanAction,
  usePlanHistory,
  useSetPlan,
} from '../api/hooks'
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
  Row,
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
  const [companyOpen, setCompanyOpen] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [form, setForm] = useState<Record<string, string>>({})
  const set = (k: string, v: string) => setForm({ ...form, [k]: v })

  const myPlan = useMyPlan()
  const board = useLeaderboard()
  const all = useAllPlans()
  const company = useCompanyPlan()
  const historyQ = usePlanHistory(undefined, 6)
  const planAction = usePlanAction()
  const bugun = new Date()
  const davr = { year: bugun.getFullYear(), month: bugun.getMonth() + 1 }

  const tabs = [
    ...(me.role === 'agent' ? [{ key: 'my', label: 'Mening rejam' }] : []),
    ...(canEdit ? [{ key: 'company', label: 'Kompaniya' }] : []),
    { key: 'board', label: 'Reyting' },
    ...(canEdit ? [{ key: 'edit', label: 'Reja qo‘yish' }] : []),
  ]

  async function ishga(path: string, body?: unknown, ok = 'Bajarildi') {
    try {
      const r = await planAction.mutateAsync({ path, body })
      haptic('success')
      alertUser(r.message ?? ok)
    } catch (e: any) {
      alertUser(e?.message ?? 'Bajarilmadi')
    }
  }

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

              {myPlan.data.forecast ? (
                <Card className="mt-3 p-3">
                  <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
                    Shu sur‘atda oy oxirida
                  </div>
                  <div
                    className="text-[24px] font-bold"
                    style={{ color: planColor(myPlan.data.forecast.projected_pct) }}
                  >
                    {usd(myPlan.data.forecast.projected_usd)}
                  </div>
                  <div className="mt-1 text-[13px] text-[var(--muted)]">
                    {myPlan.data.forecast.on_track
                      ? 'Sur‘atingiz yetarli — shu tarzda davom eting'
                      : `Rejaga yetish uchun kuniga ${usd(
                          myPlan.data.forecast.daily_needed_usd,
                        )} kerak (hozir ${usd(myPlan.data.forecast.daily_so_far_usd)})`}
                  </div>
                </Card>
              ) : null}

              {(historyQ.data ?? []).some((h: any) => h.has_plan) ? (
                <Section title="Oxirgi 6 oy">
                  <Card className="p-0">
                    {(historyQ.data ?? []).map((h: any) => (
                      <div
                        key={`${h.year}-${h.month}`}
                        className="flex items-center gap-3 border-b border-[var(--border)] px-3 py-2 last:border-b-0"
                      >
                        <div className="w-12 shrink-0 text-[13px] font-semibold text-[var(--muted)]">
                          {h.label}
                        </div>
                        <div className="min-w-0 flex-1">
                          <Progress percent={h.overall_pct} height={6} />
                        </div>
                        <div
                          className="w-12 shrink-0 text-right text-[13px] font-bold"
                          style={{ color: planColor(h.overall_pct) }}
                        >
                          {h.has_plan ? pct(h.overall_pct, 0) : '—'}
                        </div>
                      </div>
                    ))}
                  </Card>
                </Section>
              ) : null}
            </>
          ) : null}
        </>
      ) : null}

      {tab === 'company' && canEdit ? (
        <>
          {company.isLoading ? <Loading /> : null}
          {company.data ? (
            <>
              {!company.data.has_plan ? (
                <Card className="mb-3 p-3 text-[13px] text-[var(--muted)]">
                  Bu oyga kompaniya rejasi qo‘yilmagan. Pastdagi tugma bilan qo‘ying —
                  keyin agentlarga taqsimlanganini shu yerda nazorat qilasiz.
                </Card>
              ) : null}

              <div className="mb-3 grid grid-cols-2 gap-2">
                <Stat
                  label="Kompaniya sotuvi"
                  value={usd(company.data.amount.fact)}
                  hint={`reja ${usd(company.data.amount.target)}`}
                  tone={company.data.amount.pct >= 80 ? 'ok' : 'warn'}
                />
                <Stat
                  label="Bajarilish"
                  value={pct(company.data.amount.pct, 0)}
                  hint={`${company.data.days_passed}/${company.data.days_in_month} kun`}
                />
              </div>

              {/* Prognoz — shu sur'atda oy oxirida qancha bo'ladi */}
              <Card className="mb-3 p-3">
                <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
                  Shu sur‘atda oy oxirida
                </div>
                <div
                  className="text-[26px] font-bold"
                  style={{ color: planColor(company.data.forecast.projected_pct) }}
                >
                  {usd(company.data.forecast.projected_usd)}
                </div>
                <div className="mt-1 text-[13px] text-[var(--muted)]">
                  Hozir kuniga {usd(company.data.forecast.daily_so_far_usd)} ·
                  rejaga yetish uchun{' '}
                  <b style={{ color: 'var(--fg)' }}>
                    {usd(company.data.forecast.daily_needed_usd)}/kun
                  </b>{' '}
                  kerak
                </div>
              </Card>

              {/* Taqsimot nazorati — egasiz reja */}
              {company.data.unassigned_usd > 0 ? (
                <Card className="mb-3 border-[var(--warn)] p-3">
                  <div className="text-[13px] font-semibold text-[var(--warn)]">
                    ⚠️ {usd(company.data.unassigned_usd)} egasiz
                  </div>
                  <div className="mt-1 text-[12px] text-[var(--muted)]">
                    Kompaniya rejasi {usd(company.data.amount.target)}, agentlarga
                    bo‘lingani {usd(company.data.assigned_usd)}. Farqni kimdir
                    bajarishi kerak, lekin hech kimga biriktirilmagan.
                  </div>
                </Card>
              ) : null}

              <Section title="Ko‘rsatkichlar">
                <Card>
                  <MetricBar
                    label="💵 Sotuv summasi ($)"
                    fact={company.data.amount.fact}
                    target={company.data.amount.target}
                    percent={company.data.amount.pct}
                  />
                  <MetricBar
                    label="📦 Sotilgan dona"
                    fact={company.data.units.fact}
                    target={company.data.units.target}
                    percent={company.data.units.pct}
                  />
                  <MetricBar
                    label="💰 Yig‘ilgan pul ($)"
                    fact={company.data.collection.fact}
                    target={company.data.collection.target}
                    percent={company.data.collection.pct}
                  />
                  <MetricBar
                    label="🧑‍⚕️ Yangi vrachlar"
                    fact={company.data.new_doctors.fact}
                    target={company.data.new_doctors.target}
                    percent={company.data.new_doctors.pct}
                  />
                </Card>
              </Section>

              <Section title="Reja qo‘yish">
                <Card className="p-0">
                  <Row
                    title="🏢 Kompaniya rejasini qo‘yish"
                    subtitle={`${davr.month}/${davr.year}`}
                    right="›"
                    onClick={() => setCompanyOpen(true)}
                  />
                  <Row
                    title="📋 O‘tgan oydan nusxa"
                    subtitle={`${company.data.agents_with_plan}/${company.data.agents_total} agentda reja bor`}
                    right="›"
                    onClick={() =>
                      ishga(
                        `/plans/copy-previous?year=${davr.year}&month=${davr.month}`,
                      )
                    }
                  />
                  <Row
                    title="👥 Hammaga bir xil reja"
                    subtitle="Barcha faol agentlarga bitta raqam"
                    right="›"
                    onClick={() => setBulkOpen(true)}
                  />
                </Card>
              </Section>
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

      <Sheet
        open={companyOpen}
        title="Kompaniya rejasi"
        onClose={() => setCompanyOpen(false)}
      >
        <p className="mb-3 text-[13px] text-[var(--muted)]">
          {davr.month}/{davr.year} uchun umumiy maqsad. Agentlarga bo‘lingani
          bundan kam bo‘lsa, farq «egasiz» deb ko‘rsatiladi.
        </p>
        <Field label="Sotuv summasi ($)">
          <input
            className="input"
            inputMode="decimal"
            value={form.c_amount ?? ''}
            onChange={(e) => set('c_amount', e.target.value)}
          />
        </Field>
        <Field label="Sotilgan dona">
          <input
            className="input"
            inputMode="numeric"
            value={form.c_units ?? ''}
            onChange={(e) => set('c_units', e.target.value)}
          />
        </Field>
        <Field label="Yig‘iladigan pul ($)">
          <input
            className="input"
            inputMode="decimal"
            value={form.c_coll ?? ''}
            onChange={(e) => set('c_coll', e.target.value)}
          />
        </Field>
        <Field label="Yangi vrachlar" hint="Ixtiyoriy — 0 qo‘yilsa hisobga olinmaydi">
          <input
            className="input"
            inputMode="numeric"
            value={form.c_docs ?? ''}
            onChange={(e) => set('c_docs', e.target.value)}
          />
        </Field>
        <button
          className="btn btn-primary w-full"
          disabled={planAction.isPending}
          onClick={async () => {
            await ishga('/plans/company', {
              ...davr,
              target_amount_usd: form.c_amount || '0',
              target_units: Number(form.c_units) || 0,
              target_collection_usd: form.c_coll || '0',
              target_new_doctors: Number(form.c_docs) || 0,
            })
            setCompanyOpen(false)
          }}
        >
          {planAction.isPending ? 'Saqlanmoqda…' : 'Saqlash'}
        </button>
      </Sheet>

      <Sheet
        open={bulkOpen}
        title="Hammaga bir xil reja"
        onClose={() => setBulkOpen(false)}
      >
        <p className="mb-3 text-[13px] text-[var(--muted)]">
          Barcha faol agentlarga shu raqamlar qo‘yiladi. Mavjud rejalar
          almashtiriladi.
        </p>
        <Field label="Sotuv summasi ($)">
          <input
            className="input"
            inputMode="decimal"
            value={form.b_amount ?? ''}
            onChange={(e) => set('b_amount', e.target.value)}
          />
        </Field>
        <Field label="Sotilgan dona">
          <input
            className="input"
            inputMode="numeric"
            value={form.b_units ?? ''}
            onChange={(e) => set('b_units', e.target.value)}
          />
        </Field>
        <Field label="Yig‘iladigan pul ($)">
          <input
            className="input"
            inputMode="decimal"
            value={form.b_coll ?? ''}
            onChange={(e) => set('b_coll', e.target.value)}
          />
        </Field>
        <Field label="Tashriflar" hint="Ixtiyoriy">
          <input
            className="input"
            inputMode="numeric"
            value={form.b_visits ?? ''}
            onChange={(e) => set('b_visits', e.target.value)}
          />
        </Field>
        <button
          className="btn btn-primary w-full"
          disabled={planAction.isPending}
          onClick={async () => {
            await ishga('/plans/bulk', {
              ...davr,
              target_amount_usd: form.b_amount || '0',
              target_units: Number(form.b_units) || 0,
              target_collection_usd: form.b_coll || '0',
              target_visits: Number(form.b_visits) || 0,
            })
            setBulkOpen(false)
          }}
        >
          {planAction.isPending ? 'Saqlanmoqda…' : 'Hammaga qo‘yish'}
        </button>
      </Sheet>
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
