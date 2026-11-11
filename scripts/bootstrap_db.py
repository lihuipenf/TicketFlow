"""Provision only the isolated local instance (port 3307); never the user's existing MySQL."""
from pathlib import Path
import secrets
import time
import pymysql

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.env').exists():
    raise SystemExit('.env already exists; refusing to replace credentials.')
for attempt in range(30):
    try:
        conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='')
        break
    except pymysql.OperationalError:
        time.sleep(1)
else:
    raise SystemExit('Isolated MySQL is not reachable on port 3307.')
db_password, root_password, admin_password = [secrets.token_urlsafe(24) for _ in range(3)]
with conn.cursor() as cur:
    cur.execute('CREATE DATABASE IF NOT EXISTS ticketflow CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    cur.execute("CREATE USER 'ticketflow'@'127.0.0.1' IDENTIFIED BY %s", (db_password,))
    cur.execute("GRANT ALL ON ticketflow.* TO 'ticketflow'@'127.0.0.1'")
    cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (root_password,))
conn.close()
template = (ROOT / '.env.example').read_text(encoding='utf-8')
template = template.replace('ticketflow:CHANGE_ME@', f'ticketflow:{db_password}@')
template = template.replace('GENERATE_A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS', secrets.token_urlsafe(48))
template = template.replace('CHANGE_ME_AT_LEAST_12_CHARACTERS', admin_password)
(ROOT / '.env').write_text(template + '\nLOCAL_MYSQL_ROOT_PASSWORD=' + root_password + '\n', encoding='utf-8')
print('Isolated database provisioned. Credentials stored in ignored .env; no secrets printed.')
