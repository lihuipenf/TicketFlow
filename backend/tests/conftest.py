import os
from pathlib import Path
from dotenv import dotenv_values
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.database_safety import validate_test_database_url, validate_test_grants

config = dotenv_values(Path(__file__).resolve().parents[2] / '.env')
business_url = os.environ.get('DATABASE_URL') or config.get('DATABASE_URL')
test_url = os.environ.get('TEST_DATABASE_URL') or config.get('TEST_DATABASE_URL')
os.environ['DATABASE_URL'] = validate_test_database_url(business_url, test_url)
# Unit/integration tests must never inherit a real provider credential from local .env.
# SDK transport fixtures inject their own test-only credentials explicitly.
os.environ['LLM_API_KEY'] = ''
os.environ['JWT_SECRET'] = 'test-only-jwt-secret-at-least-32-characters'
os.environ['ADMIN_PASSWORD'] = 'test-only-admin-password'
os.environ['SUPERVISOR_PASSWORD'] = 'test-only-supervisor-password'
os.environ['AGENT_PASSWORD'] = 'test-only-agent-password'
os.environ['KNOWLEDGE_PASSWORD'] = 'test-only-knowledge-password'
from app.db import engine, Base
if engine.url != make_url(test_url):
    raise ValueError('应用引擎已初始化为其他目标，拒绝运行测试；请使用新的测试进程')
with engine.connect() as connection:
    validate_test_grants(connection.scalars(text('SHOW GRANTS')).all(), make_url(test_url).database)
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
