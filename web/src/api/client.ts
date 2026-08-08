import { debugTelegramId, initData } from '../lib/telegram'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {}
  if (json) h['Content-Type'] = 'application/json'
  const data = initData()
  if (data) h['X-Telegram-Init-Data'] = data
  const debug = debugTelegramId()
  if (!data && debug) h['X-Debug-Telegram-Id'] = debug
  return h
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Xatolik (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail) && body.detail[0]?.msg)
        message = body.detail.map((d: any) => d.msg).join('; ')
    } catch {
      /* JSON emas */
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function withQuery(path: string, params?: Record<string, unknown>): string {
  if (!params) return `${BASE}${path}`
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    search.append(key, String(value))
  })
  const qs = search.toString()
  return `${BASE}${path}${qs ? `?${qs}` : ''}`
}

export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) =>
    fetch(withQuery(path, params), { headers: headers(false) }).then(handle<T>),

  post: <T>(path: string, body?: unknown) =>
    fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: headers(),
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then(handle<T>),

  patch: <T>(path: string, body: unknown) =>
    fetch(`${BASE}${path}`, {
      method: 'PATCH',
      headers: headers(),
      body: JSON.stringify(body),
    }).then(handle<T>),

  put: <T>(path: string, body: unknown) =>
    fetch(`${BASE}${path}`, {
      method: 'PUT',
      headers: headers(),
      body: JSON.stringify(body),
    }).then(handle<T>),

  del: <T>(path: string) =>
    fetch(`${BASE}${path}`, { method: 'DELETE', headers: headers(false) }).then(
      handle<T>,
    ),

  upload: <T>(path: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: headers(false),
      body: form,
    }).then(handle<T>)
  },

  /** Fayl yuklab olish (Excel/PDF) — sarlavhalar bilan. */
  download: async (path: string, params?: Record<string, unknown>) => {
    const response = await fetch(withQuery(path, params), {
      headers: headers(false),
    })
    if (!response.ok) throw new ApiError(response.status, 'Yuklab olishda xatolik')
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const match = /filename="?([^"]+)"?/.exec(disposition)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = match?.[1] ?? 'dxl-hisobot'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },
}
