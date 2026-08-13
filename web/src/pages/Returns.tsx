import { useNavigate } from 'react-router-dom'
import { useReturns } from '../api/hooks'
import { dateTime, num, usd } from '../lib/format'
import { Card, Empty, ErrorBox, Loading, Row, Screen, Section, Stat } from '../components/ui'

export default function Returns() {
  const navigate = useNavigate()
  const { data, isLoading, error } = useReturns()

  const rows = data ?? []
  const totalUsd = rows.reduce((sum, r) => sum + Number(r.total_usd), 0)
  const totalUnits = rows.reduce((sum, r) => sum + Number(r.units), 0)

  return (
    <Screen title="Qaytarishlar" subtitle={`${rows.length} ta hujjat`}>
      {error ? <ErrorBox error={error} /> : null}
      {isLoading ? <Loading /> : null}

      {rows.length ? (
        <div className="mb-4 grid grid-cols-2 gap-2">
          <Stat label="Qaytarilgan summa" value={usd(totalUsd)} />
          <Stat label="Qaytarilgan dona" value={num(totalUnits)} />
        </div>
      ) : null}

      <Card className="mb-4 text-[13px] leading-relaxed text-[var(--muted)]">
        <b className="text-[var(--fg)]">Qanday qaytariladi?</b>
        <br />
        Buyurtmalar → <b>«Yetkazilgan»</b> bo‘limidan kerakli buyurtmani oching →
        pastdagi <b>«↩️ Tovarni qaytarish (vozvrat)»</b> tugmasini bosing.
        <br />
        <br />
        Qaytarish buyurtma orqali yoziladi — shunda tovar qaysi narxda sotilgan
        bo‘lsa, o‘sha narxda qaytadi. Ombor qoldig‘i, vrachning qarzi, sotuv
        hisoboti va oylik reja bir vaqtda to‘g‘rilanadi.
      </Card>

      <Section title="Tarix">
        {rows.map((r) => (
          <Card key={r.id} className="mb-2 p-0">
            <Row
              title={`${r.doctor_name} · ${r.number}`}
              subtitle={
                [
                  dateTime(r.created_at),
                  r.order_number ? `Buyurtma ${r.order_number}` : null,
                  r.reason,
                ]
                  .filter(Boolean)
                  .join(' · ')
              }
              right={`− ${usd(r.total_usd)}`}
              rightSub={`${num(r.units)} dona`}
              onClick={r.order_id ? () => navigate(`/orders/${r.order_id}`) : undefined}
            />
            {/* Qaysi razmer qaytgani — omborchi uchun eng kerakli ma'lumot */}
            <div className="border-t border-[var(--border)] px-3 py-2">
              {(r.items ?? []).map((item: any) => (
                <div
                  key={item.product_id}
                  className="flex items-baseline justify-between gap-2 py-0.5 text-[13px]"
                >
                  <span className="min-w-0">
                    <b>{item.size ?? '—'}</b>
                    <span className="text-[var(--muted)]">
                      {item.implant_type ? ` · ${item.implant_type}` : ''}
                    </span>
                  </span>
                  <span className="shrink-0 font-semibold">{num(item.qty)} dona</span>
                </div>
              ))}
            </div>
          </Card>
        ))}
        {!isLoading && !rows.length ? (
          <Empty text="Hali qaytarish bo‘lmagan" />
        ) : null}
      </Section>
    </Screen>
  )
}
