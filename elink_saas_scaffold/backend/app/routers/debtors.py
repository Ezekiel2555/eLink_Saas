from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/debtors", tags=["debtors"])


@router.get("/", response_model=List[schemas.DebtorOut])
def list_debtors(
    status: str = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    q = db.query(models.Debtor).filter(models.Debtor.business_id == user.business_id)
    if status:
        q = q.filter(models.Debtor.status == status)
    return q.order_by(models.Debtor.id.desc()).all()


@router.post("/{debtor_id}/payments")
def record_payment(
    debtor_id: int,
    payload: schemas.DebtorPaymentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    debtor = (
        db.query(models.Debtor)
        .filter(models.Debtor.id == debtor_id, models.Debtor.business_id == user.business_id)
        .first()
    )
    if not debtor:
        raise HTTPException(status_code=404, detail="Debtor not found")
    if debtor.status != "open":
        raise HTTPException(status_code=400, detail=f"Debtor account is {debtor.status}, not open")

    amount = min(payload.amount, debtor.balance)
    debtor.balance = round(debtor.balance - amount, 2)
    if debtor.balance <= 0:
        debtor.balance = 0.0
        debtor.status = "settled"

    payment = models.DebtorPayment(
        business_id=user.business_id,
        debtor_id=debtor.id,
        amount=amount,
        note=payload.note,
    )
    db.add(payment)
    db.commit()
    return {"ok": True, "new_balance": debtor.balance, "status": debtor.status}
