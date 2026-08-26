# eLink SaaS — multi-tenant scaffold

This is a working, tested first slice of turning eLink from a one-computer
desktop app into a hosted product that many businesses can subscribe to.

It is **not** the full eLink feature set — it's the core money-tracking loop
(Dashboard, Record Sale, Vouchers, Sales Log, Debtors, Agent Commission),
built to prove the multi-tenant architecture actually works, end to end,
before investing time porting every other tab (MikroTik sync, Till
Reconciliation, Jobs & Estimates, Employees, etc.).

## What's actually here

```
elink_saas/
├── backend/
│   ├── app/
│   │   ├── main.py          ← FastAPI app, wires everything together
│   │   ├── database.py      ← SQLite locally, swap to Postgres via env var
│   │   ├── models.py        ← the multi-tenant schema (every table has business_id)
│   │   ├── schemas.py       ← API request/response shapes
│   │   ├── auth.py          ← JWT login, the get_current_user dependency
│   │   └── routers/
│   │       ├── auth.py      ← signup / login
│   │       ├── vouchers.py  ← voucher profiles + stock
│   │       ├── sales.py     ← record sale, sales log, void
│   │       ├── debtors.py   ← debtor list + payments
│   │       ├── agents.py    ← agents + commission calculation
│   │       └── dashboard.py ← summary stats
│   └── requirements.txt
├── frontend/
│   └── index.html           ← single-page reference UI (no build step needed)
└── README.md                ← you are here
```

## How I proved this actually works (not just "looks right")

I ran the server and, with a script, signed up two separate fake
businesses — "Kofi Hotspot Shop" and "Ama Internet Cafe" — created
different voucher profiles under each, recorded sales, made a credit
sale that created a debtor, took a partial payment, and checked
dashboards and agent commissions. The key assertion that matters most:

> Ama's API calls can **never** see Kofi's data, and vice versa, even
> though they're both rows in the exact same tables in the exact same
> database.

That's the whole point of multi-tenancy, and it's the part most worth
verifying rather than taking on faith — see the transcript above in this
conversation for the full test output. Every check passed.

## Running it yourself

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
This starts on `http://127.0.0.1:8000` and creates `elink_saas.db`
(a local SQLite file) automatically. Visit `http://127.0.0.1:8000/docs`
for the interactive API explorer — every endpoint is listed there.

**Frontend:**
```bash
cd frontend
python3 -m http.server 8080
```
Then open `http://127.0.0.1:8080` in a browser. Create a business, log in,
and click through Dashboard → Record Sale → Vouchers → Sales Log →
Debtors → Agent Commission. It's talking to the real API the whole time.

## Postgres + Alembic migrations — done and proven

Both of the first two "not done yet" items are now actually done, not
just planned. Here's exactly what was proven, so you don't have to take
it on faith:

- Installed real Postgres 16 locally, created a dedicated `elink_app`
  database user and an `elink_saas` database (not a shared/superuser
  account — see `.env.example` for how this was set up).
- Set `DATABASE_URL` to point at it. **No application code changed** —
  `app/database.py` already supported this via the environment variable;
  Postgres and SQLite are both just SQLAlchemy dialects underneath.
- Ran `alembic init`, wired `alembic/env.py` to read the same
  `DATABASE_URL` the app uses and to know about every model in
  `app/models.py`, so `--autogenerate` diffs against your real schema
  instead of you hand-writing migrations from scratch.
- Generated and applied the **initial migration** — created all 11
  tables in real Postgres purely from `alembic upgrade head`, with
  `app/main.py`'s old `create_all()` call removed (Alembic now owns
  schema creation, which is the actual point of adding it).
- Re-ran the full two-tenant isolation test (Kofi vs. Ama) against this
  real Postgres database — identical result to the SQLite version, every
  check passed.
- **Then proved the part that actually matters**: with real data already
  sitting in Postgres (two real user accounts, one real sale), added a
  new `phone` column to the `User` model, ran
  `alembic revision --autogenerate`, and applied it. Result: a single,
  correct `ADD COLUMN ... NULLABLE` — Kofi and Ama's existing accounts
  were untouched, the new column just sits there empty for them, and
  Kofi could still log in immediately afterward. That's the actual
  guarantee migrations buy you over `create_all()`: you can evolve the
  schema on a database with real customer data in it, live, without
  losing anything.

**Using it going forward:**
```bash
# whenever you change app/models.py:
alembic revision --autogenerate -m "describe the change"
# review the generated file in alembic/versions/ before applying —
# autogenerate is very good but not infallible, especially for renames
alembic upgrade head
```

One caveat worth flagging honestly: this was proven on a Postgres
instance running locally in the same sandbox as the app, as a proof of
the mechanism — not against your eventual production host. The commands
and the migration files are identical either way (that's the entire
value of DATABASE_URL-based configuration), but you should still run
this same sequence once against your actual production database before
trusting it with real customers.

## What's deliberately NOT done yet (and why)

I scoped this down on purpose rather than trying to build everything at
once — here's what's left, roughly in the order I'd tackle it:

1. **Paystack subscription billing.** The `Business` model already has
   the fields (`plan`, `subscription_status`, `paystack_subscription_code`)
   — the actual Paystack API calls to create/charge/cancel a subscription
   aren't wired up yet. Your existing `paystack.py` from the desktop app
   has most of the logic needed; it just needs to move server-side.

2. **The MikroTik "bridge" problem.** A hosted server can't reach a
   router sitting on a customer's local network directly. The plan (as
   discussed): a small local agent — really a stripped-down version of
   the current desktop app's `mikrotik_sync.py` — installed on-site,
   that talks to the router locally and phones home to this API. Not
   built yet; the MVP intentionally works without live MikroTik sync
   (customers paste voucher codes in via the batch-add endpoint instead,
   same as any manually-generated batch today).

3. **Password reset, email verification, inviting staff users.** Signup
   and login work; the surrounding account-management flows don't exist
   yet.

4. **Porting the remaining tabs**: Calendar, Customers, Broadcast,
   Vendors, Employees, Jobs & Estimates, Till Reconciliation, Reports,
   Settings, Users, Audit Log, WhatsApp/Telegram/Cloud backup. All
   architecturally straightforward now that the pattern is proven — each
   is "add a table with business_id, add a scoped router, add a tab to
   the frontend" — just volume of work, not new hard problems.

5. **Deployment.** Locally this runs on your machine. To actually put it
   in front of customers you'd deploy the backend somewhere like
   Railway, Render, or Fly.io (Postgres + the FastAPI app), and the
   frontend as a static site (Netlify, Vercel, or the same host). None
   of that is done here — this scaffold is the code, not the hosting.

## Suggested path from here

With Postgres and migrations proven, the next highest-leverage step is
Paystack subscription billing (#1 above) — that's what turns this from
"a working app" into "a business that can charge a pilot customer."
After that, I'd deploy it somewhere real (#5) before porting the
remaining tabs, so you can start learning from an actual pilot customer's
usage which of those tabs (Employees? Till Reconciliation? MikroTik
sync?) they actually ask for first, rather than guessing.
