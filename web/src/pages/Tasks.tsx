import { useNavigate } from 'react-router-dom'
import { useTasks, useUpdateTask } from '../api/hooks'
import { shortDate } from '../lib/format'
import { haptic } from '../lib/telegram'
import { Card, Chip, Empty, ErrorBox, Loading, Screen } from '../components/ui'

const KIND_ICONS: Record<string, string> = {
  birthday: '🎂',
  sleeping: '😴',
  overdue: '💳',
  manual: '📌',
}

export default function Tasks() {
  const navigate = useNavigate()
  const { data, isLoading, error } = useTasks()
  const update = useUpdateTask()

  async function close(id: number, status: 'done' | 'skipped') {
    await update.mutateAsync({ id, body: { status } })
    haptic('success')
  }

  return (
    <Screen title="Vazifalar" subtitle={`${data?.length ?? 0} ta ochiq vazifa`}>
      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {data?.length === 0 ? <Empty text="Ochiq vazifa yo‘q 🎉" /> : null}

      <div className="space-y-2">
        {(data ?? []).map((task) => {
          const overdue = new Date(task.due_date) < new Date(new Date().toDateString())
          return (
            <Card key={task.id}>
              <div className="mb-2 flex items-start gap-2">
                <span className="text-[18px]">{KIND_ICONS[task.kind] ?? '📌'}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-semibold">{task.title}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <Chip color={overdue ? 'var(--danger)' : undefined}>
                      {shortDate(task.due_date)}
                    </Chip>
                    {task.kind_label ? <Chip>{task.kind_label}</Chip> : null}
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                {task.doctor_id ? (
                  <button
                    className="btn btn-sm flex-1"
                    onClick={() => navigate(`/doctors/${task.doctor_id}`)}
                  >
                    Kartochka
                  </button>
                ) : null}
                {task.doctor_phone ? (
                  <a className="btn btn-sm flex-1" href={`tel:${task.doctor_phone}`}>
                    📞 Qo‘ng‘iroq
                  </a>
                ) : null}
                <button
                  className="btn btn-sm btn-primary flex-1"
                  onClick={() => close(task.id, 'done')}
                >
                  ✓ Bajardim
                </button>
                <button className="btn btn-sm" onClick={() => close(task.id, 'skipped')}>
                  ✕
                </button>
              </div>
            </Card>
          )
        })}
      </div>
    </Screen>
  )
}
