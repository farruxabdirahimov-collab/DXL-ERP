import { useState } from 'react'
import { useCan } from '../App'
import { useSaveTariff, useTariffLadder } from '../api/hooks'
import { num, usd } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Row,
  Screen,
  Section,
  Sheet,
} from '../components/ui'

const BOSH: Record<string, string> = {
  name: '',
  package_qty: '',
  package_price_usd: '',
  term_days: '',
  gift_name: '',
  gift_cost_usd: '',
}

export default function Tariffs() {
  const can = useCan()
  const canEdit = can('tariffs.manage')
  const { data, isLoading, error } = useTariffLadder()
  const save = useSaveTariff()

  const [open, setOpen] = useState(false)
  const [editId, setEditId] = useState<number | undefined>()
  const [form, setForm] = useState<Record<string, string>>(BOSH)

  const set = (key: string, value: string) => setForm({ ...form, [key]: value })

  // Direktor raqam kiritayotganda foydani darhol ko'rib tursin
  const qty = Number(form.package_qty) || 0
  const price = Number(form.package_price_usd) || 0
  const days = Number(form.term_days) || 0
  const gift = Number(form.gift_cost_usd) || 0
  const unit = qty ? price / qty : 0
  const share = price ? (gift / price) * 100 : 0
  const perDay = days ? price / days : 0

  function ochish(tariff?: any) {
    setEditId(tariff?.id)
    setForm(
      tariff
        ? {
            name: tariff.name,
            package_qty: String(tariff.package_qty),
            package_price_usd: String(tariff.package_price_usd),
            term_days: String(tariff.term_days),
            gift_name: tariff.gift_name ?? '',
            gift_cost_usd: String(tariff.gift_cost_usd ?? ''),
          }
        : BOSH,
    )
    setOpen(true)
  }

  async function saqlash() {
    if (!form.name || !qty || !price || !days) {
      alertUser('Nom, dona, summa va muddat majburiy')
      return
    }
    try {
      await save.mutateAsync({
        id: editId,
        body: {
          name: form.name,
          package_qty: qty,
          package_price_usd: form.package_price_usd,
          term_days: days,
          gift_name: form.gift_name || null,
          gift_cost_usd: form.gift_cost_usd || '0',
          is_active: true,
        },
      })
      haptic('success')
      setOpen(false)
      alertUser(editId ? 'Tarif yangilandi' : 'Tarif yaratildi')
    } catch (e: any) {
      alertUser(e?.message ?? 'Saqlanmadi')
    }
  }

  return (
    <Screen title="Tariflar" subtitle="Taklif-shartnoma paketlari">
      {error ? <ErrorBox error={error} /> : null}
      {isLoading ? <Loading /> : null}

      {canEdit ? (
        <button className="btn btn-primary mb-3 w-full" onClick={() => ochish()}>
          + Yangi tarif
        </button>
      ) : null}

      {/* Zinapoya buzilsa — vrach kichik paketni takrorlashni foydali topadi */}
      {data?.warnings?.length ? (
        <Card className="mb-3 border-[var(--warn)] p-3">
          <div className="mb-1 text-[13px] font-semibold text-[var(--warn)]">
            ⚠️ Zinapoya buzilgan
          </div>
          {data.warnings.map((w: string, i: number) => (
            <p key={i} className="text-[12px] text-[var(--muted)]">
              {w}
            </p>
          ))}
          <p className="mt-2 text-[12px] text-[var(--muted)]">
            Sovg‘a ulushi paket kattalashgani sayin <b>oshib borishi</b> kerak —
            aks holda katta paket hech qachon tanlanmaydi.
          </p>
        </Card>
      ) : null}

      <Section title="Paketlar">
        {(data?.tariffs ?? []).map((t: any) => (
          <Card key={t.id} className="mb-2 p-0">
            <Row
              title={`${t.name} · ${num(t.package_qty)} dona`}
              subtitle={`${usd(t.package_price_usd)} · ${t.term_days} kun · ${
                t.gift_name ?? 'sovg‘asiz'
              }`}
              right={`${usd(t.unit_price_usd)}/dona`}
              rightSub={
                t.gift_share_pct != null ? `ulush ${t.gift_share_pct}%` : undefined
              }
              onClick={canEdit ? () => ochish(t) : undefined}
            />
            {t.gift_share_pct != null ? (
              <div className="flex justify-between border-t border-[var(--border)] px-3 py-2 text-[12px] text-[var(--muted)]">
                <span>
                  Sovg‘a {usd(t.gift_cost_usd)} · kunlik aylanma{' '}
                  {usd(t.daily_turnover_usd)}
                </span>
                <span>{t.ladder_ok ? '✅' : '⚠️'}</span>
              </div>
            ) : null}
          </Card>
        ))}
        {!isLoading && !data?.tariffs?.length ? (
          <Empty text="Hali tarif yaratilmagan" />
        ) : null}
      </Section>

      <Sheet
        open={open}
        title={editId ? 'Tarifni tahrirlash' : 'Yangi tarif'}
        onClose={() => setOpen(false)}
      >
        <Field label="Tarif nomi" hint="Vrach shuni ko‘radi. Masalan: Katta-100">
          <input
            className="input"
            value={form.name}
            onChange={(e) => set('name', e.target.value)}
          />
        </Field>
        <Field label="Implant soni">
          <input
            className="input"
            inputMode="numeric"
            value={form.package_qty}
            onChange={(e) => set('package_qty', e.target.value)}
          />
        </Field>
        <Field label="Tarif summasi ($)" hint="Paket qat‘iy narxda — razmerdan qat‘i nazar">
          <input
            className="input"
            inputMode="decimal"
            value={form.package_price_usd}
            onChange={(e) => set('package_price_usd', e.target.value)}
          />
        </Field>
        <Field label="Muddat (kun)" hint="Teskari sanoq shartnoma imzolangandan boshlanadi">
          <input
            className="input"
            inputMode="numeric"
            value={form.term_days}
            onChange={(e) => set('term_days', e.target.value)}
          />
        </Field>
        <Field label="Sovg‘a nomi" hint="Vrach faqat nomini ko‘radi, qiymatini emas">
          <input
            className="input"
            value={form.gift_name}
            onChange={(e) => set('gift_name', e.target.value)}
          />
        </Field>
        <Field label="Sovg‘a tannarxi ($)" hint="Ichki raqam — foyda hisoboti uchun">
          <input
            className="input"
            inputMode="decimal"
            value={form.gift_cost_usd}
            onChange={(e) => set('gift_cost_usd', e.target.value)}
          />
        </Field>

        {/* Raqam kiritilayotganda foyda darhol ko'rinsin */}
        {qty > 0 && price > 0 ? (
          <Card className="mb-3 p-3 text-[13px]">
            <div className="flex justify-between py-0.5">
              <span className="text-[var(--muted)]">Dona narxi</span>
              <b>{usd(unit)}</b>
            </div>
            <div className="flex justify-between py-0.5">
              <span className="text-[var(--muted)]">Sovg‘a ulushi</span>
              <b>{share.toFixed(1)}%</b>
            </div>
            {days > 0 ? (
              <div className="flex justify-between py-0.5">
                <span className="text-[var(--muted)]">Kunlik aylanma</span>
                <b>{usd(perDay)}/kun</b>
              </div>
            ) : null}
            <p className="mt-2 text-[12px] text-[var(--muted)]">
              Kattaroq paketda bu ulush <b>yuqoriroq</b> bo‘lsin — shunda vrach
              ko‘proq olishni foydali deb topadi.
            </p>
          </Card>
        ) : null}

        <button
          className="btn btn-primary w-full"
          disabled={save.isPending}
          onClick={saqlash}
        >
          {save.isPending ? 'Saqlanmoqda…' : 'Saqlash'}
        </button>
      </Sheet>
    </Screen>
  )
}
