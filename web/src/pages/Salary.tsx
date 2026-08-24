import { useState } from 'react'
import { useCan, useCurrentUser } from '../App'
import {
  useKpiAction,
  useMySalary,
  useSalaries,
  useSubmissions,
} from '../api/hooks'
import { num, pct, shortDate, usd } from '../lib/format'
import { alertUser, confirmUser, haptic } from '../lib/telegram'
import {
  Card,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Progress,
  Row,
  Screen,
  Section,
  Sheet,
  Tabs,
} from '../components/ui'

export default function Salary() {
  const me = useCurrentUser()
  const can = useCan()
  const isBoss = can('plans.edit')

  const [tab, setTab] = useState(isBoss ? 'team' : 'my')
  const salary = useMySalary()
  const team = useSalaries()
  const mine = useSubmissions()
  const pending = useSubmissions({ status: 'pending' })
  const action = useKpiAction()

  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState('post')
  const [url, setUrl] = useState('')

  const tabs = [
    { key: 'my', label: 'Oyligim' },
    { key: 'posts', label: 'Postlarim' },
    ...(isBoss ? [{ key: 'team', label: 'Jamoa' }, { key: 'review', label: 'Tasdiqlash' }] : []),
  ]

  async function ishga(args: Parameters<typeof action.mutateAsync>[0]) {
    try {
      const r = await action.mutateAsync(args)
      haptic('success')
      alertUser(r.message ?? 'Bajarildi')
      return true
    } catch (e: any) {
      alertUser(e?.message ?? 'Bajarilmadi')
      return false
    }
  }

  const s = salary.data

  return (
    <Screen title="Oylik" subtitle={me.full_name}>
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {salary.error ? <ErrorBox error={salary.error} /> : null}

      {tab === 'my' ? (
        <>
          {salary.isLoading ? <Loading /> : null}
          {s ? (
            <>
              <Card className="mb-3 p-4 text-center">
                <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
                  Shu oy uchun kutilayotgan oylik
                </div>
                <div className="my-1 text-[34px] font-bold text-[var(--accent)]">
                  {usd(s.total_usd)}
                </div>
                {Number(s.potential_usd) > 0 ? (
                  <div className="text-[13px] text-[var(--muted)]">
                    Tasdiq kutayotgani hisobga olinsa{' '}
                    <b>+{usd(s.potential_usd)}</b>
                  </div>
                ) : null}
              </Card>

              <Section title="Nimadan yig'ildi">
                {s.rows.map((r: any) => (
                  <Card key={r.key} className="mb-2 p-3">
                    <div className="flex items-baseline justify-between gap-3">
                      <div className="text-[14px] font-semibold">{r.label}</div>
                      <div className="shrink-0 text-[17px] font-bold tabular-nums">
                        {usd(r.amount_usd)}
                      </div>
                    </div>

                    {r.target > 0 ? (
                      <>
                        <div className="mt-2">
                          <Progress
                            percent={Math.min(100, (r.fact / r.target) * 100)}
                            height={6}
                          />
                        </div>
                        <div className="mt-1 flex justify-between text-[12px] text-[var(--muted)]">
                          <span>
                            {r.key === 'collection'
                              ? `${usd(r.fact)} yig'ildi`
                              : `${num(r.fact)} / ${num(r.target)}`}
                          </span>
                          <span>{pct(Math.min(100, (r.fact / r.target) * 100), 0)}</span>
                        </div>
                      </>
                    ) : null}

                    <p className="mt-1.5 text-[12px] text-[var(--muted)]">{r.note}</p>
                  </Card>
                ))}
              </Section>
            </>
          ) : null}
        </>
      ) : null}

      {tab === 'posts' ? (
        <>
          <button className="btn btn-primary mb-3 w-full" onClick={() => setOpen(true)}>
            + Havola yuborish
          </button>
          <Card className="mb-3 p-3 text-[13px] text-[var(--muted)]">
            Post yoki shifokor otzivi videosining havolasini tashlang. Direktor
            tasdiqlagach oyligingizga qo‘shiladi.
          </Card>
          <Card className="p-0">
            {(mine.data ?? []).map((r: any) => (
              <Row
                key={r.id}
                title={r.kind_label}
                subtitle={`${shortDate(r.created_at)} · ${r.status_label}${
                  r.reject_reason ? ` · ${r.reject_reason}` : ''
                }`}
                right={
                  r.status === 'approved' ? '✅' : r.status === 'rejected' ? '❌' : '⏳'
                }
                onClick={
                  r.status === 'pending'
                    ? async () => {
                        if (!(await confirmUser('Havola o‘chirilsinmi?'))) return
                        await ishga({
                          path: `/kpi/submissions/${r.id}`,
                          method: 'del',
                        })
                      }
                    : undefined
                }
              />
            ))}
            {!mine.isLoading && !mine.data?.length ? (
              <Empty text="Hali havola yuborilmagan" />
            ) : null}
          </Card>
        </>
      ) : null}

      {tab === 'team' && isBoss ? (
        <>
          {team.isLoading ? <Loading /> : null}
          {team.data ? (
            <>
              <Card className="mb-3 p-3">
                <div className="text-[12px] uppercase tracking-wide text-[var(--muted)]">
                  Bu oy jami to‘lanadi
                </div>
                <div className="text-[26px] font-bold">{usd(team.data.total_usd)}</div>
              </Card>
              {(team.data.rows ?? []).map((r: any) => (
                <Card key={r.user_id} className="mb-2 p-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="text-[14px] font-semibold">{r.full_name}</div>
                    <div className="shrink-0 text-[17px] font-bold">
                      {usd(r.total_usd)}
                    </div>
                  </div>
                  <div className="mt-1 text-[12px] text-[var(--muted)]">
                    {r.rows
                      .filter((x: any) => Number(x.amount_usd) > 0)
                      .map((x: any) => `${x.label} ${usd(x.amount_usd)}`)
                      .join(' · ')}
                  </div>
                </Card>
              ))}
            </>
          ) : null}
        </>
      ) : null}

      {tab === 'review' && isBoss ? (
        <>
          <Card className="mb-3 p-3 text-[13px] text-[var(--muted)]">
            Tasdiqlangan havola menejerning oyligiga darhol qo‘shiladi.
          </Card>
          <Card className="p-0">
            {(pending.data ?? []).map((r: any) => (
              <div
                key={r.id}
                className="border-b border-[var(--border)] p-3 last:border-b-0"
              >
                <div className="text-[14px] font-semibold">
                  {r.agent_name} · {r.kind_label}
                </div>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-0.5 block break-all text-[12px]"
                >
                  {r.url}
                </a>
                <div className="mt-2 flex gap-2">
                  <button
                    className="btn btn-sm btn-primary flex-1"
                    onClick={() =>
                      ishga({
                        path: `/kpi/submissions/${r.id}/review`,
                        body: { approve: true },
                      })
                    }
                  >
                    ✅ Tasdiqlash
                  </button>
                  <button
                    className="btn btn-sm flex-1"
                    onClick={() =>
                      ishga({
                        path: `/kpi/submissions/${r.id}/review`,
                        body: { approve: false, reason: 'Talabga javob bermadi' },
                      })
                    }
                  >
                    ❌ Rad etish
                  </button>
                </div>
              </div>
            ))}
            {!pending.isLoading && !pending.data?.length ? (
              <Empty text="Tasdiq kutayotgan havola yo‘q" />
            ) : null}
          </Card>
        </>
      ) : null}

      <Sheet open={open} title="Havola yuborish" onClose={() => setOpen(false)}>
        <Field label="Turi">
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="post">Post / video (o‘zim joyladim)</option>
            <option value="review">Shifokor otzivi</option>
          </select>
        </Field>
        <Field label="Havola" hint="Telegram, Instagram yoki YouTube havolasi">
          <input
            className="input"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://..."
          />
        </Field>
        <button
          className="btn btn-primary w-full"
          disabled={url.length < 5 || action.isPending}
          onClick={async () => {
            const ok = await ishga({ path: '/kpi/submissions', body: { kind, url } })
            if (ok) {
              setOpen(false)
              setUrl('')
            }
          }}
        >
          {action.isPending ? 'Yuborilmoqda…' : 'Yuborish'}
        </button>
      </Sheet>
    </Screen>
  )
}
