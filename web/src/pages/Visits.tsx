import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCan } from '../App'
import { useCheckIn, useDoctors, useVisitSummary, useVisits } from '../api/hooks'
import { dateTime, num } from '../lib/format'
import { alertUser, getPosition, haptic } from '../lib/telegram'
import {
  Card,
  Chip,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Row,
  Screen,
  Section,
  Sheet,
  Tabs,
} from '../components/ui'

const RESULTS: Record<string, string> = {
  order: 'Buyurtma olindi',
  no_order: 'Buyurtmasiz',
  not_there: 'Vrach joyida yo‘q edi',
  payment: 'Pul yig‘ildi',
}

export default function Visits() {
  const can = useCan()
  const navigate = useNavigate()
  const canSeeAll = can('visits.all')
  const [tab, setTab] = useState('list')
  const [open, setOpen] = useState(false)
  const [doctorId, setDoctorId] = useState<number | undefined>()
  const [result, setResult] = useState('no_order')
  const [note, setNote] = useState('')

  const { data, isLoading, error } = useVisits({ limit: 100 })
  const { data: summary } = useVisitSummary()
  const { data: doctors } = useDoctors({ limit: 500 })
  const checkIn = useCheckIn()

  async function submit() {
    if (!doctorId) {
      alertUser('Vrachni tanlang')
      return
    }
    const position = await getPosition()
    try {
      await checkIn.mutateAsync({
        doctor_id: doctorId,
        lat: position?.lat ?? null,
        lon: position?.lon ?? null,
        result,
        note: note || null,
      })
      haptic('success')
      alertUser(
        position ? 'Tashrif qayd etildi' : 'Tashrif qayd etildi (joylashuvsiz)',
      )
      setOpen(false)
      setNote('')
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  return (
    <Screen
      title="Tashriflar"
      subtitle={`${data?.length ?? 0} ta yozuv`}
      action={
        <button className="btn btn-sm btn-primary" onClick={() => setOpen(true)}>
          📍 Tashrif
        </button>
      }
    >
      {canSeeAll ? (
        <Tabs
          tabs={[
            { key: 'list', label: 'Ro‘yxat' },
            { key: 'summary', label: 'Bugungi yakun' },
          ]}
          active={tab}
          onChange={setTab}
        />
      ) : null}

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}

      {tab === 'summary' && canSeeAll ? (
        <Section title={`Bugun · ${summary?.date ?? ''}`}>
          <Card className="p-0">
            {(summary?.agents ?? []).map((agent: any) => (
              <Row
                key={agent.agent_id}
                title={agent.full_name}
                subtitle={`Joyida ${num(agent.on_site)} · uzoqda ${num(agent.far)} · noma’lum ${num(agent.unknown)}`}
                right={`${num(agent.visits)} ta`}
              />
            ))}
            {!summary?.agents?.length ? <Empty text="Bugun tashrif yo‘q" /> : null}
          </Card>
          <div className="mt-2 text-[12px] text-[var(--muted)]">
            «Joyida» — klinikadan {num(summary?.max_distance_m ?? 300)} metr ichida qayd
            etilgan tashriflar.
          </div>
        </Section>
      ) : (
        <div className="space-y-2">
          {(data ?? []).map((visit) => (
            <Card key={visit.id} onClick={() => navigate(`/doctors/${visit.doctor_id}`)}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-semibold">
                    {visit.doctor_name}
                  </div>
                  <div className="text-[12px] text-[var(--muted)]">
                    {dateTime(visit.created_at)}
                    {canSeeAll && visit.agent_name ? ` · ${visit.agent_name}` : ''}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {visit.result ? <Chip>{RESULTS[visit.result]}</Chip> : null}
                    {visit.distance_m != null ? (
                      <Chip
                        color={visit.distance_m <= 300 ? 'var(--ok)' : 'var(--warn)'}
                      >
                        {num(visit.distance_m)} m
                      </Chip>
                    ) : (
                      <Chip color="var(--muted)">joylashuvsiz</Chip>
                    )}
                  </div>
                  {visit.note ? (
                    <div className="mt-1 text-[12px]">{visit.note}</div>
                  ) : null}
                </div>
              </div>
            </Card>
          ))}
          {data?.length === 0 ? <Empty text="Tashrif yo‘q" /> : null}
        </div>
      )}

      <Sheet open={open} title="Tashrif qayd etish" onClose={() => setOpen(false)}>
        <Field label="Vrach">
          <select
            className="select"
            value={doctorId ?? ''}
            onChange={(e) => setDoctorId(Number(e.target.value))}
          >
            <option value="">Tanlang</option>
            {(doctors ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name} — {d.clinic_name ?? d.phone}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Natija">
          <select
            className="select"
            value={result}
            onChange={(e) => setResult(e.target.value)}
          >
            {Object.entries(RESULTS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Izoh">
          <textarea
            className="textarea"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </Field>
        <button
          className="btn btn-primary w-full"
          disabled={checkIn.isPending}
          onClick={submit}
        >
          {checkIn.isPending ? 'Saqlanmoqda…' : '📍 Joylashuv bilan qayd etish'}
        </button>
      </Sheet>
    </Screen>
  )
}
