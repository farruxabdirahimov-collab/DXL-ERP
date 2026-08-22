import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  AudienceOption,
  AuditRow,
  Broadcast,
  Category,
  Dashboard,
  DebtRow,
  Doctor,
  DoctorRequest,
  Me,
  MyPurchases,
  OkResponse,
  Order,
  Payment,
  Post,
  PlanProgress,
  Product,
  SettingRow,
  SizeReport,
  StockRow,
  Task,
  TopProduct,
  UserRow,
  Visit,
  Warehouse,
} from './types'

/* ------------------------------------------------------------------ auth */
export const useMe = () =>
  useQuery({
    queryKey: ['me'],
    queryFn: () => api.get<Me>('/me'),
    retry: false,
    staleTime: 5 * 60 * 1000,
  })

/* --------------------------------------------------------------- katalog */
export const useCategories = () =>
  useQuery({
    queryKey: ['categories'],
    queryFn: () => api.get<Category[]>('/catalog/categories'),
    staleTime: 10 * 60 * 1000,
  })

export const useProducts = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['products', params],
    queryFn: () => api.get<Product[]>('/catalog/products', params),
  })

export const useProduct = (id?: number) =>
  useQuery({
    queryKey: ['product', id],
    queryFn: () => api.get<Product>(`/catalog/products/${id}`),
    enabled: Boolean(id),
  })

export const useProductFilters = () =>
  useQuery({
    queryKey: ['product-filters'],
    queryFn: () =>
      api.get<{ implant_types: string[]; diameters: number[]; lengths: number[] }>(
        '/catalog/products/filters',
      ),
    staleTime: 10 * 60 * 1000,
  })

export const useSaveProduct = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id
        ? api.patch<Product>(`/catalog/products/${id}`, body)
        : api.post<Product>('/catalog/products', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['products'] })
      qc.invalidateQueries({ queryKey: ['stock'] })
    },
  })
}

/* ----------------------------------------------------------------- ombor */
export const useWarehouses = () =>
  useQuery({
    queryKey: ['warehouses'],
    queryFn: () => api.get<Warehouse[]>('/stock/warehouses'),
    staleTime: 10 * 60 * 1000,
  })

export const useStock = (warehouseId?: number) =>
  useQuery({
    queryKey: ['stock', warehouseId ?? 'all'],
    queryFn: () =>
      api.get<StockRow[]>('/stock/balances', { warehouse_id: warehouseId }),
  })

export const useStockByWarehouse = () =>
  useQuery({
    queryKey: ['stock-by-warehouse'],
    queryFn: () =>
      api.get<
        { warehouse_id: number; name: string; kind: string; qty: number; skus: number; value_usd: string }[]
      >('/stock/by-warehouse'),
  })

export const useLowStock = () =>
  useQuery({ queryKey: ['low-stock'], queryFn: () => api.get<StockRow[]>('/stock/low') })

export const useStockMoves = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['stock-moves', params],
    queryFn: () => api.get<any[]>('/stock/moves', params),
  })

export const useStockAction = (path: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<OkResponse>(path, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock'] })
      qc.invalidateQueries({ queryKey: ['products'] })
      qc.invalidateQueries({ queryKey: ['low-stock'] })
      qc.invalidateQueries({ queryKey: ['stock-by-warehouse'] })
      qc.invalidateQueries({ queryKey: ['stock-moves'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

/* --------------------------------------------------------------- vrachlar */
export const useDoctors = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['doctors', params],
    queryFn: () => api.get<Doctor[]>('/doctors', params),
  })

export const useDoctor = (id?: number) =>
  useQuery({
    queryKey: ['doctor', id],
    queryFn: () => api.get<Doctor>(`/doctors/${id}`),
    enabled: Boolean(id),
  })

export const useDoctorDebt = (id?: number) =>
  useQuery({
    queryKey: ['doctor-debt', id],
    queryFn: () => api.get<any>(`/doctors/${id}/debt`),
    enabled: Boolean(id),
  })

export const useDoctorHistory = (id?: number) =>
  useQuery({
    queryKey: ['doctor-history', id],
    queryFn: () => api.get<any>(`/doctors/${id}/history`),
    enabled: Boolean(id),
  })

export const useBirthdays = (days = 7) =>
  useQuery({
    queryKey: ['birthdays', days],
    queryFn: () => api.get<Doctor[]>('/doctors/birthdays', { days }),
  })

export const useSleepingDoctors = () =>
  useQuery({
    queryKey: ['sleeping-doctors'],
    queryFn: () => api.get<Doctor[]>('/doctors/sleeping'),
  })

export const useDoctorRequests = () =>
  useQuery({
    queryKey: ['doctor-requests'],
    queryFn: () => api.get<DoctorRequest[]>('/doctors/requests'),
    refetchInterval: 60_000,
  })

export const useReviewRequest = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      action,
      body,
    }: {
      id: number
      action: 'approve' | 'reject'
      body?: unknown
    }) => api.post(`/doctors/requests/${id}/${action}`, body ?? {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['doctor-requests'] })
      qc.invalidateQueries({ queryKey: ['doctors'] })
    },
  })
}

