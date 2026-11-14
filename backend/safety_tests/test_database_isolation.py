"""Runs before integration tests: never opens a database connection."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('business,test', [
    ('mysql+pymysql://business:private@localhost/shop', None),
    ('mysql+pymysql://business:private@localhost/ticketflow', None),
    ('mysql+pymysql://business:private@localhost/shop', 'mysql+pymysql://tests:private@localhost/shop'),
    ('mysql+pymysql://business:private@localhost/shop', 'mysql+pymysql://business:private@localhost/shop_test'),
    ('mysql+pymysql://business:private@localhost/shop', 'mysql+pymysql://tests:private@localhost/other'),
    ('mysql+pymysql://business:private@localhost/shop', 'mysql+pymysql://tests:private@localhost/shop_test?database=shop'),
])
def test_unsafe_test_configuration_is_rejected_before_engine_creation(business, test):
    # A spy stops engine creation even when the old unsafe bootstrap is exercised.
    program = '''
import json, os, runpy, sys
from unittest.mock import patch
config=json.loads(sys.argv[1])
os.environ['DATABASE_URL']=config['DATABASE_URL']
os.environ.pop('TEST_DATABASE_URL',None)
with patch('dotenv.dotenv_values',return_value=config), patch('sqlalchemy.create_engine',side_effect=RuntimeError('ENGINE_ATTEMPTED')):
    try:
        runpy.run_path('tests/conftest.py')
    except ValueError:
        print('REJECTED_BEFORE_ENGINE')
    except RuntimeError as error:
        print(str(error))
'''
    config = {'DATABASE_URL': business}
    if test:
        config['TEST_DATABASE_URL'] = test
    result = subprocess.run([sys.executable, '-B', '-c', program, json.dumps(config)],
                            cwd=BACKEND, capture_output=True, text=True, check=True,
                            env={**os.environ, 'PYTHONPATH': str(BACKEND)})
    assert result.stdout.strip() == 'REJECTED_BEFORE_ENGINE'


def test_valid_explicit_configuration_reaches_engine_creation():
    from app.database_safety import validate_test_database_url, validate_test_grants
    url = 'mysql+pymysql://tests:synthetic@127.0.0.1/shop_test?charset=utf8mb4'
    assert validate_test_database_url('mysql+pymysql://business:synthetic@127.0.0.1/shop', url) == url
    validate_test_grants(["GRANT USAGE ON *.* TO 'tests'@'127.0.0.1'",
                          "GRANT ALL PRIVILEGES ON `shop\\_test`.* TO 'tests'@'127.0.0.1'"], 'shop_test')


@pytest.mark.parametrize('grant', [
    "GRANT ALL PRIVILEGES ON *.* TO 'tests'@'127.0.0.1'",
    "GRANT SELECT ON `shop`.* TO 'tests'@'127.0.0.1'",
    "GRANT ALL PRIVILEGES ON `shop_test`.* TO 'tests'@'127.0.0.1'",
    "GRANT ALL PRIVILEGES ON `shop\\_test`.* TO 'tests'@'127.0.0.1' WITH GRANT OPTION",
    "GRANT 'privileged_role' TO 'tests'@'127.0.0.1'",
])
def test_overprivileged_test_account_is_rejected(grant):
    from app.database_safety import validate_test_grants
    with pytest.raises(ValueError):
        validate_test_grants([grant], 'shop_test')


def test_preloaded_business_engine_is_rejected_before_connecting():
    program = '''
import os, runpy, sys, types
from unittest.mock import patch
from sqlalchemy.engine import make_url
business='mysql+pymysql://business:synthetic@localhost/shop'
test='mysql+pymysql://tests:synthetic@localhost/shop_test'
os.environ['DATABASE_URL']=business
os.environ['TEST_DATABASE_URL']=test
def forbidden():
    raise RuntimeError('BUSINESS_CONNECTION_ATTEMPTED')
module=types.ModuleType('app.db')
module.engine=types.SimpleNamespace(url=make_url(business),connect=forbidden)
module.Base=object()
sys.modules['app.db']=module
with patch('dotenv.dotenv_values',return_value={'DATABASE_URL':business,'TEST_DATABASE_URL':test}):
    try:
        runpy.run_path('tests/conftest.py')
    except ValueError:
        print('REJECTED_BEFORE_CONNECT')
    except RuntimeError as error:
        print(str(error))
'''
    result = subprocess.run([sys.executable, '-B', '-c', program], cwd=BACKEND,
                            capture_output=True, text=True, check=True,
                            env={**os.environ, 'PYTHONPATH': str(BACKEND)})
    assert result.stdout.strip() == 'REJECTED_BEFORE_CONNECT'
