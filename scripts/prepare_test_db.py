"""Provision the local test account; never grant the test runner business access."""
from pathlib import Path
import secrets
import sys
from dotenv import dotenv_values, set_key
from sqlalchemy.engine import make_url
import pymysql

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
from app.database_safety import validate_test_database_url, validate_test_grants

config = dotenv_values(root / '.env')
business = make_url(config['DATABASE_URL'])
if business.host not in ('127.0.0.1', 'localhost') or business.port != 3307:
    raise SystemExit('此引导脚本仅适用于本机3307实例；外部环境请手工创建独立测试库和专用账号。')
test_url = config.get('TEST_DATABASE_URL') or business.set(
    username='ticketflow_tests', password=secrets.token_urlsafe(32),
    database=business.database + '_test', query={'charset': 'utf8mb4'},
).render_as_string(hide_password=False)
validate_test_database_url(config['DATABASE_URL'], test_url)
target = make_url(test_url)
if not target.password or target.password.startswith('CHANGE_ME'):
    target = target.set(password=secrets.token_urlsafe(32))
    test_url = target.render_as_string(hide_password=False)
if target.username != 'ticketflow_tests' or target.host != business.host or target.port != business.port:
    raise SystemExit('本机脚本仅管理同实例 ticketflow_tests 账号；其他配置请手工配置最小权限。')
if not target.password:
    raise SystemExit('测试账号须配置独立密码。')

connection = pymysql.connect(host=business.host, port=3307, user='root', password=config['LOCAL_MYSQL_ROOT_PASSWORD'])
try:
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{target.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        cursor.execute('CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s', (target.username, '127.0.0.1', target.password))
        cursor.execute('ALTER USER %s@%s IDENTIFIED BY %s', (target.username, '127.0.0.1', target.password))
        cursor.execute('REVOKE ALL PRIVILEGES, GRANT OPTION FROM %s@%s', (target.username, '127.0.0.1'))
        # Escape schema-pattern underscores, not merely SQL identifier quotes.
        grant_database = target.database.replace('_', r'\_')
        cursor.execute(f'GRANT ALL ON `{grant_database}`.* TO %s@%s', (target.username, '127.0.0.1'))
finally:
    connection.close()

with pymysql.connect(host=target.host, port=target.port, user=target.username,
                     password=target.password, database=target.database) as test_connection:
    with test_connection.cursor() as cursor:
        cursor.execute('SHOW GRANTS')
        validate_test_grants([row[0] for row in cursor.fetchall()], target.database)
set_key(str(root / '.env'), 'TEST_DATABASE_URL', test_url)
print('Dedicated test database/account ready; TEST_DATABASE_URL saved to ignored .env. No credentials printed.')
