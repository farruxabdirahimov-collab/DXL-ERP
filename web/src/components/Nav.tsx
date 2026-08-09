import { NavLink } from 'react-router-dom'
import type { Me } from '../api/types'

export interface NavItem {
  to: string
  label: string
  icon: string
}

/** Rolga qarab pastki menyu (eng ko'p 5 ta bo'lim). */
const EXTRA_ITEMS: Record<string, NavItem> = {
  warehouse: { to: '/stock', label: 'Ombor', icon: '📦' },
  accountant: { to: '/debts', label: 'Qarzlar', icon: '💳' },
  agent: { to: '/doctors', label: 'Vrachlar', icon: '🧑‍⚕️' },
  director: { to: '/reports', label: 'Hisobot', icon: '📈' },
}

/** Asosiy rol menyuni belgilaydi, qo'shimcha rollar unga qo'shiladi. */
export function navFor(me: Me): NavItem[] {
  const base = baseNavFor(me)
  if (!me.extra_roles?.length) return base

  const items = base.filter((item) => item.to !== '/more')
  for (const role of me.extra_roles) {
    const extra = EXTRA_ITEMS[role]
    if (extra && !items.some((item) => item.to === extra.to)) items.push(extra)
  }
  // Pastki menyuda eng ko'pi 5 ta joy bor, oxirgisi doim "Yana"
  return [...items.slice(0, 4), { to: '/more', label: 'Yana', icon: '☰' }]
}

function baseNavFor(me: Me): NavItem[] {
  switch (me.role) {
    case 'doctor':
      return [
        { to: '/catalog', label: 'Katalog', icon: '🦷' },
        { to: '/new-order', label: 'Buyurtma', icon: '🛒' },
        { to: '/content', label: 'Bilim', icon: '📚' },
        { to: '/orders', label: 'Tarix', icon: '📋' },
        { to: '/my-debt', label: 'Hisobim', icon: '💳' },
      ]
    case 'agent':
      return [
        { to: '/', label: 'Bosh', icon: '📊' },
        { to: '/doctors', label: 'Vrachlar', icon: '🧑‍⚕️' },
        { to: '/orders', label: 'Buyurtma', icon: '📋' },
        { to: '/plan', label: 'Reja', icon: '🎯' },
        { to: '/more', label: 'Yana', icon: '☰' },
      ]
    case 'warehouse':
      return [
        { to: '/', label: 'Bosh', icon: '📊' },
        { to: '/stock', label: 'Ombor', icon: '📦' },
        { to: '/orders', label: 'Buyurtma', icon: '📋' },
        { to: '/catalog', label: 'Katalog', icon: '🦷' },
        { to: '/more', label: 'Yana', icon: '☰' },
      ]
    case 'accountant':
      return [
        { to: '/', label: 'Bosh', icon: '📊' },
        { to: '/debts', label: 'Qarzlar', icon: '💳' },
        { to: '/payments', label: 'To‘lov', icon: '💰' },
        { to: '/doctors', label: 'Vrachlar', icon: '🧑‍⚕️' },
        { to: '/more', label: 'Yana', icon: '☰' },
      ]
    default:
      return [
        { to: '/', label: 'Bosh', icon: '📊' },
        { to: '/orders', label: 'Buyurtma', icon: '📋' },
        { to: '/doctors', label: 'Vrachlar', icon: '🧑‍⚕️' },
        { to: '/reports', label: 'Hisobot', icon: '📈' },
        { to: '/more', label: 'Yana', icon: '☰' },
      ]
  }
}

export function BottomNav({ items }: { items: NavItem[] }) {
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex border-t"
      style={{
        background: 'var(--card)',
        borderColor: 'var(--border)',
        paddingBottom: 'var(--safe-bottom)',
      }}
    >
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className="flex flex-1 flex-col items-center gap-0.5 py-2"
          style={({ isActive }) => ({
            color: isActive ? 'var(--accent)' : 'var(--muted)',
          })}
        >
          <span className="text-[19px] leading-none">{item.icon}</span>
          <span className="text-[10.5px] font-semibold">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
