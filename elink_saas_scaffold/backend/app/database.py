"""
Database engine + session setup.

Local development: defaults to a SQLite file (elink_saas.db) so you can run
this immediately with zero external setup.

Production: set the DATABASE_URL environment variable to a Postgres URL, e.g.

    postgresql+psycopg2://user:password@host:5432/elink

No other code changes are needed to switch — SQLAlchemy abstracts the
dialect. Postgres is what you actually want in production because SQLite
does not handle concurrent writes from many tenants well; SQLite here is
purely for local development and testing this scaffold.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./elink_saas.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
