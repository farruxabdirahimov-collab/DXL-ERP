import { useState } from 'react'
import { useCreateInvite, useInvites, useSaveUser, useUsers } from '../api/hooks'
import type { Role, UserRow } from '../api/types'
import { dateTime, shortDate } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Chip,
  CopyLink,
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

const ROLE_LABELS: Record<Role, string> = {
  superadmin: 'Super-admin',
  director: 'Direktor',
  founder: 'Ta’sischi',
  accountant: 'Buxgalter',
  warehouse: 'Omborchi',
  agent: 'Sotuv agenti',
  doctor: 'Vrach',
}

const ROLE_HINTS: Record<Role, string> = {
  superadmin: 'Hamma narsa + tizim sozlamalari',
  director: 'Hamma narsa, xodim qo‘shish, tasdiqlash',
  founder: 'Faqat ko‘rish (read-only)',
  accountant: 'To‘lov, qarz, moliyaviy hisobot',
  warehouse: 'Ombor, kirim/chiqim, buyurtma yig‘ish',
  agent: 'O‘z vrachlari, buyurtma, to‘lov yig‘ish',
  doctor: 'Mijoz — katalog, buyurtma, o‘z qarzi',
}

export default function Users() {
  const [tab, setTab] = useState('users')
  const [inviteOpen, setInviteOpen] = useState(false)
  const [editing, setEditing] = useState<UserRow | null>(null)

  const { data: users, isLoading, error } = useUsers({ only_active: false })
  const { data: invites } = useInvites()
  const createInvite = useCreateInvite()
  const saveUser = useSaveUser()

  const [createdLink, setCreatedLink] = useState<string | null>(null)
  const [shownInvite, setShownInvite] = useState<{ name: string; link: string } | null>(
    null,
  )

  const [form, setForm] = useState<{
    full_name: string
    role: Role
    phone: string
    has_own_stock: boolean
  }>({ full_name: '', role: 'agent', phone: '', has_own_stock: false })

  async function submitInvite() {
    if (!form.full_name.trim()) {
      alertUser('Xodimning ismini yozing')
      return
    }
    try {
      const invite = await createInvite.mutateAsync({
        full_name: form.full_name,
        role: form.role,
        phone: form.phone || null,
        has_own_stock: form.has_own_stock,
        valid_days: 7,
      })
      haptic('success')
      alertUser(
        `Taklif havolasi tayyor:\n${invite.link}\n\nShu havolani xodimga yuboring — u bosgach avtomatik ro‘yxatdan o‘tadi.`,
      )
      setInviteOpen(false)
      setForm({ full_name: '', role: 'agent', phone: '', has_own_stock: false })
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  async function toggleActive(user: UserRow) {
    try {
      await saveUser.mutateAsync({ id: user.id, body: { is_active: !user.is_active } })
      haptic('success')
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  async function saveEdit() {
    if (!editing) return
    try {
      await saveUser.mutateAsync({
        id: editing.id,
        body: {
          full_name: editing.full_name,
          role: editing.role,
          phone: editing.phone,
          has_own_stock: editing.has_own_stock,
        },
      })
      haptic('success')
      setEditing(null)
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  return (
    <Screen
      title="Xodimlar"
      subtitle={`${users?.length ?? 0} ta foydalanuvchi`}
      action={
        <button className="btn btn-sm btn-primary" onClick={() => setInviteOpen(true)}>
          + Taklif
        </button>
      }
    >
      <Tabs
        tabs={[
          { key: 'users', label: 'Xodimlar' },
          { key: 'invites', label: `Taklifnomalar (${invites?.length ?? 0})` },
        ]}
        active={tab}
        onChange={setTab}
      />

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}

      {tab === 'users' ? (
        <div className="space-y-2">
          {(users ?? []).map((user) => (
            <Card key={user.id}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-semibold">
                    {user.full_name}
                  </div>
                  <div className="text-[12px] text-[var(--muted)]">
                    {user.phone ?? 'telefon yo‘q'}
                    {user.telegram_username ? ` · @${user.telegram_username}` : ''}
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <Chip>{ROLE_LABELS[user.role]}</Chip>
                    {!user.is_active ? (
                      <Chip color="var(--danger)">Faolsiz</Chip>
                    ) : null}
                    {user.has_own_stock ? <Chip>📦 Qo‘l ombori</Chip> : null}
                    {!user.telegram_id ? (
                      <Chip color="var(--warn)">Telegram ulanmagan</Chip>
                    ) : null}
                  </div>
                </div>
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  className="btn btn-sm flex-1"
                  onClick={() => setEditing({ ...user })}
                >
                  ✏️ Tahrirlash
                </button>
                <button className="btn btn-sm flex-1" onClick={() => toggleActive(user)}>
                  {user.is_active ? '⏸ To‘xtatish' : '▶️ Faollashtirish'}
                </button>
              </div>
            </Card>
          ))}
          {users?.length === 0 ? <Empty /> : null}
        </div>
      ) : (
        <Card className="p-0">
          {(invites ?? []).map((invite: any) => (
            <Row
              key={invite.id}
              title={invite.full_name}
              subtitle={`${ROLE_LABELS[invite.role as Role]} · amal qiladi ${shortDate(invite.expires_at)}`}
              right="📋"
              onClick={() =>
                setShownInvite({
                  name: invite.full_name,
                  link: invite.link ?? invite.token,
                })
              }
            />
          ))}
          {!invites?.length ? <Empty text="Faol taklifnoma yo‘q" /> : null}
        </Card>
      )}

      {/* Yangi taklifnoma */}
      <Sheet
        open={inviteOpen}
        title="Xodimni taklif qilish"
        onClose={() => setInviteOpen(false)}
      >
        <Field label="F.I.O.">
          <input
            className="input"
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          />
        </Field>
        <Field label="Rol" hint={ROLE_HINTS[form.role]}>
          <select
            className="select"
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
          >
            {(Object.keys(ROLE_LABELS) as Role[])
              .filter((role) => role !== 'doctor')
              .map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABELS[role]}
                </option>
              ))}
          </select>
        </Field>
        <Field label="Telefon (ixtiyoriy)">
          <input
            className="input"
            inputMode="tel"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
          />
        </Field>
        {form.role === 'agent' ? (
          <label className="mb-3 flex items-center gap-2 text-[14px]">
            <input
              type="checkbox"
              checked={form.has_own_stock}
              onChange={(e) => setForm({ ...form, has_own_stock: e.target.checked })}
            />
            Qo‘l ombori bo‘lsin (agent o‘zida tovar olib yuradi)
          </label>
        ) : null}
        <button
          className="btn btn-primary w-full"
          disabled={createInvite.isPending}
          onClick={submitInvite}
        >
          {createInvite.isPending ? 'Yaratilmoqda…' : 'Taklif havolasini yaratish'}
        </button>
      </Sheet>

      {/* Yangi yaratilgan havola */}
      <Sheet
        open={Boolean(createdLink)}
        title="Taklif havolasi tayyor"
        onClose={() => setCreatedLink(null)}
      >
        <p className="mb-3 text-[13px] text-[var(--muted)]">
          Shu havolani xodimga yuboring. U havolani bosgach avtomatik ro'yxatdan
          o'tadi — parol yoki qo'shimcha ro'yxatdan o'tish kerak emas.
        </p>
        {createdLink ? <CopyLink url={createdLink} /> : null}
      </Sheet>

      {/* Ro'yxatdan tanlangan havola */}
      <Sheet
        open={Boolean(shownInvite)}
        title={shownInvite?.name ?? ''}
        onClose={() => setShownInvite(null)}
      >
        {shownInvite ? <CopyLink url={shownInvite.link} label="Taklif havolasi" /> : null}
      </Sheet>

      {/* Tahrirlash */}
      <Sheet
        open={Boolean(editing)}
        title="Xodimni tahrirlash"
        onClose={() => setEditing(null)}
      >
        {editing ? (
          <>
            <Field label="F.I.O.">
              <input
                className="input"
                value={editing.full_name}
                onChange={(e) => setEditing({ ...editing, full_name: e.target.value })}
              />
            </Field>
            <Field label="Rol" hint={ROLE_HINTS[editing.role]}>
              <select
                className="select"
                value={editing.role}
                onChange={(e) =>
                  setEditing({ ...editing, role: e.target.value as Role })
                }
              >
                {(Object.keys(ROLE_LABELS) as Role[]).map((role) => (
                  <option key={role} value={role}>
                    {ROLE_LABELS[role]}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Telefon">
              <input
                className="input"
                inputMode="tel"
                value={editing.phone ?? ''}
                onChange={(e) => setEditing({ ...editing, phone: e.target.value })}
              />
            </Field>
            {editing.role === 'agent' ? (
              <label className="mb-3 flex items-center gap-2 text-[14px]">
                <input
                  type="checkbox"
                  checked={editing.has_own_stock}
                  onChange={(e) =>
                    setEditing({ ...editing, has_own_stock: e.target.checked })
                  }
                />
                Qo‘l ombori bo‘lsin
              </label>
            ) : null}
            <div className="mb-3 text-[12px] text-[var(--muted)]">
              Oxirgi faollik: {dateTime(editing.last_seen_at)}
            </div>
            <button
              className="btn btn-primary w-full"
              disabled={saveUser.isPending}
              onClick={saveEdit}
            >
              Saqlash
            </button>
          </>
        ) : null}
      </Sheet>
    </Screen>
  )
}
