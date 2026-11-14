"""Bound upload resources and authenticate before FastAPI parses multipart."""
from tempfile import SpooledTemporaryFile
from threading import BoundedSemaphore
import anyio
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.responses import JSONResponse
from app.auth import current_user
from app.config import settings
from app.db import Session


def authorize_upload(token):
    with Session() as db:
        user = current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
        if user.role not in ('admin', 'supervisor', 'knowledge'):
            raise HTTPException(403, '当前角色无权上传知识文档')


class UploadIngress:
    def __init__(self, app, *, authorize=None, max_request_bytes=None,
                 timeout_seconds=None, max_concurrent=None):
        cfg = settings()
        self.app = app
        self.authorize = authorize or authorize_upload
        self.max_bytes = max_request_bytes if max_request_bytes is not None else cfg.upload_max_request_bytes
        self.timeout = timeout_seconds if timeout_seconds is not None else cfg.upload_timeout_seconds
        capacity = max_concurrent if max_concurrent is not None else cfg.upload_max_concurrent
        self.slots = BoundedSemaphore(capacity)
        self.auth_slots = BoundedSemaphore(capacity)

    def bounded_authorize(self, token):
        # This lease belongs to the thread, not to its cancellable HTTP waiter.
        if not self.auth_slots.acquire(blocking=False):
            raise HTTPException(429, '上传鉴权繁忙，请稍后重试')
        try:
            self.authorize(token)
        finally:
            self.auth_slots.release()

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        root = scope.get('root_path', '')
        if root and path.startswith(root + '/'):
            path = path[len(root):]
        if scope['type'] != 'http' or scope.get('method') != 'POST' or path.rstrip('/') != '/api/v1/knowledge/documents':
            return await self.app(scope, receive, send)

        async def reject(status, detail):
            headers = {'Connection': 'close'}
            if status == 429:
                headers['Retry-After'] = '1'
            await JSONResponse({'detail': detail}, status_code=status, headers=headers)(scope, receive, send)

        lengths = [value for name, value in scope['headers'] if name.lower() == b'content-length']
        has_transfer_encoding = any(name.lower() == b'transfer-encoding' for name, _ in scope['headers'])
        if (len(lengths) > 1 or (lengths and has_transfer_encoding)
                or any(len(value) > 20 or not value.isdigit() for value in lengths)):
            return await reject(400, '无效或冲突的上传长度头')
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > self.max_bytes:
            return await reject(413, '上传请求体超出限制')
        authorization = [value for name, value in scope['headers'] if name.lower() == b'authorization']
        if len(authorization) != 1:
            return await reject(401, '请先登录')
        try:
            scheme, token = authorization[0].decode('ascii').split()
            if scheme.lower() != 'bearer' or len(token) > 8192:
                raise ValueError
        except (UnicodeDecodeError, ValueError):
            return await reject(401, '无效的登录凭据')
        if not self.slots.acquire(blocking=False):
            return await reject(429, '上传并发已满，请稍后重试')
        body = None
        try:
            try:
                with anyio.fail_after(self.timeout):
                    await anyio.to_thread.run_sync(self.bounded_authorize, token, abandon_on_cancel=True)
                    # Only authenticated callers can allocate temporary upload storage.
                    body = SpooledTemporaryFile(max_size=64 * 1024, mode='w+b')
                    total = 0
                    while True:
                        message = await receive()
                        if message['type'] == 'http.disconnect':
                            return
                        chunk = message.get('body', b'')
                        total += len(chunk)
                        if total > self.max_bytes:
                            return await reject(413, '上传请求体超出限制')
                        body.write(chunk)
                        if not message.get('more_body', False):
                            break
                        await anyio.lowlevel.checkpoint()
                    if declared is not None and declared != total:
                        return await reject(400, '实际上传长度与声明不一致')
            except HTTPException as exc:
                return await reject(exc.status_code, exc.detail)
            except TimeoutError:
                return await reject(408, '上传超时，请在规定时间内完成上传')
            # Receiving is complete: application processing has its own lifecycle.
            body.seek(0)
            complete = False
            async def replay():
                nonlocal complete
                if complete:
                    return await receive()
                chunk = body.read(64 * 1024)
                complete = body.tell() == total
                return {'type': 'http.request', 'body': chunk, 'more_body': not complete}
            await self.app(scope, replay, send)
        finally:
            if body is not None:
                body.close()
            self.slots.release()
