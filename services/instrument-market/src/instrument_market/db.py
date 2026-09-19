from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from instrument_market.config import get_settings
from instrument_market.models import Base


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    connect_args: dict[str, bool] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


def get_session() -> Generator[Session]:
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as session:
        yield session


def database_is_ready() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def create_local_schema() -> None:
    from instrument_market.storage.receipts import metadata as receipt_metadata

    Base.metadata.create_all(get_engine())
    receipt_metadata.create_all(get_engine())
