import { useMemo, useState } from 'react'
import { useCan, useCurrentUser } from '../App'
import {
  useCategories,
  useProductFilters,
  useProducts,
  useSaveProduct,
} from '../api/hooks'
import { api } from '../api/client'
import type { Product } from '../api/types'
import { num, usd } from '../lib/format'
import { alertUser, haptic } from '../lib/telegram'
import {
  Card,
  Chip,
  Empty,
  ErrorBox,
  Field,
  Loading,
  Screen,
  Sheet,
  Tabs,
} from '../components/ui'

function stockTone(product: Product): { label: string; color: string } {
  if (product.qty <= 0) return { label: 'Tugagan', color: 'var(--danger)' }
  if (product.min_stock > 0 && product.qty <= product.min_stock)
    return { label: 'Kam qoldi', color: 'var(--warn)' }
  return { label: 'Yetarli', color: 'var(--ok)' }
}

export default function Catalog() {
  const me = useCurrentUser()
  const can = useCan()
  const canEdit = can('products.edit')

  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState<number | undefined>()
  const [implantType, setImplantType] = useState<string | undefined>()
  const [onlyInStock, setOnlyInStock] = useState(false)
  const [selected, setSelected] = useState<Product | null>(null)
  const [editing, setEditing] = useState<Partial<Product> | null>(null)

  const { data: categories } = useCategories()
  const { data: filters } = useProductFilters()
  const params = useMemo(
    () => ({
      search: search || undefined,
      category_id: categoryId,
      implant_type: implantType,
      in_stock: onlyInStock ? true : undefined,
    }),
    [search, categoryId, implantType, onlyInStock],
  )
  const { data: products, isLoading, error } = useProducts(params)
  const saveProduct = useSaveProduct()

  const categoryTabs = [
    { key: '', label: 'Hammasi' },
    ...(categories ?? []).map((c) => ({ key: String(c.id), label: c.name_uz })),
  ]

  async function handleImport(file: File) {
    try {
      const result = await api.upload<{ message?: string }>(
        '/catalog/products/import',
        file,
      )
      alertUser(result.message ?? 'Import bajarildi')
      window.location.reload()
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Import xatosi')
    }
  }

  async function submitEdit() {
    if (!editing) return
    const body: Record<string, unknown> = {
      name: editing.name,
      category_id: Number(editing.category_id),
      diameter_mm: editing.diameter_mm || null,
      length_mm: editing.length_mm || null,
      implant_type: editing.implant_type || null,
      connection_type: editing.connection_type || null,
      price_usd: editing.price_usd ?? '0',
      min_stock: Number(editing.min_stock ?? 0),
    }
    if (!editing.id) {
      body.sku = editing.sku
      if (!body.sku || !body.name) {
        alertUser('SKU va nomni to‘ldiring')
        return
      }
    }
    try {
      await saveProduct.mutateAsync({ id: editing.id, body })
      haptic('success')
      setEditing(null)
      setSelected(null)
    } catch (err) {
      alertUser(err instanceof Error ? err.message : 'Saqlashda xatolik')
    }
  }

  return (
    <Screen
      title="Katalog"
      subtitle={products ? `${products.length} ta mahsulot` : undefined}
      action={
        canEdit ? (
          <button
            className="btn btn-sm btn-primary"
            onClick={() =>
              setEditing({
                category_id: categories?.[0]?.id,
                price_usd: '0',
                min_stock: 0,
              })
            }
          >
            + Yangi
          </button>
        ) : null
      }
    >
      <input
        className="input mb-3"
        placeholder="Nomi yoki SKU bo‘yicha qidirish…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <Tabs
        tabs={categoryTabs}
        active={categoryId ? String(categoryId) : ''}
        onChange={(key) => setCategoryId(key ? Number(key) : undefined)}
      />

      {filters && filters.implant_types.length > 0 ? (
        <div className="scroll-x mb-3 flex gap-2">
          <button
            className="chip"
            style={
              onlyInStock
                ? { background: 'var(--ok)', color: '#fff', borderColor: 'transparent' }
                : undefined
            }
            onClick={() => setOnlyInStock((v) => !v)}
          >
            Faqat mavjud
          </button>
          {filters.implant_types.map((type) => (
            <button
              key={type}
              className="chip"
              style={
                implantType === type
                  ? {
                      background: 'var(--accent)',
                      color: 'var(--accent-text)',
                      borderColor: 'transparent',
                    }
                  : undefined
              }
              onClick={() => setImplantType(implantType === type ? undefined : type)}
            >
              {type}
            </button>
          ))}
        </div>
      ) : null}

      {canEdit ? (
        <div className="mb-3 flex gap-2">
          <button
            className="btn btn-sm flex-1"
            onClick={() => api.download('/catalog/products.xlsx')}
          >
            ⬇️ Excel’ga yuklash
          </button>
          <label className="btn btn-sm flex-1">
            ⬆️ Excel’dan yuklash
            <input
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleImport(file)
              }}
            />
          </label>
        </div>
      ) : null}

      {isLoading ? <Loading /> : null}
      {error ? <ErrorBox error={error} /> : null}
      {products && products.length === 0 ? <Empty text="Mahsulot topilmadi" /> : null}

      <div className="space-y-2">
        {(products ?? []).map((product) => {
          const tone = stockTone(product)
          return (
            <Card key={product.id} onClick={() => setSelected(product)}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-semibold">{product.name}</div>
                  <div className="mt-0.5 text-[12px] text-[var(--muted)]">
                    {product.sku}
                    {product.implant_type ? ` · ${product.implant_type}` : ''}
                  </div>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-[15px] font-bold">{usd(product.price_usd)}</div>
                  <div className="text-[12px]" style={{ color: tone.color }}>
                    {num(product.available)} dona
                  </div>
                </div>
              </div>
            </Card>
          )
        })}
      </div>

      {/* Mahsulot kartochkasi */}
      <Sheet
        open={Boolean(selected)}
        title={selected?.name ?? ''}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <div>
            <div className="mb-3 flex flex-wrap gap-2">
              <Chip>{selected.sku}</Chip>
              {selected.category_name ? <Chip>{selected.category_name}</Chip> : null}
              {selected.implant_type ? <Chip>{selected.implant_type}</Chip> : null}
              {selected.connection_type ? <Chip>{selected.connection_type}</Chip> : null}
            </div>
            <table className="tbl mb-3">
              <tbody>
                <tr>
                  <td className="text-[var(--muted)]">Narx</td>
                  <td className="text-right font-bold">{usd(selected.price_usd)}</td>
                </tr>
                <tr>
                  <td className="text-[var(--muted)]">Razmer</td>
                  <td className="text-right">
                    {selected.diameter_mm && selected.length_mm
                      ? `${Number(selected.diameter_mm)} × ${Number(selected.length_mm)} mm`
                      : '—'}
                  </td>
                </tr>
                <tr>
                  <td className="text-[var(--muted)]">Omborda</td>
                  <td className="text-right">{num(selected.qty)} dona</td>
                </tr>
                <tr>
                  <td className="text-[var(--muted)]">Band qilingan</td>
                  <td className="text-right">{num(selected.reserved)} dona</td>
                </tr>
                <tr>
                  <td className="text-[var(--muted)]">Bo‘sh</td>
                  <td className="text-right font-bold">{num(selected.available)} dona</td>
                </tr>
                <tr>
                  <td className="text-[var(--muted)]">Minimal qoldiq</td>
                  <td className="text-right">{num(selected.min_stock)} dona</td>
                </tr>
              </tbody>
            </table>
            {selected.description ? (
              <p className="mb-3 text-[13px] text-[var(--muted)]">{selected.description}</p>
            ) : null}
            {canEdit ? (
              <button
                className="btn btn-primary w-full"
                onClick={() => setEditing({ ...selected })}
              >
                Tahrirlash
              </button>
            ) : null}
          </div>
        ) : null}
      </Sheet>

      {/* Tahrirlash / yangi qo'shish */}
      <Sheet
        open={Boolean(editing)}
        title={editing?.id ? 'Mahsulotni tahrirlash' : 'Yangi mahsulot'}
        onClose={() => setEditing(null)}
      >
        {editing ? (
          <div>
            {!editing.id ? (
              <Field label="SKU (kod)">
                <input
                  className="input"
                  value={editing.sku ?? ''}
                  onChange={(e) => setEditing({ ...editing, sku: e.target.value })}
                />
              </Field>
            ) : null}
            <Field label="Nomi">
              <input
                className="input"
                value={editing.name ?? ''}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              />
            </Field>
            <Field label="Kategoriya">
              <select
                className="select"
                value={editing.category_id ?? ''}
                onChange={(e) =>
                  setEditing({ ...editing, category_id: Number(e.target.value) })
                }
              >
                {(categories ?? []).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name_uz}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Diametr (mm)">
                <input
                  className="input"
                  inputMode="decimal"
                  value={editing.diameter_mm ?? ''}
                  onChange={(e) =>
                    setEditing({ ...editing, diameter_mm: e.target.value })
                  }
                />
              </Field>
              <Field label="Uzunlik (mm)">
                <input
                  className="input"
                  inputMode="decimal"
                  value={editing.length_mm ?? ''}
                  onChange={(e) => setEditing({ ...editing, length_mm: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Turi">
              <input
                className="input"
                value={editing.implant_type ?? ''}
                onChange={(e) =>
                  setEditing({ ...editing, implant_type: e.target.value })
                }
              />
            </Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Narx (USD)">
                <input
                  className="input"
                  inputMode="decimal"
                  value={editing.price_usd ?? ''}
                  onChange={(e) => setEditing({ ...editing, price_usd: e.target.value })}
                />
              </Field>
              <Field label="Minimal qoldiq">
                <input
                  className="input"
                  inputMode="numeric"
                  value={editing.min_stock ?? 0}
                  onChange={(e) =>
                    setEditing({ ...editing, min_stock: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
            <button
              className="btn btn-primary w-full"
              disabled={saveProduct.isPending}
              onClick={submitEdit}
            >
              {saveProduct.isPending ? 'Saqlanmoqda…' : 'Saqlash'}
            </button>
          </div>
        ) : null}
      </Sheet>
    </Screen>
  )
}
