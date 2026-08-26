"""
Multi-tenant schema.

The core idea: ONE set of tables, shared by every customer business ("tenant").
Every table that holds business data carries a `business_id` foreign key.
Every query in the routers filters by the current user's business_id, so
Business A can never see Business B's rows — even though they're sitting in
the exact same database and tables.

Compare this to the original eLink: there, "isolation between businesses"
was achieved by giving each business its own separate SQLite file on their
own computer. Here, isolation is achieved by a WHERE clause instead of a
separate file. That's the whole trick of multi-tenancy.
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from .database import Base


def now():
    return datetime.datetime.utcnow()


class Business(Base):
    """One row per paying customer (tenant). Everything else hangs off this."""
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=now)

    # Subscription/billing fields — wired up to Paystack Subscriptions later.
    plan = Column(String, default="trial")  # trial | solo | team | full
    subscription_status = Column(String, default="trialing")  # trialing|active|past_due|canceled
    trial_ends_at = Column(DateTime, default=lambda: now() + datetime.timedelta(days=14))
    paystack_customer_code = Column(String, nullable=True)
    paystack_subscription_code = Column(String, nullable=True)

    users = relationship("User", back_populates="business")


class User(Base):
    """A staff login. business_id ties them to exactly one tenant."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    phone = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="admin")  # admin | cashier | agent_manager (mirrors eLink's roles)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now)

    business = relationship("Business", back_populates="users")


class VoucherProfile(Base):
    """A Wi-Fi package definition, e.g. '1 Day Unlimited - GHS 5'."""
    __tablename__ = "voucher_profiles"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    cost_price = Column(Float, default=0.0)  # for margin reporting
    duration_label = Column(String, nullable=True)  # "1 Day", "1 Week", etc.
    low_stock_threshold = Column(Integer, default=10)
    created_at = Column(DateTime, default=now)


class Voucher(Base):
    """A single voucher code."""
    __tablename__ = "vouchers"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("voucher_profiles.id"), nullable=False, index=True)
    code = Column(String, nullable=False, index=True)
    sold = Column(Boolean, default=False)
    sold_sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    created_at = Column(DateTime, default=now)


class Agent(Base):
    """A reseller/agent who sells on commission."""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    commission_rate = Column(Float, default=0.0)  # percent
    created_at = Column(DateTime, default=now)


class Sale(Base):
    """A recorded sale. total is what the customer paid (or owes, if credit)."""
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("voucher_profiles.id"), nullable=False)
    profile_name = Column(String, nullable=False)  # snapshot, in case profile is edited/deleted later
    qty = Column(Integer, nullable=False, default=1)
    total = Column(Float, nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    is_credit = Column(Boolean, default=False)  # true if this became a debtor record
    voided = Column(Boolean, default=False)
    voided_at = Column(DateTime, nullable=True)
    void_reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)


class Debtor(Base):
    """A customer who owes money for a credit sale."""
    __tablename__ = "debtors"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=True)
    total = Column(Float, nullable=False)
    balance = Column(Float, nullable=False)
    status = Column(String, default="open")  # open | settled | voided
    created_at = Column(DateTime, default=now)


class DebtorPayment(Base):
    """A partial/full payment against a debtor's balance."""
    __tablename__ = "debtor_payments"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    debtor_id = Column(Integer, ForeignKey("debtors.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)


class CommissionAdjustment(Base):
    """A manual flat-amount commission/allowance entry for an agent."""
    __tablename__ = "commission_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)


class Payout(Base):
    """An actual commission payment made out to an agent."""
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)
