/** Telegram Mini App SDK ustidan yupqa qatlam. */

type TgWebApp = {
  initData: string
  initDataUnsafe?: { user?: { id: number; first_name?: string } }
  colorScheme?: 'light' | 'dark'
  themeParams?: Record<string, string>
  ready: () => void
  expand: () => void
  close: () => void
  MainButton: {
    setText: (t: string) => void
    show: () => void
    hide: () => void
    enable: () => void
    disable: () => void
    showProgress: (leaveActive?: boolean) => void
    hideProgress: () => void
    onClick: (cb: () => void) => void
    offClick: (cb: () => void) => void
  }
  BackButton: {
    show: () => void
    hide: () => void
    onClick: (cb: () => void) => void
    offClick: (cb: () => void) => void
  }
  HapticFeedback?: {
    impactOccurred: (s: string) => void
    notificationOccurred: (t: string) => void
  }
  showAlert?: (msg: string, cb?: () => void) => void
  showConfirm?: (msg: string, cb?: (ok: boolean) => void) => void
  requestLocation?: unknown
  disableVerticalSwipes?: () => void
  setHeaderColor?: (c: string) => void
}

export const tg: TgWebApp | undefined = (window as any).Telegram?.WebApp

export function initTelegram() {
  if (!tg) {
    // Brauzerda ochilgan (ishlab chiqish rejimi)
    document.documentElement.dataset.dark =
      window.matchMedia('(prefers-color-scheme: dark)').matches ? '1' : '0'
    return
  }
  tg.ready()
  tg.expand()
  tg.disableVerticalSwipes?.()
  document.documentElement.dataset.dark = tg.colorScheme === 'dark' ? '1' : '0'
}

/** Har so'rovga qo'shiladigan imzo. */
export function initData(): string {
  return tg?.initData ?? ''
}

/** Ishlab chiqishda BOT_TOKEN bo'lmaganda ishlatiladi. */
export function debugTelegramId(): string | null {
  const fromQuery = new URLSearchParams(window.location.search).get('debug_tg')
  if (fromQuery) {
    localStorage.setItem('debug_tg', fromQuery)
    return fromQuery
  }
  return localStorage.getItem('debug_tg')
}

export function haptic(kind: 'light' | 'medium' | 'success' | 'error' = 'light') {
  if (!tg?.HapticFeedback) return
  if (kind === 'success' || kind === 'error') {
    tg.HapticFeedback.notificationOccurred(kind)
  } else {
    tg.HapticFeedback.impactOccurred(kind)
  }
}

export function alertUser(message: string) {
  if (tg?.showAlert) tg.showAlert(message)
  else window.alert(message)
}

export function confirmUser(message: string): Promise<boolean> {
  return new Promise((resolve) => {
    if (tg?.showConfirm) tg.showConfirm(message, (ok) => resolve(Boolean(ok)))
    else resolve(window.confirm(message))
  })
}

/** Joriy joylashuvni oladi (tashrif qayd etish uchun). */
export function getPosition(): Promise<{ lat: number; lon: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null)
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 8000 },
    )
  })
}
