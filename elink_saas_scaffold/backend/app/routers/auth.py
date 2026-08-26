from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.TokenResponse)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    """
    Creates a brand new tenant (Business) plus its first admin User.
    This is the moment a new customer business is born in the system —
    everything they create afterward will be scoped to this business_id.
    """
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    business = models.Business(name=payload.business_name)
    db.add(business)
    db.flush()  # gets business.id without committing yet

    user = models.User(
        business_id=business.id,
        name=payload.owner_name,
        email=payload.email,
        hashed_password=auth.hash_password(payload.password),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth.create_access_token(user.id)
    return schemas.TokenResponse(
        access_token=token,
        business_name=business.name,
        user_name=user.name,
        role=user.role,
    )


@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not auth.verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = auth.create_access_token(user.id)
    business = db.query(models.Business).filter(models.Business.id == user.business_id).first()
    return schemas.TokenResponse(
        access_token=token,
        business_name=business.name,
        user_name=user.name,
        role=user.role,
    )
