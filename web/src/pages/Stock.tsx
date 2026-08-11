import { useMemo, useState } from 'react'
import { useCan } from '../App'
import {
  useLowStock,
  useProducts,
  useStock,
  useStockAction,
  useStockByWarehouse,
  useStockMoves,
  useWarehouses,
} from '../api/hooks'
import { api } from '../api/client'
import { dateTime, num, usd } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Row,
  Screen,
  Sheet,
  Tabs,
} from '../components/ui'

const MOVE_LABELS: Record<string, string> = {
  in: 'Kirim',
  transfer: 'Ko‘chirish',
  sale: 'Sotuv',
  return: 'Qaytarish',
  writeoff: 'Spisaniye',
  adjust: 'Korreksiya',
}

interface Line {
  product_id: number
  name: string
  qty: number
  cost_usd?: string
}

export default function Stock() {
  const can = useCan()
  const canEdit = can('stock.edit')

  const [tab, setTab] = useState('balances')
  const [warehouseId, setWarehouseId] = useState<number | undefined>()
  const [search, setSearch] = useState('')
  const [action, setAction] = useState<
    'receipt' | 'transfer' | 'writeoff' | 'adjust' | null
  >(null)

  const { data: warehouses } = useWarehouses()
  const { data: balances, isLoading, error } = useStock(warehouseId)
  const { data: low } = useLowStock()
  const { data: byWarehouse } = useStockByWarehouse()
  const { data: moves } = useStockMoves({ warehouse_id: warehouseId, limit: 100 })

  const filtered = useMemo(() => {
    const rows = tab === 'low' ? (low ?? []) : (balances ?? [])
    if (!search) return rows
    const needle = search.toLowerCase()
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(needle) || r.sku.toLowerCase().includes(needle),
    )
  }, [tab, low, balances, search])

  const totalValue = (balances ?? []).reduce((sum, r) => sum + Number(r.value_usd), 0)

  return (
    <Screen
      title="Ombor"
      subtitle={`Umumiy qiymat: ${usd(totalValue, 0)}`}
      action={
        canEdit ? (
          <button className="btn btn-sm btn-primary" onClick={() => setAction('receipt')}>
            + Kirim
          </button>
        ) : null
      }
    >
      {warehouses && warehouses.length > 1 ? (
        <select
          className="select mb-3"
          value={warehouseId ?? ''}
          onChange={(e) =>
            setWarehouseId(e.target.value ? Number(e.target.value) : undefined)
          }
        >
          <option value="">Barcha omborlar</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
      ) : null}

      <Tabs
        tabs={[
          { key: 'balances', label: 'Qoldiq' },
          { key: 'low', label: `Kam qolgan (${low?.length ?? 0})` },
          { key: 'warehouses', label: 'Omborlar' },
          { key: 'moves', label: 'Harakat' },
        ]}
        active={tab}
        onChange={setTab}
      />

      {canEdit ? (
        <div className="scroll-x mb-3 flex gap-2">
          <button className="btn btn-sm" onClick={() => setAction('transfer')}>
            ↔️ Ko‘chirish
          </button>
          <button className="btn btn-sm" onClick={() => setAction('adjust')}>
            🔢 Inventarizatsiya
          </button>
          <button className="btn btn-sm" onClick={() => setAction('writeoff')}>
            🗑 Spisaniye
          </button>
          <button
            className="btn btn-sm"
            onClick={() => api.download('/reports/export.xlsx', { kind: 'stock' })}
          >
            ⬇️ Excel
          </button>
        </div>
      ) : null}

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}

      {tab === 'warehouses' ? (
        <Card className="p-0">
          {(byWarehouse ?? []).map((w) => (
            <Row
              key={w.warehouse_id}
              title={w.name}
              subtitle={`${w.kind === 'main' ? 'Markaziy' : 'Agent ombori'} · ${num(w.skus)} nomda`}
              right={`${num(w.qty)} dona`}
              rightSub={usd(w.value_usd, 0)}
            />
          ))}
          {!byWarehouse?.length ? <Empty /> : null}
        </Card>
      ) : null}

      {tab === 'moves' ? (
        <Card className="p-0">
          {(moves ?? []).map((move: any) => (
            <Row
              key={move.id}
              title={move.product}
              subtitle={`${MOVE_LABELS[move.kind] ?? move.kind} · ${dateTime(move.created_at)}${
                move.user ? ` · ${move.user}` : ''
              }`}
              right={`${['in', 'return', 'transfer'].includes(move.kind) ? '+' : '−'}${num(move.qty)}`}
            />
          ))}
          {!moves?.length ? <Empty text="Harakat yo‘q" /> : null}
        </Card>
      ) : null}

      {tab === 'balances' || tab === 'low' ? (
        <>
          <input
            className="input mb-3"
            placeholder="Qidirish…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Card className="p-0">
            {filtered.map((row) => {
              const critical = row.qty <= 0
              const lowStock = row.min_stock > 0 && row.qty <= row.min_stock
              return (
                <Row
                  key={row.product_id}
                  title={row.name}
                  subtitle={
                    <>
                      {row.sku}
                      {row.size && row.size !== '—' ? ` · ${row.size}` : ''}
                      {tab === 'low' && row.days_left != null
                        ? ` · ~${row.days_left} kunga yetadi`
                        : ''}
                    </>
                  }
                  right={
                    <span
                      style={{
                        color: critical
                          ? 'var(--danger)'
                          : lowStock
                            ? 'var(--warn)'
                            : undefined,
                      }}
                    >
                      {num(row.qty)}
                    </span>
                  }
                  rightSub={
                    row.reserved > 0
                      ? `band ${num(row.reserved)} · min ${num(row.min_stock)}`
                      : `min ${num(row.min_stock)}`
                  }
                />
              )
            })}
            {filtered.length === 0 ? <Empty /> : null}
          </Card>
        </>
      ) : null}

      <StockActionSheet
        action={action}
        onClose={() => setAction(null)}
        warehouses={warehouses ?? []}
        defaultWarehouseId={warehouseId}
      />
    </Screen>
  )
}

