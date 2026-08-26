import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummary)
def summary(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    now = datetime.datetime.utcnow()
    today_start = datetime.datetime(now.year, now.month, now.day)
    month_start = datetime.datetime(now.year, now.month, 1)

    def revenue_since(start):
        return (
            db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
            .filter(
                models.Sale.business_id == user.business_id,
                models.Sale.voided == False,  # noqa: E712
                models.Sale.created_at >= start,
            )
            .scalar()
        )

    today_revenue = revenue_since(today_start)
    month_revenue = revenue_since(month_start)

    today_sales_count = (
        db.query(func.count(models.Sale.id))
        .filter(
            models.Sale.business_id == user.business_id,
            models.Sale.voided == False,  # noqa: E712
            models.Sale.created_at >= today_start,
        )
        .scalar()
    )

    outstanding_debt = (
        db.query(func.coalesce(func.sum(models.Debtor.balance), 0.0))
        .filter(models.Debtor.business_id == user.business_id, models.Debtor.status == "open")
        .scalar()
    )

    # Low stock: profiles whose available voucher count is below threshold.
    profiles = (
        db.query(models.VoucherProfile)
        .filter(models.VoucherProfile.business_id == user.business_id)
        .all()
    )
    low_stock = []
    for p in profiles:
        available = (
            db.query(func.count(models.Voucher.id))
            .filter(
                models.Voucher.business_id == user.business_id,
                models.Voucher.profile_id == p.id,
                models.Voucher.sold == False,  # noqa: E712
            )
            .scalar()
        )
        if (available or 0) < p.low_stock_threshold:
            low_stock.append(p.name)

    return schemas.DashboardSummary(
        today_revenue=today_revenue,
        today_sales_count=today_sales_count,
        month_revenue=month_revenue,
        outstanding_debt=outstanding_debt,
        low_stock_profiles=low_stock,
    )
