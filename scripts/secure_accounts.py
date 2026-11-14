"""Initialize/synchronize independent seed credentials; never print credentials."""
from pathlib import Path
import argparse
import secrets
import sys
from dotenv import dotenv_values, set_key

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend'))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--rotate', action='store_true', help='Rotate all four local seed account passwords')
args = parser.parse_args()
env_file = root / '.env'
original = env_file.read_bytes()
config = dotenv_values(env_file)
roles = ('admin', 'supervisor', 'agent', 'knowledge')
credentials = {role: config.get(role.upper() + '_PASSWORD') or '' for role in roles}
if args.rotate or any(len(value) < 12 or value.startswith(('CHANGE_ME', 'GENERATE_')) for value in credentials.values()) or len(set(credentials.values())) != 4:
    credentials = {role: secrets.token_urlsafe(32) for role in roles}

from app.db import Session
from app.accounts import ensure_seed_accounts
with Session() as db:
    try:
        changed = ensure_seed_accounts(db, credentials)
        for role, value in credentials.items():
            set_key(str(env_file), role.upper() + '_PASSWORD', value)
        db.commit()
    except Exception:
        db.rollback()
        env_file.write_bytes(original)
        raise
print('Independent seed credentials synchronized; updated accounts: ' + ', '.join(changed or ['none']))
print('Read the corresponding *_PASSWORD in local .env. Old sessions require login again; no passwords printed.')
