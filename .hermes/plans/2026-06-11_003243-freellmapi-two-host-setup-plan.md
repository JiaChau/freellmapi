# FreeLLMAPI + Hermes Two-Host Setup Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Fully set up two isolated FreeLLMAPI instances (Mac and OptiPlex), wire Hermes profiles to each host-local proxy, and establish a repeatable, secure provider-key import workflow that can be run once for mirrored keys or later for a one-device-only batch.

**Architecture:**
Use one Dockerized FreeLLMAPI instance per host, with host-local data volumes and host-local `.env` files so the Mac and OptiPlex never point to each other. Keep dashboard auth separate from the unified `/v1` bearer key, and keep provider keys in the FreeLLMAPI dashboard only. Hermes should use profile-local `model.*` config and point each profile at the local host’s `http://127.0.0.1:3001/v1` endpoint (or the OptiPlex Tailscale/LAN address only when remote access is explicitly desired).

**Tech Stack:**
Docker Compose, FreeLLMAPI, Hermes CLI, SQLite-backed FreeLLMAPI state, host-local shell scripts, `curl`, `python3`, and per-host Hermes profiles.

---

## Required user inputs before execution

Collect these before any implementation begins:

1. **Provider key set(s)**
   - Which providers should be imported now?
   - Which ones are mirrored to both hosts vs. reserved for a future one-device-only batch?
   - Confirm the `KEYSET_LABEL` to use for the first batch (default: `set1`).

2. **Host access preference**
   - Do you want the OptiPlex dashboard accessed only locally on the host, or via SSH tunnel/Tailscale from the Mac?
   - If remote access is desired, confirm the preferred secure path.

3. **Hermes profile names**
   - Confirm whether to keep `mac-local` and `server-free`, or rename them.
   - Confirm the desired default profile on each machine.

4. **Dashboard identity policy**
   - Confirm whether both hosts should use the same dashboard email or separate dashboard emails.
   - Confirm whether password rotation should be repeated after setup.

5. **Verification scope**
   - Which smoke tests must pass before you consider setup complete?
   - At minimum: dashboard login, provider import, `/v1/models`, Hermes `chat -q`, and profile config sanity.

---

## Step-by-step plan

### Task 1: Freeze the baseline and confirm host-local topology

**Objective:** Verify both FreeLLMAPI stacks are up, local-only, and ready for a controlled setup pass.

**Files:**
- Inspect only (no edits):
  - `~/freellmapi/docker-compose.yml`
  - `~/freellmapi/.env`
  - `~/freellmapi/.dashboard-login`
  - `/opt/freellmapi/docker-compose.yml`
  - `/opt/freellmapi/.env`
  - `/opt/freellmapi/.dashboard-login`
  - `~/.hermes/profiles/mac-local/config.yaml`
  - `~/.hermes/profiles/server-free/config.yaml`

**Step 1: Verify container status on both hosts**

Run locally on each host:
```bash
cd ~/freellmapi && docker compose ps
```
And on the OptiPlex:
```bash
ssh ja@100.89.164.94 'cd /opt/freellmapi && docker compose ps'
```
Expected: one running `freellmapi` container on each host, bound to the intended local port mapping.

**Step 2: Verify dashboard auth status locally**

Run on each host:
```bash
curl -s http://127.0.0.1:3001/api/auth/status
```
Expected: JSON response with `needsSetup` and no accidental authenticated session.

**Step 3: Verify Hermes profile endpoints**

Run:
```bash
hermes -p mac-local config get model.base_url
hermes -p server-free config get model.base_url
```
Expected: Mac profile points to the Mac FreeLLMAPI endpoint; server profile points to the OptiPlex endpoint or the intended remote-access address.

---

### Task 2: Confirm and standardize dashboard credentials

**Objective:** Ensure both hosts have a known dashboard login and a repeatable recovery path.

**Files:**
- Create/modify:
  - `~/freellmapi/.dashboard-login`
  - `/opt/freellmapi/.dashboard-login`
  - `~/freellmapi/scripts/rotate-dashboard-login.py`
  - `/opt/freellmapi/scripts/rotate-dashboard-login.py`

**Step 1: Decide the login policy**

Choose one:
- same email/password on both hosts
- same email, different password per host
- different email/password per host

Record the decision before touching credentials.

**Step 2: Rotate login on the Mac host**

Run locally after confirming the desired login policy:
```bash
cd ~/freellmapi
./scripts/rotate-dashboard-login.py --generate
```
Expected: script rewrites `.dashboard-login`, resets the dashboard DB account, and clears stale sessions.

**Step 3: Mirror or rotate on the OptiPlex**

Run remotely:
```bash
ssh ja@100.89.164.94 'cd /opt/freellmapi && ./scripts/rotate-dashboard-login.py --generate'
```
Expected: same effect on the OptiPlex dashboard DB and login file.

**Step 4: Verify login locally on each host**

Run:
```bash
python3 - <<'PY'
from pathlib import Path
import json, urllib.request
login = {}
for line in Path('.dashboard-login').read_text().splitlines():
    if '=' in line:
        k,v=line.split('=',1)
        login[k]=v
req = urllib.request.Request('http://127.0.0.1:3001/api/auth/login', data=json.dumps({'email': login['EMAIL'], 'password': login['PASSWORD']}).encode(), headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=10) as r:
    print(r.read().decode())
PY
```
Expected: JSON containing a session token and the dashboard email.

---

### Task 3: Prepare the provider-key import workflow

**Objective:** Make provider-key import repeatable, local-only, and safe for both mirrored and one-device-only batches.

