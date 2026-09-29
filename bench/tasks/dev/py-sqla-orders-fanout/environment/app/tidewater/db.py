"""Engine and session helpers."""

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL_ENV = "TIDEWATER_DATABASE_URL"


def database_url() -> str:
    url = os.environ.get(DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(f"{DATABASE_URL_ENV} is not set")
    return url


def make_engine(url: str | None = None, *, echo: bool = False) -> Engine:
    return create_engine(url or database_url(), echo=echo, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
