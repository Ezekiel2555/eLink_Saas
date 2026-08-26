from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("/", response_model=schemas.SaleOut)
def record_sale(
    payload: schemas.SaleCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Records a sale. If is_credit is set, this also creates a Debtor record
    for whatever wasn't paid upfront — same behaviour as eLink's "Mark sale
    as unpaid/credit" flow, just server-side and tenant-scoped now.
    """
    profile = (
        db.query(models.VoucherProfile)
        .filter(
            models.VoucherProfile.id == payload.profile_id,
            models.VoucherProfile.business_id == user.business_id,
        )
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Voucher profile not found")

    if payload.is_credit and not payload.customer_name:
        raise HTTPException(status_code=400, detail="customer_name is required for a credit sale")

    sale = models.Sale(
        business_id=user.business_id,
        profile_id=profile.id,
        profile_name=profile.name,
        qty=payload.qty,
        total=payload.total,
        agent_id=payload.agent_id,
        is_credit=payload.is_credit,
    )
    db.add(sale)
    db.flush()  # get sale.id

    # Allocate available vouchers of this profile to this sale.
    available = (
        db.query(models.Voucher)
        .filter(
            models.Voucher.business_id == user.business_id,
            models.Voucher.profile_id == profile.id,
            models.Voucher.sold == False,  # noqa: E712
        )
        .limit(payload.qty)
        .all()
    )
    for v in available:
        v.sold = True
        v.sold_sale_id = sale.id
        v.agent_id = payload.agent_id

    if payload.is_credit:
        owing = round(payload.total - payload.paid_now, 2)
        if owing > 0:
            debtor = models.Debtor(
                business_id=user.business_id,
                sale_id=sale.id,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                total=payload.total,
                balance=owing,
                status="open",
            )
            db.add(debtor)

    db.commit()
    db.refresh(sale)
    return sale


@router.get("/", response_model=List[schemas.SaleOut])
def sales_log(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.Sale)
        .filter(models.Sale.business_id == user.business_id)
        .order_by(models.Sale.id.desc())
        .limit(limit)
        .all()
    )


@router.post("/{sale_id}/void")
def void_sale(
    sale_id: int,
    payload: schemas.VoidSaleRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Voiding: returns any linked vouchers to available stock, and voids the
    linked debtor if one exists — mirroring eLink's performVoidSale logic.
    Unlike a plain delete, void keeps the historical row (flagged, not
    removed) so reports and the audit trail stay intact.
    """
    sale = (
        db.query(models.Sale)
        .filter(models.Sale.id == sale_id, models.Sale.business_id == user.business_id)
        .first()
    )
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    if sale.voided:
        raise HTTPException(status_code=400, detail="Sale is already voided")

    vouchers = (
        db.query(models.Voucher)
        .filter(models.Voucher.business_id == user.business_id, models.Voucher.sold_sale_id == sale_id)
        .all()
    )
    for v in vouchers:
        v.sold = False
        v.sold_sale_id = None
        v.agent_id = None

    debtor = (
        db.query(models.Debtor)
        .filter(models.Debtor.business_id == user.business_id, models.Debtor.sale_id == sale_id)
        .first()
    )
    if debtor:
        debtor.status = "voided"
        debtor.balance = 0.0

    sale.voided = True
    from datetime import datetime as _dt
    sale.voided_at = _dt.utcnow()
    sale.void_reason = payload.reason

    db.commit()
    return {"ok": True, "released_vouchers": len(vouchers)}
