export type Role =
  | 'superadmin'
  | 'director'
  | 'founder'
  | 'accountant'
  | 'warehouse'
  | 'agent'
  | 'doctor'

export interface Me {
  id: number
  telegram_id: number | null
  full_name: string
  phone: string | null
  role: Role
  role_label: string
  is_active: boolean
  has_own_stock: boolean
  permissions: string[]
  doctor_id: number | null
}

export interface Product {
  id: number
  sku: string
  name: string
  category_id: number
  category_name?: string | null
  brand: string
  diameter_mm: string | null
  length_mm: string | null
  implant_type: string | null
  connection_type: string | null
  unit: string
  price_usd: string
  min_stock: number
  image_url: string | null
  description: string | null
  is_active: boolean
  qty: number
  reserved: number
  available: number
}

export interface Category {
  id: number
  code: string
  name_uz: string
  is_active: boolean
}

export interface Warehouse {
  id: number
  name: string
  kind: 'main' | 'agent'
  owner_user_id: number | null
  is_active: boolean
}

export interface StockRow {
  product_id: number
  sku: string
  name: string
  category?: string | null
  size?: string | null
  qty: number
  reserved: number
  available: number
  min_stock: number
  price_usd: string
  value_usd: string
  shortage?: number
  days_left?: number | null
  avg_daily?: number
  days_idle?: number | null
}

export interface Doctor {
  id: number
  full_name: string
  phone: string
  extra_phone: string | null
  clinic_name: string | null
  region: string | null
  district: string | null
  address: string | null
  lat: number | null
  lon: number | null
  birth_date: string | null
  specialty: string | null
  agent_id: number | null
  agent_name?: string | null
  telegram_id: number | null
  debt_limit_usd: string
  payment_term_days: number
  discount_pct: string
  category: 'A' | 'B' | 'C' | 'new'
  loyalty_score: number
  total_purchased_usd: string
  purchased_12m_usd: string
  orders_12m: number
  avg_payment_delay_days: number
  last_order_at: string | null
  notes: string | null
  is_active: boolean
  credit_block_override: boolean
  debt_usd: string
  overdue_usd: string
  oldest_due_date: string | null
  overdue_days: number
}

export type OrderStatus =
  | 'new'
  | 'director_review'
  | 'approved'
  | 'picking'
  | 'shipped'
  | 'delivered'
  | 'cancelled'
  | 'rejected'

export interface OrderItem {
  id: number
  product_id: number
  product_name?: string | null
  sku?: string | null
  size?: string | null
  qty: number
  price_usd: string
  discount_pct: string
  line_total_usd: string
}

export interface Order {
  id: number
  number: string
  doctor_id: number
  doctor_name?: string | null
  doctor_phone?: string | null
  agent_id: number | null
  agent_name?: string | null
  warehouse_id: number
  warehouse_name?: string | null
  source: 'doctor' | 'agent'
  status: OrderStatus
  status_label?: string | null
  subtotal_usd: string
  discount_pct: string
  discount_usd: string
  total_usd: string
  total_uzs: string | null
  fx_rate: string
  paid_usd: string
  returned_usd: string
  debt_usd: string
  due_date: string | null
  needs_director: boolean
  director_reason: string | null
  comment: string | null
  cancel_reason: string | null
  created_at: string
  approved_at: string | null
  delivered_at: string | null
  items: OrderItem[]
}

export interface Payment {
  id: number
  doctor_id: number
  doctor_name?: string | null
  order_id: number | null
  order_number?: string | null
  amount_uzs: string
  amount_usd: string
  fx_rate: string
  method: 'cash' | 'card' | 'transfer'
  paid_at: string
  received_by_id: number | null
  received_by_name?: string | null
  agent_id: number | null
  note: string | null
}

export interface DebtRow {
  doctor_id: number
  full_name: string
  clinic_name: string | null
  phone: string
  category: string | null
  loyalty_score: number
  debt_usd: string
  overdue_usd: string
  debt_limit_usd: string
  payment_term_days: number
  oldest_due_date: string | null
  overdue_days: number
  open_orders: number
  agent_id: number | null
}

export interface Metric {
  fact: number
  target: number
  pct: number
}

export interface PlanProgress {
  user_id: number
  full_name: string
  year: number
  month: number
  amount: Metric
  units: Metric
  collection: Metric
  overall_pct: number
  days_passed: number
  days_in_month: number
  has_plan: boolean
  expected_pace_pct?: number
  rank?: number
  target_amount_usd?: string
  target_units?: number
  target_collection_usd?: string
}

export interface Dashboard {
  date: string
  today: SalesSummary
  month: SalesSummary
  my_month?: SalesSummary
  debt: { total_usd: string; overdue_usd: string; doctors_in_debt: number }
  low_stock_count: number
  out_of_stock_count: number
  new_doctors_today: number
  pending_orders: Record<string, number>
  stock_value_usd: string
}

export interface SalesSummary {
  amount_usd: string
  units: number
  orders: number
  doctors: number
  collected_usd: string
}

export interface TopProduct {
  product_id: number
  sku: string
  name: string
  size: string
  implant_type: string | null
  qty: number
  amount_usd: string
}

export interface SizeDemand {
  diameter_mm: number
  length_mm: number
  size: string
  qty: number
  amount_usd: string
}

export interface UserRow {
  id: number
  telegram_id: number | null
  telegram_username: string | null
  full_name: string
  phone: string | null
  role: Role
  is_active: boolean
  has_own_stock: boolean
  created_at: string
  last_seen_at: string | null
}

export interface Task {
  id: number
  created_at: string
  user_id: number
  doctor_id: number | null
  doctor_name?: string | null
  doctor_phone?: string | null
  kind: 'birthday' | 'sleeping' | 'overdue' | 'manual'
  kind_label?: string | null
  due_date: string
  title: string
  status: 'open' | 'done' | 'skipped'
  note: string | null
}

export interface Visit {
  id: number
  created_at: string
  agent_id: number
  agent_name?: string | null
  doctor_id: number
  doctor_name?: string | null
  lat: number | null
  lon: number | null
  distance_m: number | null
  result: 'order' | 'no_order' | 'not_there' | 'payment' | null
  note: string | null
}

export interface SettingRow {
  key: string
  value: unknown
  label_uz: string
}

export interface AuditRow {
  id: number
  created_at: string
  user_id: number | null
  user_name: string | null
  action: string
  entity: string
  entity_id: string | null
  old_value: Record<string, unknown> | null
  new_value: Record<string, unknown> | null
  comment: string | null
}

export interface OkResponse {
  ok: boolean
  message?: string | null
}
