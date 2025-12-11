# n8n-ops Entitlements System Specification  
This document defines the complete feature-flag, plan, and entitlement architecture for n8n-ops.  
All implementation is executed **in phases**, and each phase is designed to be independently buildable and testable by Claude Code.

Follow this exact process:

1. **I will instruct Claude:** “Implement Phase 1 from entitlements.md.”  
2. Claude must complete Phase 1 fully, including tests, and stop.  
3. When reviewed and accepted, I will instruct Claude: “Implement Phase 2 from entitlements.md.”  
4. Repeat until all phases are complete.

Claude must **never** jump ahead to future phases without explicit instruction.

---

# ============================================================
# PHASES (READ FIRST)
# ============================================================

There are **4 total phases**.

--------------------------------------------------------------------
## **PHASE 1 — Minimal Vertical Slice (MVP Entitlements Path)**
--------------------------------------------------------------------

### **Goal**
Create a fully functional vertical slice of the entitlements system that touches backend persistence, entitlement resolution, backend enforcement, and frontend gating, but only for **3 features**:

- `snapshots_enabled`
- `workflow_limits`
- `workflow_ci_cd`

This proves the architecture end-to-end without building everything at once.

---

### **What to Build**

#### **1. Persistence Entities**
Create persistent models + migrations for:

- Feature  
- Plan  
- PlanFeature (plan → feature mapping)  
- TenantPlan (tenant → plan assignment with entitlements version)

**NOT included yet:**
- TenantFeatureOverride  
- Audit tables  
- Agency features  
- Full feature catalog  

#### **2. Seed Data for Phase 1**
Insert:

##### Plans:
- `free`
- `pro`
- `enterprise`
- `agency` (placeholder, not used yet)

##### Features:
- `snapshots_enabled` (flag)
- `workflow_ci_cd` (flag)
- `workflow_limits` (limit)

##### Plan-feature mapping for Phase 1 ONLY:

**free:**
- `snapshots_enabled = true`
- `workflow_ci_cd = false`
- `workflow_limits = 10`

**pro:**
- `snapshots_enabled = true`
- `workflow_ci_cd = true`
- `workflow_limits = 200`

**enterprise:**  
(same as pro for now, differences come later)
- `snapshots_enabled = true`
- `workflow_ci_cd = true`
- `workflow_limits = 5000`

**agency:**  
- Seed same as pro for now (real mapping added in Phase 2)

#### **3. Entitlements Service**
Implement a centralized backend service that:

- Loads plan + plan-feature mappings for a tenant  
- Produces effective entitlements  
- Exposes:
  - `has_flag(feature_id)`  
  - `get_limit(feature_id)`  
- Uses entitlements version for cache invalidation

#### **4. Extend Context API**
Add entitlements info to the existing `/context` or `/me` endpoint:

- plan ID
- entitlements version
- features map with final values

#### **5. Backend Enforcement (Phase 1 features only)**
Implement enforcement for:

- `snapshots_enabled` → block snapshot operations if disabled  
- `workflow_ci_cd` → block CI/CD operations if disabled  
- `workflow_limits` → enforce workflow count limit

Use a reusable guard/middleware mechanism.

#### **6. Frontend Consumption**
Implement minimal frontend changes:

- Read entitlements from context
- Add a simple `useFeature(featureId)` hook or equivalent
- Gate UI that triggers:
  - Snapshots  
  - CI/CD actions  

#### **7. Tests**
Provide tests for:

- Entitlement composition  
- Enforcement of flags  
- Enforcement of `workflow_limits`  
- Context endpoint returning entitlements  

---

### **What NOT to Build in Phase 1**
- Full feature catalog  
- TenantFeatureOverride  
- Audit logs  
- Access logs  
- Advanced CI/CD approvals  
- Agency or enterprise-specific functionality  
- Admin UI  

Keep Phase 1 small, vertical, and clean.

---

### **Phase 1 Definition of Done**
- Querying entitlements for any tenant works.  
- Frontend can display/hide snapshot + CI/CD actions based on entitlements.  
- Backend correctly blocks operations that require Phase 1 features.  
- All tests pass.  
- No other features implemented yet.

====================================================================
## **PHASE 2 — Full Feature Catalog + Full Enforcement**
====================================================================

### **Goal**
Expand the vertical slice into the full entitlement architecture by adding the entire feature catalog, full plan mappings, and applying enforcement across the entire backend + frontend.

---

### **What to Build**

#### **1. Add Full Feature Catalog**
Add persistent features for:

### Environment
- `environment_basic`
- `environment_health`
- `environment_diff`
- `environment_limits` (limit)

### Workflows + CI/CD
- `workflow_read`
- `workflow_push`
- `workflow_dirty_check`
- `workflow_ci_cd` (already exists)
- `workflow_ci_cd_approval`
- `workflow_limits` (already exists)

### Snapshots
- `snapshots_enabled` (exists)
- `snapshots_auto`
- `snapshots_history` (limit)
- `snapshots_export`

