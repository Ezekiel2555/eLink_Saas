from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, vouchers, sales, debtors, agents, dashboard

# Schema creation/evolution is now Alembic's job (see alembic/), not the
# app's. Run `alembic upgrade head` before starting the app for the first
# time, and after pulling any change that touches app/models.py. The app
# no longer auto-creates tables on startup — doing that alongside a real
# migration tool is how you accidentally get a database Alembic doesn't
# think matches its own migration history, which is a genuinely nasty
# problem to untangle once there's real customer data in it.

app = FastAPI(title="eLink SaaS API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your actual frontend domain before going live
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(vouchers.router)
app.include_router(sales.router)
app.include_router(debtors.router)
app.include_router(agents.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}
