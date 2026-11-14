from datetime import timedelta
from hashlib import sha256
import hmac
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import User, now, session

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def credential_stamp(user):
    # Opaque, keyed fingerprint; no password/hash is exposed in the JWT.
    return hmac.new(settings().jwt_secret.get_secret_value().encode(),
                    (user.id + ':' + user.password_hash).encode(), sha256).hexdigest()


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: DBSession = Depends(session)):
    if not credentials:
        raise HTTPException(401, '请先登录')
    try:
        payload = jwt.decode(credentials.credentials, settings().jwt_secret.get_secret_value(), algorithms=['HS256'])
        user = db.get(User, payload['sub'])
        if not user:
            raise ValueError('Unknown user')
        stamp = payload.get('cred')
        if not isinstance(stamp, str) or not hmac.compare_digest(stamp, credential_stamp(user)):
            raise ValueError('Credentials changed')
        return user
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, '登录已过期，请重新登录')


def require(*roles):
    def check(user: User = Depends(current_user)):
        if user.role not in roles:
            raise HTTPException(403, '当前角色无权执行此操作')
        return user
    return check


def login(db, username, password):
    user = db.scalar(select(User).where(User.username == username))
    if not user or not passwords.verify(password, user.password_hash):
        raise HTTPException(401, '用户名或密码不正确')
    secret = settings().jwt_secret.get_secret_value()
    if len(secret) < 32:
        raise HTTPException(503, '请配置 JWT_SECRET')
    token = jwt.encode({'sub': user.id, 'exp': now() + timedelta(hours=8), 'cred': credential_stamp(user)}, secret, algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'user': {'id': user.id, 'username': user.username, 'role': user.role}}
