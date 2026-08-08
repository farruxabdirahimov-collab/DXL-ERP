"""API uchun pydantic sxemalari."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    DoctorCategory,
    OrderSource,
    OrderStatus,
    PaymentMethod,
    Role,
    TaskKind,
    TaskStatus,
    VisitResult,
    WarehouseKind,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------- auth
class MeOut(ORMModel):
    id: int
    telegram_id: int | None
    full_name: str
    phone: str | None
    role: Role
    role_label: str
    is_active: bool
    has_own_stock: bool
    permissions: list[str] = []
    doctor_id: int | None = None


class UserOut(ORMModel):
    id: int
    telegram_id: int | None
    telegram_username: str | None
    full_name: str
    phone: str | None
    role: Role
    is_active: bool
    has_own_stock: bool
    created_at: datetime
    last_seen_at: datetime | None


class UserCreateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    role: Role
    phone: str | None = None
    telegram_id: int | None = None
    has_own_stock: bool = False


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    phone: str | None = None
    is_active: bool | None = None
    has_own_stock: bool | None = None
    note: str | None = None


class InviteOut(ORMModel):
    id: int
    token: str
    role: Role
    full_name: str
    phone: str | None
    expires_at: datetime
    used_at: datetime | None
    link: str | None = None


class InviteCreateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    role: Role
    phone: str | None = None
    has_own_stock: bool = False
    valid_days: int = Field(default=7, ge=1, le=90)


# ------------------------------------------------------------------ catalog
class CategoryOut(ORMModel):
    id: int
    code: str
    name_uz: str
    is_active: bool


class ProductOut(ORMModel):
    id: int
    sku: str
    name: str
    category_id: int
    category_name: str | None = None
    brand: str
    diameter_mm: Decimal | None
    length_mm: Decimal | None
    implant_type: str | None
    connection_type: str | None
    unit: str
    price_usd: Decimal
    min_stock: int
    image_url: str | None
    description: str | None
    is_active: bool
    qty: int = 0
    reserved: int = 0
    available: int = 0


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=2, max_length=200)
    category_id: int
    brand: str = "DXL"
    diameter_mm: Decimal | None = None
    length_mm: Decimal | None = None
    implant_type: str | None = None
    connection_type: str | None = None
    unit: str = "dona"
    price_usd: Decimal = Field(default=Decimal("0"), ge=0)
    min_stock: int = Field(default=0, ge=0)
    image_url: str | None = None
    description: str | None = None
    is_active: bool = True


class ProductUpdateIn(BaseModel):
    name: str | None = None
    category_id: int | None = None
    diameter_mm: Decimal | None = None
    length_mm: Decimal | None = None
    implant_type: str | None = None
    connection_type: str | None = None
    price_usd: Decimal | None = Field(default=None, ge=0)
    min_stock: int | None = Field(default=None, ge=0)
    image_url: str | None = None
    description: str | None = None
    is_active: bool | None = None


class WarehouseOut(ORMModel):
    id: int
    name: str
    kind: WarehouseKind
    owner_user_id: int | None
    is_active: bool


class StockRowOut(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str | None = None
    size: str | None = None
    qty: int
    reserved: int = 0
    available: int = 0
    min_stock: int = 0
    price_usd: Decimal = Decimal("0")
    value_usd: Decimal = Decimal("0")


class ReceiptLineIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)


class ReceiptIn(BaseModel):
    warehouse_id: int | None = None
    supplier: str | None = None
    invoice_no: str | None = None
    note: str | None = None
    lines: list[ReceiptLineIn] = Field(min_length=1)


class TransferLineIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)


class TransferIn(BaseModel):
    from_warehouse_id: int
    to_warehouse_id: int
    note: str | None = None
    lines: list[TransferLineIn] = Field(min_length=1)


class AdjustIn(BaseModel):
    warehouse_id: int
    product_id: int
    new_qty: int = Field(ge=0)
    note: str | None = None


class WriteOffIn(BaseModel):
    warehouse_id: int
    reason: str = Field(min_length=3)
    lines: list[TransferLineIn] = Field(min_length=1)


# ---------------------------------------------------------------------- crm
class DoctorOut(ORMModel):
    id: int
    full_name: str
    phone: str
    extra_phone: str | None
    clinic_name: str | None
    region: str | None
    district: str | None
    address: str | None
    lat: float | None
    lon: float | None
    birth_date: date | None
    specialty: str | None
    agent_id: int | None
    agent_name: str | None = None
    telegram_id: int | None
    debt_limit_usd: Decimal
    payment_term_days: int
    discount_pct: Decimal
    category: DoctorCategory
    loyalty_score: int
    total_purchased_usd: Decimal
    purchased_12m_usd: Decimal
    orders_12m: int
    avg_payment_delay_days: float
    last_order_at: datetime | None
    notes: str | None
    is_active: bool
    credit_block_override: bool
    # hisoblanadigan
    debt_usd: Decimal = Decimal("0")
    overdue_usd: Decimal = Decimal("0")
    oldest_due_date: date | None = None
    overdue_days: int = 0


class DoctorIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=5, max_length=20)
    extra_phone: str | None = None
    clinic_name: str | None = None
    region: str | None = None
    district: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    birth_date: date | None = None
    specialty: str | None = None
    agent_id: int | None = None
    debt_limit_usd: Decimal | None = Field(default=None, ge=0)
    payment_term_days: int | None = Field(default=None, ge=0, le=365)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    notes: str | None = None

    @field_validator("phone", "extra_phone")
    @classmethod
    def _clean_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        return cleaned or None


class DoctorUpdateIn(DoctorIn):
    full_name: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    credit_block_override: bool | None = None


# ------------------------------------------------------------------- orders
class OrderLineIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class OrderIn(BaseModel):
    doctor_id: int | None = None
    warehouse_id: int | None = None
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    comment: str | None = None
    lines: list[OrderLineIn] = Field(min_length=1)


class OrderItemOut(ORMModel):
    id: int
    product_id: int
    product_name: str | None = None
    sku: str | None = None
    size: str | None = None
    qty: int
    price_usd: Decimal
    discount_pct: Decimal
    line_total_usd: Decimal


class OrderOut(ORMModel):
    id: int
    number: str
    doctor_id: int
    doctor_name: str | None = None
    doctor_phone: str | None = None
    agent_id: int | None
    agent_name: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    source: OrderSource
    status: OrderStatus
    status_label: str | None = None
    subtotal_usd: Decimal
    discount_pct: Decimal
    discount_usd: Decimal
    total_usd: Decimal
    total_uzs: Decimal | None = None
    fx_rate: Decimal
    paid_usd: Decimal
    returned_usd: Decimal
    debt_usd: Decimal = Decimal("0")
    due_date: date | None
    needs_director: bool
    director_reason: str | None
    comment: str | None
    cancel_reason: str | None
    created_at: datetime
    approved_at: datetime | None
    delivered_at: datetime | None
    items: list[OrderItemOut] = []


class CancelIn(BaseModel):
    reason: str | None = None


# ----------------------------------------------------------------- payments
class PaymentIn(BaseModel):
    doctor_id: int
    amount_uzs: Decimal = Field(gt=0)
    method: PaymentMethod = PaymentMethod.CASH
    order_id: int | None = None
    fx_rate: Decimal | None = Field(default=None, gt=0)
    paid_at: datetime | None = None
    note: str | None = None


class PaymentOut(ORMModel):
    id: int
    doctor_id: int
    doctor_name: str | None = None
    order_id: int | None
    order_number: str | None = None
    amount_uzs: Decimal
    amount_usd: Decimal
    fx_rate: Decimal
    method: PaymentMethod
    paid_at: datetime
    received_by_id: int | None
    received_by_name: str | None = None
    agent_id: int | None
    note: str | None


class FxRateIn(BaseModel):
    usd_uzs: Decimal = Field(gt=0)
    rate_date: date | None = None


class ReturnIn(BaseModel):
    doctor_id: int
    order_id: int | None = None
    warehouse_id: int | None = None
    reason: str | None = None
    lines: list[TransferLineIn] = Field(min_length=1)


# -------------------------------------------------------------------- plans
class PlanIn(BaseModel):
    user_id: int
    year: int = Field(ge=2020, le=2100)
    month: int = Field(ge=1, le=12)
    target_amount_usd: Decimal = Field(default=Decimal("0"), ge=0)
    target_units: int = Field(default=0, ge=0)
    target_collection_usd: Decimal = Field(default=Decimal("0"), ge=0)


# ------------------------------------------------------------------- visits
class VisitIn(BaseModel):
    doctor_id: int
    lat: float | None = None
    lon: float | None = None
    result: VisitResult | None = None
    note: str | None = None
    order_id: int | None = None


class VisitOut(ORMModel):
    id: int
    created_at: datetime
    agent_id: int
    agent_name: str | None = None
    doctor_id: int
    doctor_name: str | None = None
    lat: float | None
    lon: float | None
    distance_m: float | None
    result: VisitResult | None
    note: str | None


# -------------------------------------------------------------------- tasks
class TaskOut(ORMModel):
    id: int
    created_at: datetime
    user_id: int
    doctor_id: int | None
    doctor_name: str | None = None
    doctor_phone: str | None = None
    kind: TaskKind
    kind_label: str | None = None
    due_date: date
    title: str
    status: TaskStatus
    note: str | None


class TaskUpdateIn(BaseModel):
    status: TaskStatus
    note: str | None = None


class TaskCreateIn(BaseModel):
    doctor_id: int | None = None
    user_id: int | None = None
    due_date: date
    title: str = Field(min_length=2, max_length=200)
    note: str | None = None


# ----------------------------------------------------------------- settings
class SettingIn(BaseModel):
    key: str
    value: object


class AuditOut(ORMModel):
    id: int
    created_at: datetime
    user_id: int | None
    user_name: str | None
    action: str
    entity: str
    entity_id: str | None
    old_value: dict | None
    new_value: dict | None
    comment: str | None


class OkOut(BaseModel):
    ok: bool = True
    message: str | None = None
