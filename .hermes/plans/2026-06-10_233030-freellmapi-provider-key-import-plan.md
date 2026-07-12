# FreeLLMAPI Provider-Key Import and Verification Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Safely import provider keys into the Mac and OptiPlex FreeLLMAPI instances, verify the local-only dashboard and `/v1` proxy wiring on each host, and establish a clean path for mirrored first batches plus future one-device-only key batches.

**Architecture:** Keep each host fully isolated: one Dockerized FreeLLMAPI instance on the Mac and one on the OptiPlex, each with its own `.env`, dashboard login, and SQLite data volume. Use host-local env files for provider keys so the same first batch can be mirrored on both machines now, while future batches can be restricted to a single host. Hermes should keep using the host-local FreeLLMAPI unified API key, never the dashboard password, and verification should stay local to each machine (`127.0.0.1:3001`) unless an explicit remote check is needed.

**Tech Stack:** Docker Compose, FreeLLMAPI dashboard/admin API, Hermes CLI profiles (`mac-local`, `server-free`), Python 3 for import helpers, `curl`, local SQLite-backed FreeLLMAPI DB, host-local `.env` files.

---

## Current State / Assumptions

- Both hosts already have separate FreeLLMAPI repos and containers.
- Dashboard auth has already been rotated and is stored in each host’s local `.dashboard-login` file.
- The import helper exists or will be reused at:
  - `~/freellmapi/scripts/import-provider-keys.py`
  - `/opt/freellmapi/scripts/import-provider-keys.py`
- The provider-key file is host-local and private:
  - `~/freellmapi/.provider-keys.env`
  - `/opt/freellmapi/.provider-keys.env`
- The first key batch will be mirrored to both hosts.
- A later batch may be one-device-only and should not be mirrored.

---

## Proposed Approach

1. Treat the provider-key batch as a local import artifact, not a shell variable or global secret.
2. Use the import helper to POST keys into each host’s FreeLLMAPI dashboard/API.
3. Verify success locally on the same host using only localhost endpoints.
4. Label imports with a batch tag such as `set1` so future batches can be distinguished.
5. Keep future one-device batches in a separate file and import them only on the intended host.

---

## Step-by-Step Plan

### Task 1: Finalize the host-local import contract

**Objective:** Make sure the import inputs, labels, and verification targets are unambiguous before any key import happens.

**Files:**
- Inspect: `~/freellmapi/scripts/import-provider-keys.py`
- Inspect: `/opt/freellmapi/scripts/import-provider-keys.py`
- Inspect: `~/freellmapi/.dashboard-login`
- Inspect: `/opt/freellmapi/.dashboard-login`
- Inspect: `~/freellmapi/.provider-keys.env`
- Inspect: `/opt/freellmapi/.provider-keys.env`

**Checklist:**
- Confirm the dashboard login file is separate from the unified API key.
- Confirm the import helper reads a host-local env file and uses the dashboard login to authenticate.
- Confirm the batch label defaults to `KEYSET_LABEL` from the env file and can be overridden on the CLI.
- Confirm both hosts stay isolated and continue using local-only base URLs.

**Validation:**
- `curl -s http://127.0.0.1:3001/api/auth/status`
- `docker compose ps`
- `freellmapi-import --help`

---

### Task 2: Prepare the mirrored first key batch (`set1`)

**Objective:** Put the same provider keys into both host-local env files so the first import can be mirrored.

**Files:**
- Modify: `~/freellmapi/.provider-keys.env`
- Modify: `/opt/freellmapi/.provider-keys.env`

**Contents:**
```bash
KEYSET_LABEL=set1
GOOGLE_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=
CEREBRAS_API_KEY=
NVIDIA_API_KEY=
MISTRAL_API_KEY=
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

**Rules:**
- Fill only the providers you actually intend to use.
- Keep the file `chmod 600`.
- Do not paste keys directly into shell commands.

**Validation:**
- `chmod 600 .provider-keys.env`
- `python3 - <<'PY' ...` to parse the file locally without printing secret values

---

### Task 3: Dry-run the import locally on each host

**Objective:** Verify the script sees the right keys and target host before any database changes.

**Files:**
- Run against: `~/freellmapi`
- Run against: `/opt/freellmapi`

**Commands:**
```bash
cd ~/freellmapi
freellmapi-import --base-url http://127.0.0.1:3001 --login-file .dashboard-login --keys-file .provider-keys.env --dry-run
```

```bash
ssh ja@100.89.164.94 'cd /opt/freellmapi && freellmapi-import --base-url http://127.0.0.1:3001 --login-file .dashboard-login --keys-file .provider-keys.env --dry-run'
```

**Expected:**
- JSON output listing only the platforms present in the env file.
- No secret values printed.
- No DB mutation.

---

### Task 4: Import the mirrored batch on the Mac

**Objective:** Add the first provider batch to the Mac FreeLLMAPI dashboard and confirm it persists.

**Files:**
- Use: `~/freellmapi/scripts/import-provider-keys.py`
- Verify: Mac Docker volume and local dashboard state

**Command:**
```bash
cd ~/freellmapi
freellmapi-import --base-url http://127.0.0.1:3001 --login-file .dashboard-login --keys-file .provider-keys.env
```

**Validation:**
- `curl -s http://127.0.0.1:3001/api/auth/status`
- `curl -s -H "Authorization: Bearer <unified-key>" http://127.0.0.1:3001/v1/models`
- Open the local dashboard and confirm the imported provider rows appear with `set1:*` labels.
- Verify Hermes still points at the Mac local endpoint via the `mac-local` profile.

