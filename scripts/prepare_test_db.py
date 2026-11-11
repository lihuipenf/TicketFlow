from pathlib import Path
from dotenv import dotenv_values
import pymysql

root = Path(__file__).resolve().parents[1]
config = dotenv_values(root / '.env')
connection = pymysql.connect(host='127.0.0.1', port=3307, user='root', password=config['LOCAL_MYSQL_ROOT_PASSWORD'])
with connection.cursor() as cursor:
    cursor.execute('CREATE DATABASE IF NOT EXISTS ticketflow_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    cursor.execute("GRANT ALL ON ticketflow_test.* TO 'ticketflow'@'127.0.0.1'")
connection.close()
print('Dedicated test database ready.')