export const useSaveDoctor = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id
        ? api.patch<Doctor>(`/doctors/${id}`, body)
        : api.post<Doctor>('/doctors', body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['doctors'] })
      if (vars.id) qc.invalidateQueries({ queryKey: ['doctor', vars.id] })
    },
  })
}

/* ------------------------------------------------------------- buyurtmalar */
export const useOrders = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['orders', params],
    queryFn: () => api.get<Order[]>('/orders', params),
  })

export const useOrder = (id?: number) =>
  useQuery({
    queryKey: ['order', id],
    queryFn: () => api.get<Order>(`/orders/${id}`),
    enabled: Boolean(id),
  })

export const useCreateOrder = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<Order>('/orders', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export const useOrderAction = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      action,
      body,
    }: {
      id: number
      action: string
      body?: unknown
    }) => api.post<Order>(`/orders/${id}/${action}`, body ?? {}),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['orders'] })
      qc.invalidateQueries({ queryKey: ['order', vars.id] })
      qc.invalidateQueries({ queryKey: ['stock'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['debts'] })
    },
  })
}

/* ------------------------------------------------------------------ pul */
export const useFxRate = () =>
  useQuery({
    queryKey: ['fx'],
    queryFn: () => api.get<{ date: string; usd_uzs: string }>('/finance/fx'),
    staleTime: 5 * 60 * 1000,
  })

export const useSetFxRate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { usd_uzs: number; rate_date?: string }) =>
      api.post<OkResponse>('/finance/fx', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fx'] }),
  })
}

export const usePayments = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['payments', params],
    queryFn: () => api.get<Payment[]>('/finance/payments', params),
  })

export const useCreatePayment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<OkResponse>('/finance/payments', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['payments'] })
      qc.invalidateQueries({ queryKey: ['debts'] })
      qc.invalidateQueries({ queryKey: ['doctors'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      qc.invalidateQueries({ queryKey: ['plan'] })
    },
  })
}

export const useDebts = (onlyOverdue = false) =>
  useQuery({
    queryKey: ['debts', onlyOverdue],
    queryFn: () => api.get<DebtRow[]>('/finance/debts', { only_overdue: onlyOverdue }),
  })

export const useDebtAging = () =>
  useQuery({
    queryKey: ['debt-aging'],
    queryFn: () => api.get<Record<string, string>>('/finance/debts/aging'),
  })

export const useMyDebt = () =>
  useQuery({ queryKey: ['my-debt'], queryFn: () => api.get<any>('/finance/my-debt') })

export const useReturns = () =>
  useQuery({
    queryKey: ['returns'],
    queryFn: () => api.get<any[]>('/finance/returns'),
  })

export const useCreateReturn = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<OkResponse>('/finance/returns', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['debts'] })
      qc.invalidateQueries({ queryKey: ['stock'] })
      qc.invalidateQueries({ queryKey: ['orders'] })
      qc.invalidateQueries({ queryKey: ['returns'] })
      qc.invalidateQueries({ queryKey: ['reports'] })
    },
  })
}

/* ------------------------------------------------------------- hisobotlar */
export const useDashboard = () =>
  useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<Dashboard>('/reports/dashboard'),
    refetchInterval: 60_000,
  })

export const useTrend = (days = 30) =>
  useQuery({
    queryKey: ['trend', days],
    queryFn: () => api.get<{ date: string; amount_usd: string }[]>('/reports/trend', { days }),
  })

export const useTopProducts = (params: Record<string, unknown>, ascending = false) =>
  useQuery({
    queryKey: ['top-products', params, ascending],
    queryFn: () =>
      api.get<TopProduct[]>(
        ascending ? '/reports/products/least' : '/reports/products/top',
        params,
      ),
  })

export const useSizeDemand = (params: Record<string, unknown>) =>
  useQuery({
    queryKey: ['size-demand', params],
    queryFn: () => api.get<SizeReport>('/reports/products/sizes', params),
  })

