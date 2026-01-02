# Instructions — Deterministic Dev Ports (Windows)

## Objective
Prevent automatic port switching, eliminate orphaned dev processes, and ensure deterministic frontend/backend ports during local development and testing.

Target:
- Frontend: **localhost:3000**
- Backend: **localhost:4000**

Claude Code must **fail fast** if ports are unavailable and must **never auto-switch ports**.

---

## Operating Rules (Hard Constraints)

1. **Ports are fixed**
   - Frontend MUST bind to `3000`
   - Backend MUST bind to `4000`
   - If either port is unavailable, STOP and report the blocking process

2. **No auto-increment or fallback ports**
   - Do NOT select alternate ports (3001, 4001, etc.)
   - Do NOT prompt interactively to change ports
   - Do NOT suppress `EADDRINUSE` errors

3. **Claude does NOT own long-running dev servers**
   - Claude may start servers for verification
   - Claude must NOT attempt graceful shutdown
   - Claude must NOT wait on interactive termination
   - Process termination must be explicit and forced

---

## Preflight: Port Ownership Enforcement (MANDATORY)

Before starting **any** dev server or test run, Claude Code MUST execute the following logic.

### Step 1 — Detect listeners
Check for active listeners on required ports:

- Port `3000`
- Port `4000`

Use Windows-native commands.

### Step 2 — If a port is in use
1. Identify the PID listening on the port
2. Identify the owning process
3. Force-kill the entire process tree
4. Re-check the port until it is free

Claude MUST log:
- Port number
- PID
- Process name
- Kill confirmation

### Step 3 — Abort on failure
If a port remains occupied after forced termination:
- STOP execution
- Report the blocking PID and process
- Do NOT continue

---

## Required Command Pattern (Windows)

Claude Code MUST use **forced process-tree termination**.

```powershell
# Find listeners
netstat -ano | findstr :3000
netstat -ano | findstr :4000

# Inspect process
tasklist /fi "pid eq <PID>"

# Kill entire tree
taskkill /PID <PID> /F /T
