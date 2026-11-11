import os
from pathlib import Path
from dotenv import dotenv_values
import pytest
from sqlalchemy.orm import Session

config = dotenv_values(Path(__file__).resolve().parents[2] / '.env')
os.environ['DATABASE_URL'] = os.environ.get('TEST_DATABASE_URL') or config['DATABASE_URL'].replace('/ticketflow?', '/ticketflow_test?')
# Unit/integration tests must never inherit a real provider credential from local .env.
# SDK transport fixtures inject their own test-only credentials explicitly.
os.environ['LLM_API_KEY'] = ''
from app.db import engine, Base
Base.metadata.create_all(engine)


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode='create_savepoint', expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