export const useSalesByType = (params: Record<string, unknown>) =>
  useQuery({
    queryKey: ['sales-by-type', params],
    queryFn: () =>
      api.get<{ implant_type: string; qty: number; amount_usd: string }[]>(
        '/reports/products/types',
        params,
      ),
  })

export const useDeadStock = () =>
  useQuery({
    queryKey: ['dead-stock'],
    queryFn: () => api.get<StockRow[]>('/reports/products/dead'),
  })

export const useOutOfStock = () =>
  useQuery({
    queryKey: ['out-of-stock'],
    queryFn: () => api.get<StockRow[]>('/reports/products/out'),
  })

export const useSalesReport = (params: Record<string, unknown>) =>
  useQuery({
    queryKey: ['sales-report', params],
    queryFn: () => api.get<any>('/reports/sales', params),
  })

export const useAgentsReport = (params: Record<string, unknown>) =>
  useQuery({
    queryKey: ['agents-report', params],
    queryFn: () => api.get<any[]>('/reports/agents', params),
  })

export const useDoctorsReport = () =>
  useQuery({
    queryKey: ['doctors-report'],
    queryFn: () => api.get<any[]>('/reports/doctors'),
  })

export const useDailyPreview = () =>
  useQuery({
    queryKey: ['daily-preview'],
    queryFn: () => api.get<{ date: string; text: string }>('/reports/daily-preview'),
  })

/* ------------------------------------------------------------------ reja */
export const useMyPlan = () =>
  useQuery({ queryKey: ['plan', 'my'], queryFn: () => api.get<PlanProgress>('/plans/my') })

export const useLeaderboard = () =>
  useQuery({
    queryKey: ['plan', 'leaderboard'],
    queryFn: () => api.get<PlanProgress[]>('/plans/leaderboard'),
  })

export const useAllPlans = () =>
  useQuery({ queryKey: ['plan', 'all'], queryFn: () => api.get<PlanProgress[]>('/plans') })

export const useSetPlan = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<OkResponse>('/plans', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plan'] }),
  })
}

/* -------------------------------------------------------------- tashriflar */
export const useVisits = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['visits', params],
    queryFn: () => api.get<Visit[]>('/visits', params),
  })

export const useVisitSummary = () =>
  useQuery({
    queryKey: ['visit-summary'],
    queryFn: () => api.get<any>('/visits/today-summary'),
  })

export const useCheckIn = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<Visit>('/visits', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['visits'] }),
  })
}

/* ---------------------------------------------------------------- vazifalar */
export const useTasks = () =>
  useQuery({ queryKey: ['tasks'], queryFn: () => api.get<Task[]>('/tasks') })

export const useUpdateTask = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: unknown }) =>
      api.patch<Task>(`/tasks/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })
}

/* ------------------------------------------------------------------ admin */
export const useUsers = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['users', params],
    queryFn: () => api.get<UserRow[]>('/admin/users', params),
  })

export const useAgents = () =>
  useQuery({
    queryKey: ['agents'],
    queryFn: () => api.get<UserRow[]>('/admin/agents'),
    staleTime: 10 * 60 * 1000,
  })

export const useSaveUser = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id
        ? api.patch<UserRow>(`/admin/users/${id}`, body)
        : api.post<UserRow>('/admin/users', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      qc.invalidateQueries({ queryKey: ['agents'] })
    },
  })
}

export const useInvites = () =>
  useQuery({ queryKey: ['invites'], queryFn: () => api.get<any[]>('/admin/invites') })

export const useCreateInvite = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<any>('/admin/invites', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invites'] }),
  })
}

export const useSettings = () =>
  useQuery({ queryKey: ['settings'], queryFn: () => api.get<SettingRow[]>('/admin/settings') })

export const useSaveSetting = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { key: string; value: unknown }) =>
      api.put<OkResponse>('/admin/settings', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })
}

export const useAudit = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['audit', params],
    queryFn: () => api.get<AuditRow[]>('/admin/audit', params),
  })


/* ---------------------------------------------------------------- kontent */
export const usePosts = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['posts', params],
    queryFn: () => api.get<Post[]>('/content/posts', params),
  })

export const usePost = (id?: number) =>
  useQuery({
    queryKey: ['post', id],
    queryFn: () => api.get<Post>(`/content/posts/${id}`),
    enabled: Boolean(id),
  })

export const useSavePost = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id
        ? api.patch<Post>(`/content/posts/${id}`, body)
        : api.post<Post>('/content/posts', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['posts'] }),
  })
}

export const useDeletePost = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.del<OkResponse>(`/content/posts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['posts'] }),
  })
}

