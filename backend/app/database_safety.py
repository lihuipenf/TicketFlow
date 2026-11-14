"""Validate test targets without importing the application's database engine."""
import re
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def validate_test_database_url(business_url, test_url):
    if not business_url or not test_url:
        raise ValueError('必须显式配置业务 DATABASE_URL 和独立 TEST_DATABASE_URL；禁止自动推导测试库')
    try:
        business, test = make_url(business_url), make_url(test_url)
        if test.drivername != 'mysql+pymysql' or not test.host or not test.username:
            raise ValueError
        if not re.fullmatch(r'[A-Za-z0-9_]+_test(?:_[A-Za-z0-9_]+)?', test.database or ''):
            raise ValueError
        if (test.database or '').casefold() == (business.database or '').casefold():
            raise ValueError
        if test.username.casefold() in {'root', (business.username or '').casefold()}:
            raise ValueError
        # PyMySQL query options can override host/user/database parsed from the URL.
        if set(test.query) - {'charset'}:
            raise ValueError
    except (ValueError, TypeError, AttributeError, ArgumentError):
        raise ValueError('测试库配置不安全：须使用独立的 *_test 库及专用非 root 账号；查询参数仅支持 charset') from None
    return test_url


def validate_test_grants(grants, database):
    """Refuse global, role-based or cross-database privileges before test DDL."""
    for grant in grants:
        match = re.match(r'^GRANT (.+?) ON (.+?) TO ', grant)
        if not match:
            raise ValueError('测试账号不能继承角色或代理权限')
        privileges, target = match.groups()
        if privileges == 'USAGE' and target == '*.*':
            continue
        expected = '`' + database.replace('_', r'\_') + '`.*'
        if target != expected or 'WITH GRANT OPTION' in grant:
            raise ValueError('测试账号必须仅拥有当前测试库权限，库名通配符须转义')
