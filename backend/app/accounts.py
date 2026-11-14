"""The four local seed accounts use independent, explicitly configured credentials."""
from sqlalchemy import select
from app.db import User
from app.auth import passwords

ROLES = ('admin', 'supervisor', 'agent', 'knowledge')


def ensure_seed_accounts(db, credentials):
    values = [credentials.get(role, '') for role in ROLES]
    if (any(not 12 <= len(value.strip()) <= 200 or value.startswith(('CHANGE_ME', 'GENERATE_')) for value in values)
            or len(set(values)) != len(ROLES)):
        raise ValueError('四个初始账号必须配置至少12位、互不相同的密码；运行 scripts/secure_accounts.py 生成独立凭据')
    users = {user.username: user for user in db.scalars(select(User).where(User.username.in_(ROLES)).with_for_update())}
    if any(user.role != name for name, user in users.items()):
        raise ValueError('初始账号角色与预期不符，请由管理员核验，禁止自动提升权限')
    changed = []
    for role in ROLES:
        user = users.get(role)
        if user is None:
            db.add(User(username=role, role=role, password_hash=passwords.hash(credentials[role])))
            changed.append(role)
        elif not passwords.verify(credentials[role], user.password_hash):
            user.password_hash = passwords.hash(credentials[role])
            changed.append(role)
    db.flush()
    return changed