function StockActionSheet({
  action,
  onClose,
  warehouses,
  defaultWarehouseId,
}: {
  action: 'receipt' | 'transfer' | 'writeoff' | 'adjust' | null
  onClose: () => void
  warehouses: { id: number; name: string; kind: string }[]
  defaultWarehouseId?: number
}) {
  const [search, setSearch] = useState('')
  const [lines, setLines] = useState<Line[]>([])
  const [fromId, setFromId] = useState<number | undefined>(defaultWarehouseId)
  const [toId, setToId] = useState<number | undefined>()
  const [reason, setReason] = useState('')
  const [supplier, setSupplier] = useState('')
  const [adjustQty, setAdjustQty] = useState('0')

  const { data: products } = useProducts({ search: search || undefined, limit: 40 })

  const endpoint =
    action === 'receipt'
      ? '/stock/receipts'
      : action === 'transfer'
        ? '/stock/transfers'
        : action === 'writeoff'
          ? '/stock/writeoffs'
          : '/stock/adjust'
  const mutation = useStockAction(endpoint)

  const titles = {
    receipt: 'Kirim (yetkazib beruvchidan)',
    transfer: 'Omborlar orasida ko‘chirish',
    writeoff: 'Spisaniye',
    adjust: 'Inventarizatsiya',
  }

  function addLine(product: { id: number; name: string }) {
    setLines((prev) =>
      prev.some((l) => l.product_id === product.id)
        ? prev
        : [...prev, { product_id: product.id, name: product.name, qty: 1 }],
    )
    setSearch('')
  }

  function setQty(productId: number, qty: number) {
    setLines((prev) =>
      prev.map((l) => (l.product_id === productId ? { ...l, qty } : l)),
    )
  }

  async function submit() {
    try {
      let body: Record<string, unknown>
      if (action === 'adjust') {
        if (lines.length !== 1) {
          alertUser('Bitta mahsulot tanlang')
          return
        }
        body = {
          warehouse_id: fromId ?? warehouses[0]?.id,
          product_id: lines[0].product_id,
          new_qty: Number(adjustQty),
          note: reason || null,
        }
      } else if (action === 'transfer') {
        if (!fromId || !toId) {
          alertUser('Qaysi ombordan qaysi omborga — tanlang')
          return
        }
        body = {
          from_warehouse_id: fromId,
          to_warehouse_id: toId,
          note: reason || null,
          lines: lines.map((l) => ({ product_id: l.product_id, qty: l.qty })),
        }
      } else if (action === 'writeoff') {
        if (!reason.trim()) {
          alertUser('Spisaniye sababini yozing')
          return
        }
        body = {
          warehouse_id: fromId ?? warehouses[0]?.id,
          reason,
          lines: lines.map((l) => ({ product_id: l.product_id, qty: l.qty })),
        }
      } else {
        body = {
          warehouse_id: fromId,
          supplier: supplier || null,
          note: reason || null,
          lines: lines.map((l) => ({
            product_id: l.product_id,
            qty: l.qty,
            cost_usd: l.cost_usd ?? '0',
          })),
        }
      }

      const result = await mutation.mutateAsync(body)
      haptic('success')
      alertUser(result.message ?? 'Bajarildi')
      setLines([])
      setReason('')
      onClose()
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Xatolik')
    }
  }

  return (
    <Sheet
      open={Boolean(action)}
      title={action ? titles[action] : ''}
      onClose={onClose}
    >
      {action === 'transfer' ? (
        <div className="grid grid-cols-2 gap-2">
          <Field label="Qaysi ombordan">
            <select
              className="select"
              value={fromId ?? ''}
              onChange={(e) => setFromId(Number(e.target.value))}
            >
              <option value="">Tanlang</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Qaysi omborga">
            <select
              className="select"
              value={toId ?? ''}
              onChange={(e) => setToId(Number(e.target.value))}
            >
              <option value="">Tanlang</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
      ) : (
        <Field label="Ombor">
          <select
            className="select"
            value={fromId ?? ''}
            onChange={(e) => setFromId(Number(e.target.value))}
          >
            <option value="">Tanlang</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </Field>
      )}

      {action === 'receipt' ? (
        <Field label="Yetkazib beruvchi">
          <input
            className="input"
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
            placeholder="Masalan: DXL Korea"
          />
        </Field>
      ) : null}

      <Field label="Mahsulot qo‘shish">
        <input
          className="input"
          placeholder="Nomi yoki SKU…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Field>

      {search && products ? (
        <Card className="mb-3 max-h-52 overflow-y-auto p-0">
          {products.slice(0, 20).map((p) => (
            <Row
              key={p.id}
              title={p.name}
              subtitle={`${p.sku} · omborda ${num(p.qty)}`}
              onClick={() => addLine(p)}
            />
          ))}
        </Card>
      ) : null}

      {lines.length > 0 ? (
        <Card className="mb-3 p-0">
          {lines.map((line) => (
            <div
              key={line.product_id}
              className="flex items-center gap-2 border-b border-[var(--border)] p-2 last:border-b-0"
            >
              <div className="min-w-0 flex-1 truncate text-[13px]">{line.name}</div>
              {action === 'adjust' ? (
                <input
                  className="input w-24 shrink-0 text-right"
                  inputMode="numeric"
                  value={adjustQty}
                  onChange={(e) => setAdjustQty(e.target.value)}
                />
              ) : (
                <input
                  className="input w-20 shrink-0 text-right"
                  inputMode="numeric"
                  value={line.qty}
                  onChange={(e) => setQty(line.product_id, Number(e.target.value))}
                />
              )}
              <button
                className="btn btn-sm"
                onClick={() =>
                  setLines((prev) => prev.filter((l) => l.product_id !== line.product_id))
                }
              >
                ✕
              </button>
            </div>
          ))}
        </Card>
      ) : null}

      <Field
        label={action === 'writeoff' ? 'Sabab (majburiy)' : 'Izoh'}
        hint={
          action === 'adjust'
            ? 'Yangi qoldiq — omborda haqiqatan nechta borligi'
            : undefined
        }
      >
        <input
          className="input"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </Field>

      <button
        className="btn btn-primary w-full"
        disabled={lines.length === 0 || mutation.isPending}
        onClick={submit}
      >
        {mutation.isPending ? 'Bajarilmoqda…' : 'Tasdiqlash'}
      </button>
    </Sheet>
  )
}
