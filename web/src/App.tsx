import { createContext, useContext } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useMe } from './api/hooks'
import type { Me } from './api/types'
import { BottomNav, navFor } from './components/Nav'
import { ErrorBox, Loading } from './components/ui'

import Dashboard from './pages/Dashboard'
import Catalog from './pages/Catalog'
import Content from './pages/Content'
import Stock from './pages/Stock'
import Doctors from './pages/Doctors'
import DoctorPage from './pages/DoctorPage'
import Orders from './pages/Orders'
import OrderPage from './pages/OrderPage'
import NewOrder from './pages/NewOrder'
import Contracts from './pages/Contracts'
import Payments from './pages/Payments'
import Profit from './pages/Profit'
import Tariffs from './pages/Tariffs'
import Returns from './pages/Returns'
import Debts from './pages/Debts'
import MyDebt from './pages/MyDebt'
import Reports from './pages/Reports'
import Plan from './pages/Plan'
import Visits from './pages/Visits'
import Tasks from './pages/Tasks'
import More from './pages/More'
import Users from './pages/Users'
import SettingsPage from './pages/SettingsPage'
import Audit from './pages/Audit'

const MeContext = createContext<Me | null>(null)

export function useCurrentUser(): Me {
  const me = useContext(MeContext)
  if (!me) throw new Error('Foydalanuvchi konteksti topilmadi')
  return me
}

export function useCan(): (permission: string) => boolean {
  const me = useCurrentUser()
  return (permission: string) => me.permissions.includes(permission)
}

export default function App() {
  const { data: me, isLoading, error } = useMe()

  if (isLoading) return <Loading />

  if (error || !me) {
    return (
      <div className="p-4 pt-10">
        <div className="mb-4 text-center text-[40px]">🦷</div>
        <h1 className="mb-3 text-center text-[19px] font-bold">DXL ERP</h1>
        <ErrorBox error={error ?? new Error('Kirish amalga oshmadi')} />
        <p className="mt-4 text-center text-[13px] text-[var(--muted)]">
          Ilovani Telegram bot orqali oching. Muammo davom etsa rahbaringizga
          murojaat qiling.
        </p>
      </div>
    )
  }

  const items = navFor(me)
  const isDoctor = me.role === 'doctor'

  return (
    <MeContext.Provider value={me}>
      <div className="min-h-full" style={{ background: 'var(--bg)' }}>
        <Routes>
          <Route
            path="/"
            element={isDoctor ? <Navigate to="/catalog" replace /> : <Dashboard />}
          />
          <Route path="/catalog" element={<Catalog />} />
          <Route path="/content" element={<Content />} />
          <Route path="/content/:id" element={<Content />} />
          <Route path="/stock" element={<Stock />} />
          <Route path="/doctors" element={<Doctors />} />
          <Route path="/doctors/:id" element={<DoctorPage />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/orders/:id" element={<OrderPage />} />
          <Route path="/new-order" element={<NewOrder />} />
          <Route path="/payments" element={<Payments />} />
          <Route path="/debts" element={<Debts />} />
          <Route path="/contracts" element={<Contracts />} />
          <Route path="/profit" element={<Profit />} />
          <Route path="/tariffs" element={<Tariffs />} />
          <Route path="/returns" element={<Returns />} />
          <Route path="/my-debt" element={<MyDebt />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/plan" element={<Plan />} />
          <Route path="/visits" element={<Visits />} />
          <Route path="/tasks" element={<Tasks />} />
          <Route path="/more" element={<More />} />
          <Route path="/users" element={<Users />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/audit" element={<Audit />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <BottomNav items={items} />
      </div>
    </MeContext.Provider>
  )
}
