import { useState } from 'react'
import { useAudit } from '../api/hooks'
import { dateTime } from '../lib/format'
import { Card, Chip, Empty, ErrorBox, Loading, Screen, Tabs } from '../components/ui'

const ACTION_LABELS: Record<string, string> = {
  create: 'Yaratildi',
  update: 'O‘zgartirildi',
  delete: 'O‘chirildi',
  approve: 'Tasdiqlandi',
  deliver: 'Yetkazildi',
  cancel: 'Bekor qilindi',
  payment: 'To‘lov',
  receipt: 'Kirim',
  transfer: 'Ko‘chirish',
  writeoff: 'Spisaniye',
  adjust: 'Korreksiya',
  return: 'Qaytarish',
  set_rate: 'Kurs o‘zgardi',
  set_plan: 'Reja qo‘yildi',
  import: 'Import',
  invite: 'Taklifnoma',
}

const ENTITY_LABELS: Record<string, string> = {
  product: 'Mahsulot',
  doctor: 'Vrach',
  order: 'Buyurtma',
  stock: 'Ombor',
  user: 'Xodim',
  setting: 'Sozlama',
  fx: 'Valyuta',
  invite: 'Taklifnoma',
}

export default function Audit() {
  const [entity, setEntity] = useState('')
  const { data, isLoading, error } = useAudit({
    entity: entity || undefined,
    limit: 150,
  })

  return (
    <Screen title="Audit jurnali" subtitle="Kim, qachon, nimani o‘zgartirgani">
      <Tabs
        tabs={[
          { key: '', label: 'Hammasi' },
          { key: 'order', label: 'Buyurtma' },
          { key: 'stock', label: 'Ombor' },
          { key: 'doctor', label: 'Vrach' },
          { key: 'product', label: 'Mahsulot' },
          { key: 'user', label: 'Xodim' },
          { key: 'setting', label: 'Sozlama' },
        ]}
        active={entity}
        onChange={setEntity}
      />

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data?.length === 0 ? <Empty text="Yozuv yo‘q" /> : null}

      <div className="space-y-2">
        {(data ?? []).map((row) => (
          <Card key={row.id}>
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="text-[14px] font-semibold">
                  {ACTION_LABELS[row.action] ?? row.action} ·{' '}
                  {ENTITY_LABELS[row.entity] ?? row.entity}
                  {row.entity_id ? ` #${row.entity_id}` : ''}
                </div>
                <div className="text-[12px] text-[var(--muted)]">
                  {row.user_name ?? 'tizim'} · {dateTime(row.created_at)}
                </div>
              </div>
            </div>
            {row.comment ? (
              <div className="mt-1 text-[13px]">{row.comment}</div>
            ) : null}
            {row.old_value || row.new_value ? (
              <details className="mt-2">
                <summary className="cursor-pointer text-[12px] text-[var(--muted)]">
                  Tafsilotlar
                </summary>
                <div className="mt-1 space-y-1 text-[12px]">
                  {row.old_value ? (
                    <div>
                      <span className="text-[var(--muted)]">Oldin: </span>
                      <code>{JSON.stringify(row.old_value)}</code>
                    </div>
                  ) : null}
                  {row.new_value ? (
                    <div>
                      <span className="text-[var(--muted)]">Keyin: </span>
                      <code>{JSON.stringify(row.new_value)}</code>
                    </div>
                  ) : null}
                </div>
              </details>
            ) : null}
          </Card>
        ))}
      </div>
    </Screen>
  )
}