**Files:**
- Create/modify:
  - `~/freellmapi/.provider-keys.env`
  - `~/freellmapi/.provider-keys.env.example`
  - `~/freellmapi/scripts/import-provider-keys.py`
  - `/opt/freellmapi/.provider-keys.env`
  - `/opt/freellmapi/.provider-keys.env.example`
  - `/opt/freellmapi/scripts/import-provider-keys.py`

**Step 1: Fill in the host-local env template**

Use one env file per host. Put only the providers you want on that host.

Template:
```env
KEYSET_LABEL=set1
GOOGLE_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
GITHUB_API_KEY=
COHERE_API_KEY=
CLOUDFLARE_API_KEY=
ZHIPU_API_KEY=
OLLAMA_CLOUD_API_KEY=
HUGGINGFACE_API_KEY=
OPENCODE_API_KEY=
LLM7_API_KEY=
OVH_API_KEY=
```

**Step 2: Dry-run the import helper**

Run on each host:
```bash
cd ~/freellmapi
freellmapi-import --base-url http://127.0.0.1:3001 --login-file .dashboard-login --keys-file .provider-keys.env --dry-run
```
Expected: JSON with a preview list only; no keys imported.

**Step 3: Import the keys for real**

Run on the intended host only:
```bash
freellmapi-import --base-url http://127.0.0.1:3001 --login-file .dashboard-login --keys-file .provider-keys.env
```
Expected: JSON showing imported provider rows and labels.

**Step 4: Verify the dashboard rows locally**

Open the local dashboard and confirm the **Keys** page shows the imported providers with labels like `set1:<provider>`.

---

### Task 4: Bind Hermes profiles to the correct host-local proxy

**Objective:** Ensure Hermes uses `model.*` config for each host and does not cross-point the instances.

**Files:**
- Modify:
  - `~/.hermes/profiles/mac-local/config.yaml`
  - `~/.hermes/profiles/server-free/config.yaml`

**Step 1: Confirm the Mac profile points to the Mac proxy**

Target values:
```yaml
model:
  provider: custom:freellmapi
  base_url: http://127.0.0.1:3001/v1
  default: auto
```

**Step 2: Confirm the OptiPlex profile points to the OptiPlex proxy**

Target values:
```yaml
model:
  provider: custom:freellmapi
  base_url: http://127.0.0.1:3001/v1
  default: auto
```

Use the host-local address on the host where Hermes runs; if the profile is used from a different machine, swap to the remote host’s IP/Tailscale address intentionally and verify that decision first.

**Step 3: Verify the active profile wiring**

Run:
```bash
hermes -p mac-local config get model.base_url
hermes -p server-free config get model.base_url
```
Expected: each profile returns the intended base URL for its host.

---

### Task 5: Smoke-test the model proxy and Hermes end-to-end

**Objective:** Prove the local proxy and Hermes profile can complete a chat round-trip.

**Files:**
- No new files expected unless a verification note is added.

**Step 1: Verify `/v1/models` with the unified API key**

Run locally on each host:
```bash
curl -s -H "Authorization: Bearer <unified-key>" http://127.0.0.1:3001/v1/models
```
Expected: JSON model list, not `authentication_error`.

**Step 2: Run a one-word Hermes chat smoke test**

Run:
```bash
hermes -p mac-local chat -q "Reply with exactly one word: ready"
```
Expected: successful completion with a short reply.

**Step 3: Repeat on the other host/profile**

Run the same smoke test using the server profile.

**Step 4: Record pass/fail results**

If either test fails, stop and fix the proxy or profile before proceeding.

---

### Task 6: Document the final setup and recovery steps

**Objective:** Leave behind a durable setup note the user can follow next time without rediscovery.

**Files:**
- Create:
  - `~/freellmapi/SETUP-NOTES.md` or a repo-local runbook if one does not already exist
  - optionally `~/.hermes/plans/` follow-up notes if execution is split

**Step 1: Write recovery and rotation instructions**

Include:
- how to rotate dashboard auth
- how to rotate the unified API key
- how to re-import provider keys
- how to verify the local host only
- what not to share between hosts

**Step 2: Add a concise “break-glass” section**

Include the minimum commands needed to recover from lockout without exposing secrets.

---

## Tests / validation

Minimum validation gates:

1. `docker compose ps` shows the container healthy on both hosts.
2. `curl http://127.0.0.1:3001/api/auth/status` returns a sane dashboard state.
3. Dashboard login works with the rotated credentials.
4. Provider-key dry-run shows the intended import set.
5. Provider-key real import shows the expected rows in the Keys page.
6. `curl -H 'Authorization: Bearer <unified-key>' http://127.0.0.1:3001/v1/models` returns model data.
7. `hermes -p mac-local chat -q "Reply with exactly one word: ready"` passes.
8. `hermes -p server-free chat -q "Reply with exactly one word: ready"` passes.

---

## Risks, tradeoffs, and open questions

- **Lockout risk:** the dashboard has an in-memory throttle; repeated bad logins can lock the email temporarily.
- **Secret sprawl:** storing provider keys in plaintext env files is acceptable only if the files stay local, `chmod 600`, and out of backups/sync.
- **Quota coupling:** mirroring the same upstream keys to both hosts is convenient for comparison but couples quota usage and revocation across both machines.
- **Remote-access confusion:** the dashboard password is not the same as the unified `/v1` API key.
- **Host routing drift:** the most common operator error is pointing Hermes at the wrong host-local proxy or mixing dashboard credentials with proxy credentials.

**Open questions to resolve before execution:**
- Which providers are in the first batch?
- Which providers are reserved for one-device-only later?
- What exact dashboard identity policy do you want?
- Should the OptiPlex dashboard stay local-only or be reachable over SSH/Tailscale?

---

## Execution rule

Do not start implementation until the user provides the required inputs above. Once they do, execute one task at a time with subagent-driven-development: spec review first, then code review, then verify locally on the host before moving on.
