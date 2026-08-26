from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=List[schemas.AgentOut])
def list_agents(
    db: Session = Depends(get_db), user: models.User = Depends(auth.get_current_user)
):
    return (
        db.query(models.Agent)
        .filter(models.Agent.business_id == user.business_id)
        .all()
    )


@router.post("/", response_model=schemas.AgentOut)
def create_agent(
    payload: schemas.AgentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    agent = models.Agent(business_id=user.business_id, **payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/{agent_id}/commission")
def agent_commission(
    agent_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    """
    Mirrors eLink's own logic: commission earned is never stored — it's
    derived live from (revenue attributed to this agent * their current
    rate) + manual adjustments, minus what's already been paid out.
    """
    agent = (
        db.query(models.Agent)
        .filter(models.Agent.id == agent_id, models.Agent.business_id == user.business_id)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    revenue = (
        db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
        .filter(
            models.Sale.business_id == user.business_id,
            models.Sale.agent_id == agent_id,
            models.Sale.voided == False,  # noqa: E712
        )
        .scalar()
    )
    manual = (
        db.query(func.coalesce(func.sum(models.CommissionAdjustment.amount), 0.0))
        .filter(
            models.CommissionAdjustment.business_id == user.business_id,
            models.CommissionAdjustment.agent_id == agent_id,
        )
        .scalar()
    )
    paid = (
        db.query(func.coalesce(func.sum(models.Payout.amount), 0.0))
        .filter(
            models.Payout.business_id == user.business_id,
            models.Payout.agent_id == agent_id,
        )
        .scalar()
    )
    earned = round(revenue * (agent.commission_rate / 100.0) + manual, 2)
    balance_due = round(earned - paid, 2)
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "revenue": revenue,
        "commission_rate": agent.commission_rate,
        "manual_adjustments": manual,
        "earned": earned,
        "paid": paid,
        "balance_due": balance_due,
    }


@router.post("/commission-adjustments")
def add_commission_adjustment(
    payload: schemas.CommissionAdjustmentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    entry = models.CommissionAdjustment(business_id=user.business_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    return {"ok": True, "id": entry.id}


@router.post("/payouts")
def add_payout(
    payload: schemas.PayoutCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(auth.get_current_user),
):
    entry = models.Payout(business_id=user.business_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    return {"ok": True, "id": entry.id}
