import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# ---------- Auth ----------

class SignupRequest(BaseModel):
    business_name: str
    owner_name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    business_name: str
    user_name: str
    role: str


# ---------- Voucher profiles ----------

class VoucherProfileCreate(BaseModel):
    name: str
    price: float
    cost_price: float = 0.0
    duration_label: Optional[str] = None
    low_stock_threshold: int = 10


class VoucherProfileOut(VoucherProfileCreate):
    id: int
    available_count: int = 0

    class Config:
        from_attributes = True


# ---------- Vouchers ----------

class VoucherBatchCreate(BaseModel):
    profile_id: int
    codes: List[str]  # paste-in codes, e.g. from a MikroTik export


class VoucherOut(BaseModel):
    id: int
    profile_id: int
    code: str
    sold: bool

    class Config:
        from_attributes = True


# ---------- Agents ----------

class AgentCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    commission_rate: float = 0.0


class AgentOut(AgentCreate):
    id: int

    class Config:
        from_attributes = True


class CommissionAdjustmentCreate(BaseModel):
    agent_id: int
    amount: float
    note: Optional[str] = None


class PayoutCreate(BaseModel):
    agent_id: int
    amount: float
    note: Optional[str] = None


# ---------- Sales ----------

class SaleCreate(BaseModel):
    profile_id: int
    qty: int = 1
    total: float
    agent_id: Optional[int] = None
    is_credit: bool = False
    customer_name: Optional[str] = None  # required if is_credit
    customer_phone: Optional[str] = None
    paid_now: float = 0.0  # if is_credit, how much was paid upfront


class SaleOut(BaseModel):
    id: int
    profile_id: int
    profile_name: str
    qty: int
    total: float
    agent_id: Optional[int]
    is_credit: bool
    voided: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class VoidSaleRequest(BaseModel):
    reason: str


# ---------- Debtors ----------

class DebtorOut(BaseModel):
    id: int
    sale_id: int
    customer_name: str
    customer_phone: Optional[str]
    total: float
    balance: float
    status: str

    class Config:
        from_attributes = True


class DebtorPaymentCreate(BaseModel):
    amount: float
    note: Optional[str] = None


# ---------- Dashboard ----------

class DashboardSummary(BaseModel):
    today_revenue: float
    today_sales_count: float
    month_revenue: float
    outstanding_debt: float
    low_stock_profiles: List[str]
