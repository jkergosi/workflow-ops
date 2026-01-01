# Workflow Ops — Pro vs Agency Boundary Test

## Purpose
Ensure Pro and Agency remain distinct, with no feature cannibalization.

---

## Pro Must Always Feel Like
- Individual safety
- Undo capability
- Confidence to change

## Agency Must Always Feel Like
- Shared responsibility
- Risk governance
- Repeatable delivery

---

## Boundary Rules

| Capability | Pro | Agency |
|----------|-----|--------|
| Snapshots | ✅ | ✅ |
| Restore | ✅ | ✅ |
| Manual Promotion | ✅ | ✅ |
| Pipelines | ❌ | ✅ |
| Approvals | ❌ | ✅ |
| Drift Incidents | ❌ | ✅ |
| Multi-env governance | ❌ | ✅ |

---

## Red Flags (Cannibalization Indicators)
- Pro users asking for approvals
- Pro users confused by drift incidents
- Agency users not needing pipelines

If any occur, exposure boundaries have slipped.

---

## Golden Rule
If it protects *me*, it’s Pro.
If it protects *others*, it’s Agency.
