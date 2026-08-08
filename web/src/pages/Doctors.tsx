import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCan, useCurrentUser } from '../App'
import { useAgents, useBirthdays, useDoctors, useSaveDoctor } from '../api/hooks'
import { api } from '../api/client'
import type { Doctor } from '../api/types'
import { CATEGORY_LABELS, daysAgo, shortDate, usd } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Chip,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Screen,
  Sheet,
  Tabs,
} from '../components/ui'

export function DoctorForm({
  open,
  initial,
  onClose,
}: {
  open: boolean
  initial: Partial<Doctor> | null
  onClose: () => void
}) {
  const me = useCurrentUser()
  const can = useCan()
  const [form, setForm] = useState<Partial<Doctor>>(initial ?? {})
  const { data: agents } = useAgents()
  const save = useSaveDoctor()
  const isManager = can('doctors.all')

  // Sheet ochilganda formani boshlang'ich qiymatlar bilan to'ldiramiz
  useEffect(() => {
    if (open) setForm(initial ?? {})
  }, [open, initial?.id])

  async function submit() {
    if (!form.full_name || !form.phone) {
      alertUser('Ism va telefon raqamni to‘ldiring')
      return
    }
    const body: Record<string, unknown> = {
      full_name: form.full_name,
      phone: form.phone,
      extra_phone: form.extra_phone || null,
      clinic_name: form.clinic_name || null,
      region: form.region || null,
      district: form.district || null,
      address: form.address || null,
      birth_date: form.birth_date || null,
      specialty: form.specialty || null,
      notes: form.notes || null,
      discount_pct: form.discount_pct ?? '0',
    }
    if (isManager) {
      body.agent_id = form.agent_id ?? null
      body.debt_limit_usd = form.debt_limit_usd ?? '0'
      body.payment_term_days = form.payment_term_days ?? 30
    }
    try {
      await save.mutateAsync({ id: form.id, body })
      haptic('success')
      onClose()
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Saqlashda xatolik')
    }
  }

  return (
    <Sheet
      open={open}
      title={form.id ? 'Vrach ma’lumotlari' : 'Yangi vrach'}
      onClose={onClose}
    >
      <Field label="F.I.O.">
        <input
          className="input"
          value={form.full_name ?? ''}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Telefon">
          <input
            className="input"
            inputMode="tel"
            placeholder="+998901234567"
            value={form.phone ?? ''}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
        </Field>
        <Field label="Qo‘shimcha telefon">
          <input
            className="input"
            inputMode="tel"
            value={form.extra_phone ?? ''}
            onChange={(e) => setForm({ ...form, extra_phone: e.target.value })}
          />
        </Field>
      </div>
      <Field label="Klinika">
        <input
          className="input"
          value={form.clinic_name ?? ''}
          onChange={(e) => setForm({ ...form, clinic_name: e.target.value })}
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Viloyat">
          <input
            className="input"
            value={form.region ?? ''}
            onChange={(e) => setForm({ ...form, region: e.target.value })}
          />
        </Field>
        <Field label="Tuman">
          <input
            className="input"
            value={form.district ?? ''}
            onChange={(e) => setForm({ ...form, district: e.target.value })}
          />
        </Field>
      </div>
      <Field label="Manzil">
        <textarea
          className="textarea"
          rows={2}
          value={form.address ?? ''}
          onChange={(e) => setForm({ ...form, address: e.target.value })}
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Tug‘ilgan kun">
          <input
            className="input"
            type="date"
            value={form.birth_date ?? ''}
            onChange={(e) => setForm({ ...form, birth_date: e.target.value })}
          />
        </Field>
        <Field label="Mutaxassisligi">
          <input
            className="input"
            value={form.specialty ?? ''}
            onChange={(e) => setForm({ ...form, specialty: e.target.value })}
          />
        </Field>
      </div>

      {isManager ? (
        <>
          <Field label="Biriktirilgan agent">
            <select
              className="select"
              value={form.agent_id ?? ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  agent_id: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">Tanlanmagan</option>
              {(agents ?? []).map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.full_name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Qarz limiti (USD)">
              <input
                className="input"
                inputMode="decimal"
                value={form.debt_limit_usd ?? '0'}
                onChange={(e) => setForm({ ...form, debt_limit_usd: e.target.value })}
              />
            </Field>
            <Field label="To‘lov muddati (kun)">
              <input
                className="input"
                inputMode="numeric"
                value={form.payment_term_days ?? 30}
                onChange={(e) =>
                  setForm({ ...form, payment_term_days: Number(e.target.value) })
                }
              />
            </Field>
          </div>
        </>
      ) : null}

      <Field label="Doimiy chegirma (%)">
        <input
          className="input"
          inputMode="decimal"
          value={form.discount_pct ?? '0'}
          onChange={(e) => setForm({ ...form, discount_pct: e.target.value })}
        />
      </Field>
      <Field label="Izoh">
        <textarea
          className="textarea"
          rows={2}
          value={form.notes ?? ''}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
        />
      </Field>

      <button className="btn btn-primary w-full" disabled={save.isPending} onClick={submit}>
        {save.isPending ? 'Saqlanmoqda…' : 'Saqlash'}
      </button>
    </Sheet>
  )
}

export default function Doctors() {
  const navigate = useNavigate()
  const can = useCan()
  const [tab, setTab] = useState('all')
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<Partial<Doctor> | null>(null)

  const params = useMemo(
    () => ({
      search: search || undefined,
      only_debtors: tab === 'debtors' ? true : undefined,
      only_overdue: tab === 'overdue' ? true : undefined,
    }),
    [search, tab],
  )
  const { data, isLoading, error } = useDoctors(params)
  const { data: birthdays } = useBirthdays(14)

  const rows = tab === 'birthdays' ? (birthdays ?? []) : (data ?? [])

  return (
    <Screen
      title="Vrachlar"
      subtitle={`${rows.length} ta`}
      action={
        can('doctors.edit') ? (
          <button className="btn btn-sm btn-primary" onClick={() => setEditing({})}>
            + Yangi
          </button>
        ) : null
      }
    >
      <input
        className="input mb-3"
        placeholder="Ism, klinika yoki telefon…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <Tabs
        tabs={[
          { key: 'all', label: 'Hammasi' },
          { key: 'debtors', label: 'Qarzdorlar' },
          { key: 'overdue', label: 'Muddati o‘tgan' },
          { key: 'birthdays', label: `🎂 ${birthdays?.length ?? 0}` },
        ]}
        active={tab}
        onChange={setTab}
      />

      <button
        className="btn btn-sm mb-3 w-full"
        onClick={() => api.download('/reports/export.xlsx', { kind: 'doctors' })}
      >
        ⬇️ Excel’ga yuklash
      </button>

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {rows.length === 0 && !isLoading ? <Empty text="Vrach topilmadi" /> : null}

      <div className="space-y-2">
        {rows.map((doctor) => {
          const idle = daysAgo(doctor.last_order_at)
          return (
            <Card key={doctor.id} onClick={() => navigate(`/doctors/${doctor.id}`)}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-semibold">
                    {doctor.full_name}
                  </div>
                  <div className="truncate text-[12px] text-[var(--muted)]">
                    {doctor.clinic_name ?? doctor.phone}
                    {doctor.region ? ` · ${doctor.region}` : ''}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <Chip>{CATEGORY_LABELS[doctor.category] ?? doctor.category}</Chip>
                    <Chip>⭐ {doctor.loyalty_score}</Chip>
                    {tab === 'birthdays' && doctor.birth_date ? (
                      <Chip color="var(--accent)">🎂 {shortDate(doctor.birth_date)}</Chip>
                    ) : null}
                    {idle != null && idle > 60 ? (
                      <Chip color="var(--warn)">😴 {idle} kun</Chip>
                    ) : null}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div
                    className="text-[15px] font-bold"
                    style={{
                      color:
                        Number(doctor.overdue_usd) > 0
                          ? 'var(--danger)'
                          : Number(doctor.debt_usd) > 0
                            ? 'var(--warn)'
                            : 'var(--ok)',
                    }}
                  >
                    {usd(doctor.debt_usd)}
                  </div>
                  <div className="text-[11px] text-[var(--muted)]">
                    {Number(doctor.overdue_usd) > 0
                      ? `${doctor.overdue_days} kun kechikdi`
                      : `limit ${usd(doctor.debt_limit_usd, 0)}`}
                  </div>
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      <DoctorForm
        open={Boolean(editing)}
        initial={editing}
        onClose={() => setEditing(null)}
      />
    </Screen>
  )
}
