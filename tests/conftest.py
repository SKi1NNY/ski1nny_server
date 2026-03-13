from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import Base
from app.models import ingredient as ingredient_models
from app.models import product as product_models
from app.models import trouble_log as trouble_log_models
from app.models import user as user_models

# Import model modules so Base.metadata includes all mapped tables.
MODEL_MODULES = (
    ingredient_models,
    product_models,
    trouble_log_models,
    user_models,
)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return os.getenv("TEST_DATABASE_URL", settings.sqlalchemy_database_uri)


@pytest.fixture(scope="session")
def engine(test_database_url: str):
    engine = create_engine(test_database_url, future=True)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    testing_session_local = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    session = testing_session_local()
    transaction = session.begin()

    try:
        yield session
    finally:
        if transaction.is_active:
            transaction.rollback()
        session.close()
