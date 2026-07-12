#!/usr/bin/env python3
"""Import provider keys into a FreeLLMAPI dashboard.

Usage:
  python3 scripts/import-provider-keys.py \
    --base-url http://127.0.0.1:3001 \
    --login-file .dashboard-login \
    --keys-file .provider-keys.env

The keys file is a simple KEY=VALUE env file. Only keys that are present
and non-empty are imported. Use KEYSET_LABEL to tag imported entries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

PLATFORM_MAP = {
    "GOOGLE_API_KEY": ("google", "google"),
    "GROQ_API_KEY": ("groq", "groq"),
    "OPENROUTER_API_KEY": ("openrouter", "openrouter"),
    "CEREBRAS_API_KEY": ("cerebras", "cerebras"),
    "NVIDIA_API_KEY": ("nvidia", "nvidia"),
    "MISTRAL_API_KEY": ("mistral", "mistral"),
    "GITHUB_API_KEY": ("github", "github"),
    "GITHUB_TOKEN": ("github", "github"),
    "COHERE_API_KEY": ("cohere", "cohere"),
    "CLOUDFLARE_API_KEY": ("cloudflare", "cloudflare"),
    "ZHIPU_API_KEY": ("zhipu", "zhipu"),
    "OLLAMA_CLOUD_API_KEY": ("ollama", "ollama"),
    "HUGGINGFACE_API_KEY": ("huggingface", "huggingface"),
    "OPENCODE_API_KEY": ("opencode", "opencode"),
    "LLM7_API_KEY": ("llm7", "llm7"),
    "OVH_API_KEY": ("ovh", "ovh"),
}


def read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def request_json(url: str, method: str = "GET", headers: dict[str, str] | None = None, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        payload = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {e.reason} for {url}: {payload}") from e


def login(base_url: str, email: str, password: str) -> str:
    data = request_json(
        f"{base_url}/api/auth/login",
        method="POST",
        body={"email": email, "password": password},
    )
    token = data.get("token")
    if not token:
        raise RuntimeError("Dashboard login did not return a token")
    return token


def import_keys(base_url: str, token: str, env: dict[str, str], label_prefix: str, dry_run: bool = False) -> list[str]:
    added: list[str] = []
    headers = {"Authorization": f"Bearer {token}"}
    for env_name, (platform, short_name) in PLATFORM_MAP.items():
        value = env.get(env_name, "").strip()
        if not value:
            continue
        label = f"{label_prefix}:{short_name}" if label_prefix else short_name
        entry = {"platform": platform, "key": value, "label": label}
        if dry_run:
            added.append(f"{platform}:{label}")
            continue
        result = request_json(f"{base_url}/api/keys", method="POST", headers=headers, body=entry)
        added.append(f"{result.get('platform')}:{result.get('label')}:{result.get('id')}")
    return added


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="e.g. http://127.0.0.1:3001")
    parser.add_argument("--login-file", required=True, help="dashboard login file with EMAIL and PASSWORD")
    parser.add_argument("--keys-file", required=True, help="env file containing provider keys")
    parser.add_argument("--label-prefix", default=None, help="label prefix for imported keys")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    login_file = Path(args.login_file)
    keys_file = Path(args.keys_file)
    if not login_file.exists():
        raise SystemExit(f"Missing login file: {login_file}")
    if not keys_file.exists():
        raise SystemExit(f"Missing keys file: {keys_file}")

    login_env = read_env_file(login_file)
    email = login_env.get("EMAIL", "")
    password = login_env.get("PASSWORD", "")
    if not email or not password:
        raise SystemExit("login file must contain EMAIL and PASSWORD")

    token = login(args.base_url.rstrip("/"), email, password)
    keys_env = read_env_file(keys_file)
    label_prefix = args.label_prefix or keys_env.get("KEYSET_LABEL", "set1")
    imported = import_keys(args.base_url.rstrip("/"), token, keys_env, label_prefix, dry_run=args.dry_run)

    print(json.dumps({"base_url": args.base_url, "imported": imported}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
