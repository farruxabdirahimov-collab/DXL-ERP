import { useEffect, useState } from 'react'
import { useCan } from '../App'
import { useFxRate, useSaveSetting, useSetFxRate, useSettings } from '../api/hooks'
import { num } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import { Card, ErrorBox, Field, Loading, Screen, Section } from '../components/ui'
import { api } from '../api/client'

export default function SettingsPage() {
  const can = useCan()
  const { data, isLoading, error } = useSettings()
  const save = useSaveSetting()
  const { data: fx } = useFxRate()
  const setFx = useSetFxRate()

  const [values, setValues] = useState<Record<string, string>>({})
  const [botBusy, setBotBusy] = useState(false)
  const [rate, setRate] = useState('')

  useEffect(() => {
    if (!data) return
    const next: Record<string, string> = {}
    data.forEach((row) => {
      next[row.key] =
        typeof row.value === 'object' && row.value !== null
          ? JSON.stringify(row.value)
          : String(row.value ?? '')
    })
    setValues(next)
  }, [data])

  useEffect(() => {
    if (fx) setRate(String(Number(fx.usd_uzs)))
  }, [fx?.usd_uzs])

  async function saveOne(key: string) {
    const raw = values[key] ?? ''
    let parsed: unknown = raw
    if (raw === 'true' || raw === 'false') parsed = raw === 'true'
    else if (raw.trim().startsWith('{')) {
      try {
        parsed = JSON.parse(raw)
      } catch {
        alertUser('JSON formati noto‘g‘ri')
        return
      }
    } else if (raw !== '' && !Number.isNaN(Number(raw))) parsed = Number(raw)

    try {
      await save.mutateAsync({ key, value: parsed })
      haptic('success')
      alertUser('Saqlandi')
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  async function saveRate() {
    const value = Number(rate)
    if (!value || value <= 0) {
      alertUser('Kursni to‘g‘ri kiriting')
      return
    }
    try {
      const result = await setFx.mutateAsync({ usd_uzs: value })
      haptic('success')
      alertUser(result.message ?? 'Kurs saqlandi')
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  async function resetWebhook() {
    setBotBusy(true)
    try {
      const result = await api.post<{ ok: boolean; message: string; webhook_url: string }>(
        '/admin/reset-webhook',
      )
      haptic(result.ok ? 'success' : 'error')
      alertUser(`${result.message}\n\n${result.webhook_url}`)
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    } finally {
      setBotBusy(false)
    }
  }

  return (
    <Screen title="Sozlamalar" subtitle="Tizim qoidalari va valyuta kursi">
      <Section title="Telegram bot">
        <Card>
          <p className="mb-3 text-[13px] text-[var(--muted)]">
            Bot xabarlarga javob bermay qolsa, aloqani shu yerdan tiklang.
            Deploy qilish shart emas.
          </p>
          <button className="btn w-full" disabled={botBusy} onClick={resetWebhook}>
            {botBusy ? 'Tekshirilmoqda…' : '🔄 Bot aloqasini tiklash'}
          </button>
        </Card>
      </Section>

      {can('fx.edit') ? (
        <Section title="Valyuta kursi">
          <Card>
            <div className="mb-2 text-[13px] text-[var(--muted)]">
              Bugungi kurs: 1 USD = {num(fx?.usd_uzs ?? 0)} so‘m. Narxlar dollarda
              saqlanadi, to‘lovlar so‘mda qabul qilinadi.
            </div>
            <div className="flex gap-2">
              <input
                className="input"
                inputMode="numeric"
                value={rate}
                onChange={(e) => setRate(e.target.value)}
              />
              <button className="btn btn-primary" onClick={saveRate} disabled={setFx.isPending}>
                Saqlash
              </button>
            </div>
          </Card>
        </Section>
      ) : null}

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}

      <Section title="Tizim qoidalari">
        {(data ?? []).map((row) => (
          <Card key={row.key} className="mb-2">
            <Field label={row.key} hint={row.label_uz}>
              <div className="flex gap-2">
                {typeof row.value === 'boolean' ? (
                  <select
                    className="select"
                    value={values[row.key] ?? 'true'}
                    onChange={(e) =>
                      setValues({ ...values, [row.key]: e.target.value })
                    }
                  >
                    <option value="true">Yoqilgan</option>
                    <option value="false">O‘chirilgan</option>
                  </select>
                ) : (
                  <input
                    className="input"
                    value={values[row.key] ?? ''}
                    onChange={(e) =>
                      setValues({ ...values, [row.key]: e.target.value })
                    }
                  />
                )}
                <button
                  className="btn"
                  onClick={() => saveOne(row.key)}
                  disabled={save.isPending}
                >
                  ✓
                </button>
              </div>
            </Field>
          </Card>
        ))}
      </Section>
    </Screen>
  )
}
