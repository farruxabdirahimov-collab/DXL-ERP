import { NavLink } from 'react-router-dom'
import type { Me } from '../api/types'

export interface NavItem {
  to: string
  label: string
  icon: string
}

/** Har bir vazifaning "o'z" bo'limi — bir necha rolli xodim menyusi shundan yig'iladi. */
const ROLE_ITEMS: Record<string, NavItem> = {
  agent: { to: '/doctors', label: 'Vrachlar', icon: '🧑‍⚕️' },
  warehouse: { to: '/stock', label: 'Ombor', icon: '📦' },
  accountant: { to: '/debts', label: 'Qarzlar', icon: '💳' },
  director: { to: '/reports', label: 'Hisobot', icon: '📈' },
  superadmin: { to: '/reports', label: 'Hisobot', icon: '📈' },
  founder: { to: '/reports', label: 'Hisobot', icon: '📈' },
}

/** Kundalik ish uchun qaysi vazifa muhimroq — joy yetmasa shu tartibda beriladi. */
const ROLE_ORDER = ['agent', 'warehouse', 'accountant', 'director', 'superadmin', 'founder']

/**
 * Asosiy rol menyuni belgilaydi. Bitta xodimda bir necha vazifa bo'lsa,
 * menyu qayta yig'iladi: umumiy ikkita bo'lim + har bir vazifadan bittadan.
 *
 * Rol almashtirish yo'q — hamma bo'lim bir vaqtda ochiq turadi. Pastda
 * 4 tagina joy bor, sig'magani "Yana" ichida qoladi.
 */
export function navFor(me: Me): NavItem[] {
  const extras = me.extra_roles ?? []
  if (!extras.length || me.role === 'doctor') return baseNavFor(me)

  const items: NavItem[] = [
    { to: '/', label: 'Bosh', icon: '📊' },
    { to: '/orders', label: 'Buyurtma', icon: '📋' },
  ]
  const roles = [me.role, ...extras].sort(
    (a, b) => ROLE_ORDER.indexOf(a) - ROLE_ORDER.indexOf(b),
  )
  for (const role of roles) {
    const item = ROLE_ITEMS[role]
    if (item && !items.some((existing) => existing.to === item.to)) items.push(item)
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
