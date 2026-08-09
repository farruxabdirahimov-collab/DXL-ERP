import { useState } from 'react'
import { useCan } from '../App'
import {
  useAudiences,
  useBroadcasts,
  useDeletePost,
  useDoctors,
  usePosts,
  useSavePost,
  useSendBroadcast,
} from '../api/hooks'
import type { Post, PostKind } from '../api/types'
import { dateTime, num, shortDate } from '../lib/format'
import { alertUser, confirmUser, haptic } from '../lib/telegram'
import {
  Card,
  Chip,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Row,
  Screen,
  Sheet,
  Tabs,
} from '../components/ui'

const KIND_ICONS: Record<PostKind, string> = {
  article: '📄',
  video: '🎬',
  news: '📢',
}

const KIND_LABELS: Record<PostKind, string> = {
  article: 'Maqola',
  video: 'Video',
  news: 'Yangilik',
}

export default function Content() {
  const can = useCan()
  const canManage = can('content.manage')
  const canBroadcast = can('broadcast.send')

  const [tab, setTab] = useState('all')
  const [reading, setReading] = useState<Post | null>(null)
  const [editing, setEditing] = useState<Partial<Post> | null>(null)
  const [castOpen, setCastOpen] = useState(false)

  const kind = tab === 'all' || tab === 'sent' ? undefined : tab
  const { data: posts, isLoading, error } = usePosts({ kind })
  const savePost = useSavePost()
  const removePost = useDeletePost()
  const { data: broadcasts } = useBroadcasts()

  async function submitPost() {
    if (!editing?.title) {
      alertUser('Sarlavhani yozing')
      return
    }
    try {
      await savePost.mutateAsync({
        id: editing.id,
        body: {
          kind: editing.kind ?? 'article',
          title: editing.title,
          summary: editing.summary || null,
          body: editing.body || null,
          media_url: editing.media_url || null,
          image_url: editing.image_url || null,
          is_published: editing.is_published ?? true,
        },
      })
      haptic('success')
      setEditing(null)
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Saqlashda xatolik')
    }
  }

  async function remove(post: Post) {
    if (!(await confirmUser(`«${post.title}» o'chirilsinmi?`))) return
    await removePost.mutateAsync(post.id)
    haptic('success')
    setReading(null)
  }

  const tabs = [
    { key: 'all', label: 'Hammasi' },
    { key: 'article', label: '📄 Maqola' },
    { key: 'video', label: '🎬 Video' },
    { key: 'news', label: '📢 Yangilik' },
    ...(canBroadcast ? [{ key: 'sent', label: '✉️ Yuborilgan' }] : []),
  ]

  return (
    <Screen
      title="Bilim va yangiliklar"
      subtitle="DXL implantlari haqida materiallar"
      action={
        canManage ? (
          <button
            className="btn btn-sm btn-primary"
            onClick={() => setEditing({ kind: 'article', is_published: true })}
          >
            + Yangi
          </button>
        ) : null
      }
    >
      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      {canBroadcast && tab !== 'sent' ? (
        <button className="btn mb-3 w-full" onClick={() => setCastOpen(true)}>
          ✉️ Rassilka yuborish
        </button>
      ) : null}

      {tab === 'sent' ? (
        <Card className="p-0">
          {(broadcasts ?? []).map((cast) => (
            <Row
              key={cast.id}
              title={cast.text.slice(0, 60)}
              subtitle={`${cast.audience_label ?? cast.audience} · ${dateTime(cast.created_at)}${
                cast.author_name ? ` · ${cast.author_name}` : ''
              }`}
              right={`${num(cast.sent_count)} ta`}
              rightSub={cast.failed_count ? `${cast.failed_count} yetmadi` : 'yetkazildi'}
            />
          ))}
          {!broadcasts?.length ? <Empty text="Hali rassilka yuborilmagan" /> : null}
        </Card>
      ) : (
        <>
          {isLoading ? <Loading /> : null}
          {error ? <ErrorBox error={error} /> : null}
          {posts?.length === 0 ? <Empty text="Material yo'q" /> : null}

          <div className="space-y-2">
            {(posts ?? []).map((post) => (
              <Card key={post.id} onClick={() => setReading(post)}>
                <div className="flex items-start gap-3">
                  <span className="text-[22px]">{KIND_ICONS[post.kind]}</span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[14px] font-semibold">{post.title}</div>
                    {post.summary ? (
                      <div className="mt-0.5 line-clamp-2 text-[12px] text-[var(--muted)]">
                        {post.summary}
                      </div>
                    ) : null}
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      <Chip>{post.kind_label ?? KIND_LABELS[post.kind]}</Chip>
                      <Chip>{shortDate(post.published_at ?? post.created_at)}</Chip>
                      {!post.is_published ? (
                        <Chip color="var(--warn)">Chop etilmagan</Chip>
                      ) : null}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}

      {/* O'qish oynasi */}
      <Sheet
        open={Boolean(reading)}
        title={reading?.title ?? ''}
        onClose={() => setReading(null)}
      >
        {reading ? (
          <>
            <div className="mb-3 flex flex-wrap gap-1.5">
              <Chip>{reading.kind_label ?? KIND_LABELS[reading.kind]}</Chip>
              <Chip>{shortDate(reading.published_at ?? reading.created_at)}</Chip>
              {reading.author_name ? <Chip>{reading.author_name}</Chip> : null}
            </div>

            {reading.image_url ? (
              <img
                src={reading.image_url}
                alt=""
                className="mb-3 w-full rounded-xl"
                loading="lazy"
              />
            ) : null}

            {reading.media_url ? (
              <a
                className="btn btn-primary mb-3 w-full"
                href={reading.media_url}
                target="_blank"
                rel="noreferrer"
              >
                ▶️ Videoni ochish
              </a>
            ) : null}

            {reading.body ? (
              <p className="mb-3 whitespace-pre-wrap text-[14px] leading-relaxed">
                {reading.body}
              </p>
            ) : null}

            {canManage ? (
              <div className="flex gap-2">
                <button
                  className="btn flex-1"
                  onClick={() => {
                    setEditing({ ...reading })
                    setReading(null)
                  }}
                >
                  ✏️ Tahrirlash
                </button>
                <button className="btn btn-danger flex-1" onClick={() => remove(reading)}>
                  🗑 O'chirish
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </Sheet>

      {/* Tahrirlash */}
      <Sheet
        open={Boolean(editing)}
        title={editing?.id ? 'Materialni tahrirlash' : 'Yangi material'}
        onClose={() => setEditing(null)}
      >
        {editing ? (
          <>
            <Field label="Turi">
              <select
                className="select"
                value={editing.kind ?? 'article'}
                onChange={(e) =>
                  setEditing({ ...editing, kind: e.target.value as PostKind })
                }
              >
                <option value="article">📄 Maqola</option>
                <option value="video">🎬 Video</option>
                <option value="news">📢 Yangilik</option>
              </select>
            </Field>
            <Field label="Sarlavha">
              <input
                className="input"
                value={editing.title ?? ''}
                onChange={(e) => setEditing({ ...editing, title: e.target.value })}
              />
            </Field>
            <Field label="Qisqacha" hint="Ro'yxatda ko'rinadi">
              <textarea
                className="textarea"
                rows={2}
                value={editing.summary ?? ''}
                onChange={(e) => setEditing({ ...editing, summary: e.target.value })}
              />
            </Field>
            <Field label="Matn">
              <textarea
                className="textarea"
                rows={7}
                value={editing.body ?? ''}
                onChange={(e) => setEditing({ ...editing, body: e.target.value })}
              />
            </Field>
            <Field label="Video havolasi" hint="YouTube yoki Telegram havolasi">
              <input
                className="input"
                placeholder="https://youtube.com/..."
                value={editing.media_url ?? ''}
                onChange={(e) => setEditing({ ...editing, media_url: e.target.value })}
              />
            </Field>
            <Field label="Rasm havolasi">
              <input
                className="input"
                placeholder="https://..."
                value={editing.image_url ?? ''}
                onChange={(e) => setEditing({ ...editing, image_url: e.target.value })}
              />
            </Field>
            <label className="mb-3 flex items-center gap-2 text-[14px]">
              <input
                type="checkbox"
                checked={editing.is_published ?? true}
                onChange={(e) =>
                  setEditing({ ...editing, is_published: e.target.checked })
                }
              />
              Vrachlarga ko'rinsin
            </label>
            <button
              className="btn btn-primary w-full"
              disabled={savePost.isPending}
              onClick={submitPost}
            >
              {savePost.isPending ? 'Saqlanmoqda…' : 'Saqlash'}
            </button>
          </>
        ) : null}
      </Sheet>

      <BroadcastSheet
        open={castOpen}
        onClose={() => setCastOpen(false)}
        posts={posts ?? []}
      />
    </Screen>
  )
}

function BroadcastSheet({
  open,
  onClose,
  posts,
}: {
  open: boolean
  onClose: () => void
  posts: Post[]
}) {
  const { data: audiences } = useAudiences()
  const { data: doctors } = useDoctors({ limit: 500 })
  const send = useSendBroadcast()

  const [text, setText] = useState('')
  const [audience, setAudience] = useState('all_doctors')
  const [doctorId, setDoctorId] = useState<number | undefined>()
  const [postId, setPostId] = useState<number | undefined>()

  const selected = audiences?.find((a) => a.value === audience)

  async function submit() {
    if (!text.trim()) {
      alertUser('Xabar matnini yozing')
      return
    }
    if (audience === 'one_doctor' && !doctorId) {
      alertUser('Vrachni tanlang')
      return
    }
    try {
      const result = await send.mutateAsync({
        text,
        audience,
        doctor_id: audience === 'one_doctor' ? doctorId : null,
        post_id: postId ?? null,
      })
      haptic('success')
      alertUser(
        `✅ Yuborildi: ${result.sent_count} ta${
          result.failed_count ? `, ${result.failed_count} tasiga yetmadi` : ''
        }`,
      )
      setText('')
      setPostId(undefined)
      onClose()
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  return (
    <Sheet open={open} title="Rassilka yuborish" onClose={onClose}>
      <Field label="Kimga">
        <select
          className="select"
          value={audience}
          onChange={(e) => setAudience(e.target.value)}
        >
          {(audiences ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
              {option.count !== null ? ` (${option.count} ta)` : ''}
            </option>
          ))}
        </select>
      </Field>

      {audience === 'one_doctor' ? (
        <Field label="Vrach">
          <select
            className="select"
            value={doctorId ?? ''}
            onChange={(e) => setDoctorId(Number(e.target.value))}
          >
            <option value="">Tanlang</option>
            {(doctors ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.full_name} — {d.clinic_name ?? d.phone}
              </option>
            ))}
          </select>
        </Field>
      ) : null}

      <Field label="Xabar matni">
        <textarea
          className="textarea"
          rows={6}
          placeholder="Hurmatli hamkasb! ..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      </Field>

      <Field label="Material biriktirish" hint="Ixtiyoriy — xabarga tugma qo'shiladi">
        <select
          className="select"
          value={postId ?? ''}
          onChange={(e) => setPostId(e.target.value ? Number(e.target.value) : undefined)}
        >
          <option value="">Biriktirilmasin</option>
          {posts
            .filter((p) => p.is_published)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
        </select>
      </Field>

      {selected?.count === 0 ? (
        <div className="mb-3 text-[13px]" style={{ color: 'var(--warn)' }}>
          ⚠️ Bu guruhda Telegram'ga ulangan odam yo'q
        </div>
      ) : null}

      <button
        className="btn btn-primary w-full"
        disabled={send.isPending}
        onClick={submit}
      >
        {send.isPending ? 'Yuborilmoqda…' : '✉️ Yuborish'}
      </button>
    </Sheet>
  )
}