### Observability
- `observability_basic`
- `observability_alerts`
- `observability_alerts_advanced`
- `observability_logs`
- `observability_limits` (limit)

### Security / RBAC / Governance
- `rbac_basic`
- `rbac_advanced`
- `audit_logs`
- `audit_export`

### Agency / Multi-Tenant
- `agency_enabled`
- `agency_client_management`
- `agency_whitelabel`
- `agency_client_limits` (limit)

### Enterprise
- `sso_saml`
- `support_priority`
- `data_residency`
- `enterprise_limits` (limit)

#### **2. Seed All Features**
Seed each feature with:
- ID
- Type (flag or limit)
- Status: active
- Default value (only if needed)

#### **3. Seed Full Plan → Feature Mappings**
Seed complete entitlements for:

### **Free**
- Basic workflows, basic snapshots (small history), minimal observability  
- No CI/CD  
- No advanced features  
- Low limits  

### **Pro**
- CI/CD  
- Snapshots export + auto  
- Environment diff  
- Alerts  
- RBAC basic  
- Moderate limits  

### **Agency**
- All Pro features  
- Multi-tenant client management  
- White label  
- RBAC advanced  
- Audit logs  
- Higher limits  

### **Enterprise**
- All Agency features  
- CI/CD approvals  
- Advanced alerts  
- Audit export  
- SSO  
- Priority support  
- Data residency  
- Highest or unlimited limits  

#### **4. Backend Enforcement**
Apply backend feature + limit enforcement to:

- Environment operations  
- Workflow operations  
- CI/CD operations  
- Snapshot operations  
- Observability operations  
- RBAC operations  
- Audit operations  
- Agency operations  

#### **5. Frontend Gating**
Add `<FeatureGate>` or equivalent to:

- Snapshots  
- CI/CD  
- Environment diff, health  
- Observability sections  
- Audit logs  
- Advanced RBAC  
- Agency section  
- Enterprise settings  

#### **6. Tests**
Add tests covering:

- All newly added features  
- Enforcement across all modules  
- Frontend gating logic  

---

### **Phase 2 Definition of Done**
- Entire feature catalog exists in DB.  
- All plans have full entitlements.  
- Backend fully enforces everything.  
- Frontend cleanly gates everything.  
- No tenant overrides or audit logging yet.

====================================================================
## **PHASE 3 — Tenant Overrides + Audit Logging**
====================================================================

### **Goal**
Enable per-tenant entitlement customization and add auditability.

---

### **What to Build**
#### **1. TenantFeatureOverride Entity**
Allow overriding values for any feature, per-tenant.

#### **2. Override Merge Logic**
Entitlements service must:

- Load base plan values  
- Apply overrides on top  
- Produce final merged effective entitlements  

#### **3. Audit Logging**
Implement logging for:

- Plan → feature value changes  
- Tenant → plan changes  
- Tenant feature overrides  
- Limit hits / access denials (at least for sensitive routes)

#### **4. Tests**
- Override precedence tests  
- Audit record creation tests  
- Access log creation for denials  

---

### **Phase 3 Definition of Done**
- Per-tenant customization works.
- All changes are auditable.
- Enforcement logs significant events.

====================================================================
## **PHASE 4 — Admin Management UI**
====================================================================

### **Goal**
Provide an admin interface to manage plans, features, overrides, and view audit logs.

---

### **What to Build**

#### **1. Admin Endpoints**
Backend endpoints for:

- Viewing the feature matrix  
- Editing plan→feature values  
- Editing tenant overrides  
- Viewing audit logs  

#### **2. Admin UI Pages**
- Feature Matrix  
- Tenant Override Management  
- Audit Log Viewer  

#### **3. Tests**
- Admin endpoints  
- Permission handling  
- UI behaviors  

---

### **Phase 4 Definition of Done**
- Admins can modify entitlements without touching the database manually.  
- Audit trails are accessible from the UI.  


====================================================================
# CORE ARCHITECTURE SPECIFICATION (USED BY ALL PHASES)
====================================================================

## 1. Domain Concepts (Persistent)
- Feature  
- Plan  
- PlanFeature  
- TenantPlan  
- TenantFeatureOverride (Phase 3)  
- FeatureConfigAudit (Phase 3)  
- FeatureAccessLog (Phase 3)

## 2. Entitlements Service Responsibilities
- Load feature definitions  
- Load plan mappings  
- Load tenant overrides  
- Merge into effective entitlements  
- Cache on entitlements version  
- Expose helpers for flag + limit checking  

## 3. Context API Requirements
Must return:
- Tenant plan ID  
- Entitlements version  
- Final map of effective entitlements  

## 4. Enforcement Requirements
- Backend is **source of truth**  
- All sensitive actions must call entitlement checks  
- UI gating is only for UX  

## 5. Feature Catalog  
(Full list from the earlier section — unchanged)

## 6. Plan Seed Matrix  
(Full Free/Pro/Agency/Enterprise definitions — unchanged)

