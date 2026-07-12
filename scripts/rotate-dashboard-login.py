#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

JS = r"""
const Database = require('better-sqlite3');
const crypto = require('crypto');
const email = process.env.EMAIL;
const password = process.env.PASSWORD;
if (!email || !password) {
  console.error('Missing EMAIL or PASSWORD');
  process.exit(1);
}
const salt = crypto.randomBytes(16);
const hash = crypto.scryptSync(password, salt, 64);
const stored = `scrypt$${salt.toString('hex')}$${hash.toString('hex')}`;
const db = new Database('/app/server/data/freeapi.db');
db.pragma('foreign_keys = ON');
const tx = db.transaction(() => {
  db.prepare('DELETE FROM sessions').run();
  db.prepare('DELETE FROM users').run();
  db.prepare('INSERT INTO users (email, password_hash) VALUES (?, ?)').run(email, stored);
});
tx();
console.log(JSON.stringify({ email, rotated: true }));
""".strip()


def read_login(path: Path) -> tuple[str, str]:
    data: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        if '=' not in raw:
            continue
        key, value = raw.split('=', 1)
        data[key.strip()] = value.strip()
    email = data.get('EMAIL', '').strip()
    password = data.get('PASSWORD', '').strip()
    if not email or not password:
        raise SystemExit(f'{path} must contain EMAIL and PASSWORD')
    return email, password


def write_login(path: Path, email: str, password: str) -> None:
    path.write_text(f'EMAIL={email}\nPASSWORD={password}\n')
    os.chmod(path, 0o600)


def rotate_db(repo: Path, email: str, password: str) -> str:
    result = subprocess.run(
        [
            'docker', 'compose', 'exec', '-T',
            '-e', f'EMAIL={email}',
            '-e', f'PASSWORD={password}',
            'freellmapi',
            'node', '-e', JS,
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description='Rotate FreeLLMAPI dashboard login and DB account')
    parser.add_argument('--email', default='freellmapi-admin@example.com')
    parser.add_argument('--login-file', default='.dashboard-login')
    parser.add_argument('--generate', action='store_true', help='Generate a new password and overwrite the login file')
    args = parser.parse_args()

    repo = Path.cwd()
    login_path = repo / args.login_file

    if args.generate or not login_path.exists():
        password = secrets.token_urlsafe(24)
        write_login(login_path, args.email, password)
    else:
        args.email, password = read_login(login_path)

    login_email, login_password = read_login(login_path)
    out = rotate_db(repo, login_email, login_password)
    print(json.dumps({
        'email': login_email,
        'login_file': str(login_path),
        'rotated': True,
        'db_result': json.loads(out) if out else None,
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