export const useAudiences = () =>
  useQuery({
    queryKey: ['audiences'],
    queryFn: () => api.get<AudienceOption[]>('/content/audiences'),
  })

export const useBroadcasts = () =>
  useQuery({
    queryKey: ['broadcasts'],
    queryFn: () => api.get<Broadcast[]>('/content/broadcasts'),
  })

export const useSendBroadcast = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<Broadcast>('/content/broadcasts', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['broadcasts'] }),
  })
}

export const useMyPurchases = () =>
  useQuery({
    queryKey: ['my-purchases'],
    queryFn: () => api.get<MyPurchases>('/content/my-purchases'),
  })

/* --------------------------------------------------- taklif-shartnoma */
export const useTariffs = (onlyActive = true) =>
  useQuery({
    queryKey: ['tariffs', onlyActive],
    queryFn: () => api.get<any[]>('/contracts/tariffs', { only_active: onlyActive }),
  })

export const useTariffLadder = () =>
  useQuery({
    queryKey: ['tariff-ladder'],
    queryFn: () => api.get<any>('/contracts/tariffs/ladder'),
  })

export const useSaveTariff = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: Record<string, unknown> }) =>
      id
        ? api.patch<any>(`/contracts/tariffs/${id}`, body)
        : api.post<any>('/contracts/tariffs', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tariffs'] })
      qc.invalidateQueries({ queryKey: ['tariff-ladder'] })
    },
  })
}

export const useContracts = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['contracts', params],
    queryFn: () => api.get<any[]>('/contracts', params),
  })

export const useAtRisk = (days = 3) =>
  useQuery({
    queryKey: ['contracts-at-risk', days],
    queryFn: () => api.get<any>('/contracts/at-risk', { days }),
  })

export const usePendingGifts = () =>
  useQuery({
    queryKey: ['contracts-pending-gifts'],
    queryFn: () => api.get<any[]>('/contracts/gifts/pending'),
  })

export const useCreateContract = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: unknown) => api.post<any>('/contracts', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['contracts'] })
      qc.invalidateQueries({ queryKey: ['contracts-at-risk'] })
      qc.invalidateQueries({ queryKey: ['doctor'] })
    },
  })
}

export const useContractAction = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'gift' | 'cancel' }) =>
      api.post<OkResponse>(`/contracts/${id}/${action}`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['contracts'] })
      qc.invalidateQueries({ queryKey: ['contracts-at-risk'] })
      qc.invalidateQueries({ queryKey: ['contracts-pending-gifts'] })
      qc.invalidateQueries({ queryKey: ['stock'] })
    },
  })
}

/* ------------------------------------------------- oylik reja (Modul 2) */
export const useCompanyPlan = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['plan', 'company', params],
    queryFn: () => api.get<any>('/plans/company', params),
  })

export const usePlanHistory = (userId?: number, months = 6) =>
  useQuery({
    queryKey: ['plan', 'history', userId ?? 'me', months],
    queryFn: () => api.get<any[]>('/plans/history', { user_id: userId, months }),
  })

/** Kompaniya rejasi, ommaviy qo'yish, o'tgan oydan nusxa — bittada. */
export const usePlanAction = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) =>
      api.post<OkResponse>(path, body ?? {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plan'] }),
  })
}

/* ------------------------------------------------ foyda-zarar (Modul 3) */
export const useProfit = (params: Record<string, unknown> = {}) =>
  useQuery({
    queryKey: ['profit', params],
    queryFn: () => api.get<any>('/profit', params),
  })

export const useCostStatus = () =>
  useQuery({
    queryKey: ['profit', 'cost-status'],
    queryFn: () => api.get<any>('/profit/cost-status'),
  })

export const useExpenses = () =>
  useQuery({
    queryKey: ['profit', 'expenses'],
    queryFn: () => api.get<any[]>('/profit/expenses'),
  })

export const useExpenseCategories = () =>
  useQuery({
    queryKey: ['profit', 'expense-categories'],
    queryFn: () => api.get<any[]>('/profit/expenses/categories'),
    staleTime: 10 * 60 * 1000,
  })

/** Tannarx, xarajat qo'shish/o'chirish — hammasi foyda hisobotini yangilaydi. */
export const useProfitAction = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      path,
      body,
      method = 'post',
    }: {
      path: string
      body?: unknown
      method?: 'post' | 'del'
    }) =>
      method === 'del'
        ? api.del<OkResponse>(path)
        : api.post<OkResponse>(path, body ?? {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profit'] })
      qc.invalidateQueries({ queryKey: ['products'] })
    },
  })
}
