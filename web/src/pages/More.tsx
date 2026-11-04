import { useNavigate } from 'react-router-dom'
import { useCan, useCurrentUser } from '../App'
import { useFxRate, useTasks } from '../api/hooks'
import { num } from '../lib/format'
import { openExternal, shareToTelegram } from '../lib/telegram'
import { Card, Row, Screen, Section } from '../components/ui'

// Vrach loginsiz ochadigan sahifa — matn bot /finscan bilan bir xil
const FINSCAN_URL = `${window.location.origin}/finscan`
const FINSCAN_TEXT =
  "FinScan 360 + DXL implant paketi. O'zingizga mos shartni va raqamlarni kiriting yoki tanlang va to'lov grafigini ko'ring."

export default function More() {
  const me = useCurrentUser()
  const can = useCan()
  const navigate = useNavigate()
  const { data: tasks } = useTasks()
  const { data: fx } = useFxRate()

  const items: { to: string; label: string; icon: string; show: boolean; badge?: string }[] =
    [
      {
        to: '/tasks',
        label: 'Vazifalar',
        icon: '📌',
        show: true,
        badge: tasks?.length ? String(tasks.length) : undefined,
      },
      { to: '/catalog', label: 'Mahsulotlar katalogi', icon: '🦷', show: can('products.view') },
      { to: '/stock', label: 'Ombor', icon: '📦', show: can('stock.view') },
      { to: '/doctors', label: 'Vrachlar', icon: '🧑‍⚕️', show: can('doctors.view') },
      { to: '/orders', label: 'Buyurtmalar', icon: '📋', show: can('orders.view') },
      { to: '/payments', label: 'To‘lovlar', icon: '💰', show: can('payments.view') },
      { to: '/debts', label: 'Qarzdorlik', icon: '💳', show: can('payments.view') },
      { to: '/contracts', label: 'Shartnomalar', icon: '📝', show: can('contracts.view') },
      { to: '/tariffs', label: 'Tariflar', icon: '🏷️', show: can('tariffs.manage') },
      { to: '/returns', label: 'Qaytarishlar', icon: '↩️', show: can('returns.create') },
      { to: '/content', label: 'Bilim va rassilka', icon: '📚', show: can('content.view') },
      { to: '/reports', label: 'Hisobotlar', icon: '📈', show: can('reports.view') },
      { to: '/profit', label: 'Foyda-zarar', icon: '💹', show: can('reports.finance') },
      { to: '/plan', label: 'Oylik reja', icon: '🎯', show: can('plans.view') },
      { to: '/salary', label: 'Oyligim', icon: '💵', show: can('plans.view') },
      {
        to: '/visits',
        label: 'Tashriflar',
        icon: '📍',
        show: can('visits.own') || can('visits.all'),
      },
      { to: '/users', label: 'Xodimlar va rollar', icon: '👥', show: can('users.manage') },
      { to: '/settings', label: 'Sozlamalar', icon: '⚙️', show: can('settings.manage') },
      { to: '/audit', label: 'Audit jurnali', icon: '🔍', show: can('audit.view') },
    ]

  return (
    <Screen title="Yana" subtitle={`${me.full_name} · ${me.role_label}`}>
      <Section title="Bo‘limlar">
        <Card className="p-0">
          {items
            .filter((item) => item.show)
            .map((item) => (
              <Row
                key={item.to}
                title={
                  <span>
                    <span className="mr-2">{item.icon}</span>
                    {item.label}
                  </span>
                }
                right={item.badge ?? '›'}
                onClick={() => navigate(item.to)}
              />
            ))}
        </Card>
      </Section>

      <Section title="Vrachga ko‘rsatish">
        <Card>
          <div className="text-[15px] font-semibold">🩻 FinScan 360 + DXL implant</div>
          <div className="mt-1 text-[13px] text-[var(--muted)]">
            Vrach o‘ziga mos shartni tanlaydi va to‘lov grafigini ko‘radi. Havola loginsiz ochiladi.
          </div>
          <div className="mt-3 flex gap-2">
            <button className="btn btn-primary flex-1" onClick={() => shareToTelegram(FINSCAN_URL, FINSCAN_TEXT)}>
              ➤ Vrachga yuborish
            </button>
            <button className="btn flex-1" onClick={() => openExternal(FINSCAN_URL)}>
              Ochish
            </button>
          </div>
        </Card>
      </Section>

      <Section title="Ma’lumot">
        <Card className="p-0">
          <Row title="Rolingiz" right={me.role_label} />
          <Row title="Telefon" right={me.phone ?? '—'} />
          {fx ? (
            <Row title="Bugungi kurs" right={`1$ = ${num(fx.usd_uzs)} so'm`} />
          ) : null}
          <Row title="Telegram ID" right={me.telegram_id ?? '—'} />
        </Card>
      </Section>

      <div className="mt-4 text-center text-[12px] text-[var(--muted)]">
        DXL Dental Implant ERP · v1.0
      </div>
    </Screen>
  )
}
