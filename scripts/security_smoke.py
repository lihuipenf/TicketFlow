"""Real HTTP checks with local credentials; never creates tickets, jobs or uploads."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import sys
from threading import Thread
import time

from dotenv import dotenv_values
import httpx
import jwt
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.main import app
from app.config import settings


def headers_only(address, token=None, length=10):
    connection = socket.create_connection(address, timeout=5)
    authorization = f'Authorization: Bearer {token}\r\n' if token else ''
    connection.sendall((
        'POST /api/v1/knowledge/documents HTTP/1.1\r\n'
        f'Host: 127.0.0.1\r\n{authorization}'
        'Content-Type: multipart/form-data; boundary=security-smoke\r\n'
        f'Content-Length: {length}\r\nConnection: close\r\n\r\n'
    ).encode('ascii'))
    return connection


def status(connection):
    return int(connection.recv(4096).split(b'\r\n', 1)[0].split()[1])


def main():
    config = dotenv_values(ROOT / '.env')
    roles = ('admin', 'supervisor', 'agent', 'knowledge')
    if any(not config.get(role.upper() + '_PASSWORD') for role in roles):
        raise SystemExit('请先运行 scripts/secure_accounts.py 配置独立账号。')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    address = listener.getsockname()
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
    thread = Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    held = []
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if time.monotonic() >= deadline or not thread.is_alive():
                raise RuntimeError('验证用API未启动')
            time.sleep(0.02)
        with httpx.Client(base_url=f'http://127.0.0.1:{address[1]}/api/v1', timeout=5) as client:
            tokens, users = {}, {}
            for role in roles:
                response = client.post('/auth/login', json={
                    'username': role, 'password': config[role.upper() + '_PASSWORD']})
                assert response.status_code == 200, f'{role} login failed'
                tokens[role] = response.json()['access_token']
                users[role] = response.json()['user']['id']
                me = client.get('/auth/me', headers={'Authorization': 'Bearer ' + tokens[role]})
                assert me.status_code == 200 and me.json()['role'] == role
            assert client.post('/auth/login', json={'username': 'admin', 'password': config['AGENT_PASSWORD']}).status_code == 401
            legacy = jwt.encode({'sub': users['admin'], 'exp': datetime.now(timezone.utc) + timedelta(minutes=1)},
                                settings().jwt_secret.get_secret_value(), algorithm='HS256')
            assert client.get('/auth/me', headers={'Authorization': 'Bearer ' + legacy}).status_code == 401
            for token, length, expected in [
                (None, 10, 401), (tokens['agent'], 10, 403),
                (tokens['knowledge'], settings().upload_max_request_bytes + 1, 413),
            ]:
                with headers_only(address, token, length) as connection:
                    assert status(connection) == expected
            # Admit header-only valid uploads, then prove overload is rejected without a body.
            for _ in range(settings().upload_max_concurrent):
                held.append(headers_only(address, tokens['knowledge']))
            assert client.get('/health').status_code == 200
            with headers_only(address, tokens['knowledge']) as connection:
                assert status(connection) == 429
        print('PASS: real HTTP four-role login, cross-role password rejection, legacy JWT rejection, pre-body 401/403/413, upload concurrency 429; no business writes or model calls.')
    finally:
        for connection in held:
            connection.close()
        server.should_exit = True
        thread.join(timeout=15)
        listener.close()
        if thread.is_alive():
            raise RuntimeError('验证用API未按期退出')


if __name__ == '__main__':
    main()