---

### Task 5: Import the mirrored batch on the OptiPlex

**Objective:** Add the same provider batch to the OptiPlex FreeLLMAPI dashboard and confirm the remote host remains isolated.

**Files:**
- Use: `/opt/freellmapi/scripts/import-provider-keys.py`
- Verify: OptiPlex Docker volume and local dashboard state

**Command:**
```bash
ssh ja@100.89.164.94 'cd /opt/freellmapi && freellmapi-import --base-url http://127.0.0.1:3001 --login-file .dashboard-login --keys-file .provider-keys.env'
```

**Validation:**
- `ssh ja@100.89.164.94 'cd /opt/freellmapi && curl -s http://127.0.0.1:3001/api/auth/status'`
- `ssh ja@100.89.164.94 'cd /opt/freellmapi && docker compose ps'`
- Confirm the OptiPlex dashboard shows the same `set1:*` labels.
- Verify Hermes `server-free` still uses the OptiPlex-local FreeLLMAPI endpoint.

---

### Task 6: Verify Hermes routing against each local host

**Objective:** Prove Hermes can talk to each FreeLLMAPI instance using the host-local unified key.

**Files:**
- Inspect: `~/.hermes/profiles/mac-local/config.yaml`
- Inspect: `~/.hermes/profiles/server-free/config.yaml`

**Commands:**
```bash
hermes -p mac-local chat -q "Reply with exactly one word: ready"
hermes -p server-free chat -q "Reply with exactly one word: ready"
```

**Expected:**
- Both commands complete successfully.
- No credential prompts.
- No routing errors like `All models exhausted` or `Invalid API key`.

---

### Task 7: Prepare the future one-device-only batch workflow

**Objective:** Establish a clean pattern for the later batch that should go to only one host.

**Files:**
- Create: `~/freellmapi/.provider-keys.set2.env`
- Create: `/opt/freellmapi/.provider-keys.set2.env` only if that host should also receive it
- Update documentation if needed: `~/freellmapi/.provider-keys.env.example`

**Rules:**
- Use `KEYSET_LABEL=set2`.
- Keep the file separate from `set1`.
- Do not mirror it automatically unless that is explicitly desired later.
- Import it only on the intended host.

**Validation:**
- Dry-run on the intended host only.
- Confirm the dashboard labels clearly distinguish `set2` from `set1`.

---

### Task 8: Document the final operating procedure

**Objective:** Make the process repeatable so future key rotations do not require rediscovery.

**Files likely to change:**
- `~/freellmapi/.provider-keys.env.example`
- `~/freellmapi/scripts/import-provider-keys.py`
- `~/freellmapi/scripts/rotate-dashboard-login.py`
- Optional notes under `~/freellmapi/.hermes/plans/`

**Document:**
- Dashboard login is local and separate from the unified API key.
- Provider keys live in host-local env files.
- `set1` is mirrored across both hosts.
- `set2` (or later) may be host-specific.
- Verification is always local to the host first.

**Validation:**
- The next person should be able to follow the document without asking for hidden context.

---

## Tests / Validation

Run these after each import or password rotation:

```bash
# Local auth state
curl -s http://127.0.0.1:3001/api/auth/status

# Container health
cd ~/freellmapi && docker compose ps

# Dashboard login works locally
python3 - <<'PY'
# POST saved .dashboard-login creds to /api/auth/login and print the token response
PY

# Proxy works
curl -s -H "Authorization: Bearer <unified-key>" http://127.0.0.1:3001/v1/models
```

For the OptiPlex, run the same checks through SSH with `http://127.0.0.1:3001` from inside the remote host.

---

## Risks / Tradeoffs / Open Questions

- **Mirrored keys couple quota and revocation**: the same provider key set on both hosts is convenient now, but if a key is rate-limited or revoked, both hosts are affected.
- **Dashboard login is not the same as the unified API key**: confusion here causes the most failures.
- **Lockout behavior is in-memory**: repeated bad logins can trigger a temporary lockout, but restarting the container clears it.
- **Local-only verification is safest**: avoid exposing the dashboard broadly while importing or testing.
- **Future one-device batches need explicit handling**: they should use separate files and a deliberate host selection.

---

## Definition of Done

- Mirrored `set1` provider keys are imported on both hosts.
- Both dashboards show the imported keys with clear labels.
- Both Hermes profiles can chat successfully through their host-local FreeLLMAPI instance.
- A separate future batch path is documented for one-device-only imports.
- All secrets remain host-local and are not printed in logs or chat.
