from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List, Dict, Any
import logging
from functools import wraps

from app.services.database import db_service
from app.services.provider_registry import ProviderRegistry
from app.api.endpoints.admin_audit import create_audit_log, AuditActionType
from app.schemas.credential import (
    LogicalCredentialCreate,
    LogicalCredentialResponse,
    CredentialMappingCreate,
    CredentialMappingUpdate,
    CredentialMappingResponse,
    CredentialPreflightRequest,
    CredentialPreflightResult,
    CredentialIssue,
    ResolvedMapping,
    CredentialDetail,
    WorkflowCredentialDependencyResponse,
    DiscoveredCredential,
    CredentialMatrixResponse,
    MappingValidationReport,
    MappingIssue,
)
from app.api.endpoints.auth import get_current_user
from app.core.platform_admin import require_platform_admin

router = APIRouter()
logger = logging.getLogger(__name__)


def handle_db_errors(func):
    """Decorator to handle database errors and provide helpful messages for missing tables."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            # Check for missing table errors (Supabase/PostgreSQL)
            if "relation" in error_str and "does not exist" in error_str:
                missing_table = "credential management"
                if "logical_credentials" in error_str:
                    missing_table = "logical_credentials"
                elif "credential_mappings" in error_str:
                    missing_table = "credential_mappings"
                elif "workflow_credential_dependencies" in error_str:
                    missing_table = "workflow_credential_dependencies"

                logger.error(f"Database table missing: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database table '{missing_table}' not found. Please run the migration: migrations/create_credential_tables.sql"
                )
            # Re-raise other exceptions
            raise
    return wrapper


def get_current_tenant_id(user_info: dict) -> str:
    tenant = user_info.get("tenant") if user_info else None
    if tenant and tenant.get("id"):
        return tenant.get("id")
    return "00000000-0000-0000-0000-000000000000"


@router.get("/logical", response_model=list[LogicalCredentialResponse])
@handle_db_errors
async def list_logical_credentials(user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    return await db_service.list_logical_credentials(tenant_id)


@router.post("/logical", response_model=LogicalCredentialResponse, status_code=status.HTTP_201_CREATED)
async def create_logical_credential(body: LogicalCredentialCreate, user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    user = user_info.get("user", {})
    data = body.model_dump()
    data["tenant_id"] = tenant_id
    created = await db_service.create_logical_credential(data)
    
    await create_audit_log(
        action_type=AuditActionType.LOGICAL_CREDENTIAL_CREATED,
        action=f"Created logical credential '{created.get('name')}'",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        actor_name=user.get("name"),
        tenant_id=tenant_id,
        resource_type="logical_credential",
        resource_id=created.get("id"),
        resource_name=created.get("name"),
        new_value={"name": created.get("name"), "required_type": created.get("required_type")}
    )
    
    return created


@router.patch("/logical/{logical_id}", response_model=LogicalCredentialResponse)
async def update_logical_credential(logical_id: str, body: LogicalCredentialCreate, user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    user = user_info.get("user", {})
    
    existing = await db_service.get_logical_credential(tenant_id, logical_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logical credential not found")
    
    updated = await db_service.update_logical_credential(tenant_id, logical_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logical credential not found")
    
    await create_audit_log(
        action_type=AuditActionType.LOGICAL_CREDENTIAL_UPDATED,
        action=f"Updated logical credential '{updated.get('name')}'",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        actor_name=user.get("name"),
        tenant_id=tenant_id,
        resource_type="logical_credential",
        resource_id=logical_id,
        resource_name=updated.get("name"),
        old_value={"name": existing.get("name"), "required_type": existing.get("required_type")},
        new_value={"name": updated.get("name"), "required_type": updated.get("required_type")}
    )
    
    return updated


@router.delete("/logical/{logical_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_logical_credential(logical_id: str, user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    user = user_info.get("user", {})
    
    existing = await db_service.get_logical_credential(tenant_id, logical_id)
    credential_name = existing.get("name") if existing else logical_id
    
    await db_service.delete_logical_credential(tenant_id, logical_id)
    
    await create_audit_log(
        action_type=AuditActionType.LOGICAL_CREDENTIAL_DELETED,
        action=f"Deleted logical credential '{credential_name}'",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        actor_name=user.get("name"),
        tenant_id=tenant_id,
        resource_type="logical_credential",
        resource_id=logical_id,
        resource_name=credential_name,
        old_value={"name": existing.get("name"), "required_type": existing.get("required_type")} if existing else None
    )
    
    return {}


@router.get("/mappings", response_model=list[CredentialMappingResponse])
@handle_db_errors
async def list_mappings(environment_id: Optional[str] = None, provider: Optional[str] = None, user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    return await db_service.list_credential_mappings(tenant_id, environment_id=environment_id, provider=provider)


@router.post("/mappings", response_model=CredentialMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(body: CredentialMappingCreate, user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    user = user_info.get("user", {})
    data = body.model_dump()
    data["tenant_id"] = tenant_id
    created = await db_service.create_credential_mapping(data)
    
    logical_cred = await db_service.get_logical_credential(tenant_id, created.get("logical_credential_id"))
    env = await db_service.get_environment(created.get("environment_id"), tenant_id)
    
    await create_audit_log(
        action_type=AuditActionType.CREDENTIAL_MAPPING_CREATED,
        action=f"Created credential mapping for '{logical_cred.get('name') if logical_cred else 'unknown'}' in {env.get('n8n_name') if env else 'unknown'}",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        actor_name=user.get("name"),
        tenant_id=tenant_id,
        resource_type="credential_mapping",
        resource_id=created.get("id"),
        resource_name=f"{logical_cred.get('name') if logical_cred else 'unknown'} -> {created.get('physical_name')}",
        provider=created.get("provider"),
        new_value={
            "logical_credential_id": created.get("logical_credential_id"),
            "environment_id": created.get("environment_id"),
            "physical_name": created.get("physical_name"),
            "physical_type": created.get("physical_type")
        }
    )
    
    return created


@router.post("/mappings/validate", response_model=MappingValidationReport)
@handle_db_errors
async def validate_credential_mappings(
    environment_id: Optional[str] = Query(None, description="Filter by environment ID"),
    user_info: dict = Depends(require_platform_admin())
):
    """Validate that all credential mappings still resolve to valid N8N credentials."""
    tenant_id = get_current_tenant_id(user_info)

    mappings = await db_service.list_credential_mappings(tenant_id, environment_id=environment_id)
    logical_creds = await db_service.list_logical_credentials(tenant_id)
    environments = await db_service.get_environments(tenant_id)

    logical_by_id = {lc.get("id"): lc for lc in logical_creds}
    env_by_id = {e.get("id"): e for e in environments}

    env_credentials_cache: Dict[str, Dict[str, Any]] = {}

    total = len(mappings)
    valid_count = 0
    invalid_count = 0
    stale_count = 0
    issues: List[MappingIssue] = []

    for mapping in mappings:
        mapping_id = mapping.get("id")
        env_id = mapping.get("environment_id")
        logical_id = mapping.get("logical_credential_id")
        physical_id = mapping.get("physical_credential_id")

        logical = logical_by_id.get(logical_id, {})
        env = env_by_id.get(env_id, {})
        logical_name = logical.get("name", logical_id)
        env_name = env.get("n8n_name", env_id)

        if env_id not in env_credentials_cache:
            try:
                adapter = ProviderRegistry.get_adapter_for_environment(env)
                creds = await adapter.get_credentials()
                env_credentials_cache[env_id] = {c.get("id"): c for c in creds}
            except Exception as e:
                logger.warning(f"Failed to fetch credentials for env {env_id}: {e}")
                env_credentials_cache[env_id] = {}

        n8n_creds = env_credentials_cache.get(env_id, {})
        n8n_cred = n8n_creds.get(physical_id)

        new_status = mapping.get("status", "valid")
        issue_type = None
        issue_msg = None

        if not n8n_cred:
            new_status = "invalid"
            issue_type = "credential_not_found"
            issue_msg = f"Physical credential '{physical_id}' not found in N8N"
            invalid_count += 1
        else:
            expected_name = mapping.get("physical_name")
            actual_name = n8n_cred.get("name")
            if expected_name and actual_name and expected_name != actual_name:
                new_status = "stale"
                issue_type = "name_changed"
                issue_msg = f"Credential name changed from '{expected_name}' to '{actual_name}'"
                stale_count += 1
            else:
                new_status = "valid"
                valid_count += 1

        if mapping.get("status") != new_status:
            await db_service.update_credential_mapping(tenant_id, mapping_id, {"status": new_status})

        if issue_type:
            issues.append(MappingIssue(
                mapping_id=mapping_id,
                logical_name=logical_name,
                environment_id=env_id,
                environment_name=env_name,
                issue=issue_type,
                message=issue_msg,
            ))

    return MappingValidationReport(
        total=total,
        valid=valid_count,
        invalid=invalid_count,
        stale=stale_count,
        issues=issues,
    )


@router.patch("/mappings/{mapping_id}", response_model=CredentialMappingResponse)
async def update_mapping(mapping_id: str, body: CredentialMappingUpdate, user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    user = user_info.get("user", {})
    
    existing = await db_service.get_credential_mapping(tenant_id, mapping_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    
    updated = await db_service.update_credential_mapping(tenant_id, mapping_id, body.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    
    logical_cred = await db_service.get_logical_credential(tenant_id, updated.get("logical_credential_id"))
    env = await db_service.get_environment(updated.get("environment_id"), tenant_id)
    
    await create_audit_log(
        action_type=AuditActionType.CREDENTIAL_MAPPING_UPDATED,
        action=f"Updated credential mapping for '{logical_cred.get('name') if logical_cred else 'unknown'}' in {env.get('n8n_name') if env else 'unknown'}",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        actor_name=user.get("name"),
        tenant_id=tenant_id,
        resource_type="credential_mapping",
        resource_id=mapping_id,
        resource_name=f"{logical_cred.get('name') if logical_cred else 'unknown'} -> {updated.get('physical_name')}",
        provider=updated.get("provider"),
        old_value={
            "physical_name": existing.get("physical_name"),
            "physical_type": existing.get("physical_type"),
            "status": existing.get("status")
        },
        new_value={
            "physical_name": updated.get("physical_name"),
            "physical_type": updated.get("physical_type"),
            "status": updated.get("status")
        }
    )
    
    return updated


@router.delete("/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mapping(mapping_id: str, user_info: dict = Depends(require_platform_admin())):
    tenant_id = get_current_tenant_id(user_info)
    user = user_info.get("user", {})
    
    existing = await db_service.get_credential_mapping(tenant_id, mapping_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    
    logical_cred = await db_service.get_logical_credential(tenant_id, existing.get("logical_credential_id"))
    env = await db_service.get_environment(existing.get("environment_id"), tenant_id)
    
    await db_service.delete_credential_mapping(tenant_id, mapping_id)
    
    await create_audit_log(
        action_type=AuditActionType.CREDENTIAL_MAPPING_DELETED,
        action=f"Deleted credential mapping for '{logical_cred.get('name') if logical_cred else 'unknown'}' in {env.get('n8n_name') if env else 'unknown'}",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        actor_name=user.get("name"),
        tenant_id=tenant_id,
        resource_type="credential_mapping",
        resource_id=mapping_id,
        resource_name=f"{logical_cred.get('name') if logical_cred else 'unknown'} -> {existing.get('physical_name')}",
        provider=existing.get("provider"),
        old_value={
            "logical_credential_id": existing.get("logical_credential_id"),
            "environment_id": existing.get("environment_id"),
            "physical_name": existing.get("physical_name"),
            "physical_type": existing.get("physical_type")
        }
    )
    
    return {}


@router.post("/preflight", response_model=CredentialPreflightResult)
async def credential_preflight_check(
    body: CredentialPreflightRequest,
    user_info: dict = Depends(require_platform_admin())
):
    """
    Validate credential mappings for workflows before promotion.
    Returns blocking issues and resolved mappings.
    """
    tenant_id = get_current_tenant_id(user_info)

    blocking_issues: List[CredentialIssue] = []
    warnings: List[CredentialIssue] = []
    resolved_mappings: List[ResolvedMapping] = []

    # Get environment configs
    source_env = await db_service.get_environment(body.source_environment_id, tenant_id)
    target_env = await db_service.get_environment(body.target_environment_id, tenant_id)

    if not source_env:
        raise HTTPException(status_code=404, detail="Source environment not found")
    if not target_env:
        raise HTTPException(status_code=404, detail="Target environment not found")

    # Get target environment credentials
    try:
        target_adapter = ProviderRegistry.get_adapter_for_environment(target_env)
        target_credentials = await target_adapter.get_credentials()
        target_cred_map = {(c.get("type"), c.get("name")): c for c in target_credentials}
    except Exception as e:
        logger.error(f"Failed to fetch target credentials: {e}")
        target_cred_map = {}

    # Get GitHub service for source environment (fallback for workflow data)
    from app.services.github_service import GitHubService
    source_github = None
    source_env_type = source_env.get("n8n_type")
    if source_env.get("git_repo_url") and source_env.get("git_pat"):
        if not source_env_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Environment type is required for GitHub workflow operations. Set the environment type and try again.",
            )
        repo_url = source_env.get("git_repo_url", "").rstrip('/').replace('.git', '')
        repo_parts = repo_url.split("/")
        source_github = GitHubService(
            token=source_env.get("git_pat"),
            repo_owner=repo_parts[-2] if len(repo_parts) >= 2 else "",
            repo_name=repo_parts[-1] if len(repo_parts) >= 1 else "",
            branch=source_env.get("git_branch", "main"),
        )
    
    # Try to get all workflows from GitHub at once for efficiency
    github_workflows = {}
    if source_github and source_github.is_configured():
        try:
            github_workflows = await source_github.get_all_workflows_from_github(environment_type=source_env_type)
        except Exception as e:
            logger.warning(f"Failed to fetch workflows from GitHub: {e}")
    
    # Process each workflow
    for workflow_id in body.workflow_ids:
        # Get workflow data from cache first
        workflow_record = await db_service.get_workflow(tenant_id, body.source_environment_id, workflow_id)
        
        # If not in cache, try GitHub
        if not workflow_record:
            github_wf = github_workflows.get(workflow_id)
            if github_wf:
                workflow_record = {
                    "name": github_wf.get("name", "Unknown"),
                    "workflow_data": github_wf
                }
        
        if not workflow_record:
            # Not a blocking issue - just skip this workflow for preflight
            # It might be a new workflow being deployed
            logger.warning(f"Workflow {workflow_id} not found in cache or GitHub, skipping preflight")
            continue

        workflow_name = workflow_record.get("name", "Unknown")
        workflow_data = workflow_record.get("workflow_data", {})

        # Extract logical credentials using provider-specific adapter
        adapter_class = ProviderRegistry.get_adapter_class(body.provider)
        logical_keys = adapter_class.extract_logical_credentials(workflow_data)

        # Check each credential
        nodes = workflow_data.get("nodes", [])
        for node in nodes:
            node_credentials = node.get("credentials", {})
            for cred_type, cred_info in node_credentials.items():
                if isinstance(cred_info, dict):
                    cred_name = cred_info.get("name", "Unknown")
                else:
                    cred_name = str(cred_info) if cred_info else "Unknown"

                logical_key = f"{cred_type}:{cred_name}"

                # Try provider-aware logical mapping first
                logical = await db_service.find_logical_credential_by_name(tenant_id, logical_key)
                if logical:
                    mapping = await db_service.get_mapping_for_logical(
                        tenant_id,
                        body.target_environment_id,
                        body.provider,
                        logical.get("id"),
                    )
                    if not mapping:
                        blocking_issues.append(CredentialIssue(
                            workflow_id=workflow_id,
                            workflow_name=workflow_name,
                            logical_credential_key=logical_key,
                            issue_type="missing_mapping",
                            message=f"No mapping for '{logical_key}' in target environment",
                            is_blocking=True
                        ))
                        continue

                    # Check if mapped physical credential exists
                    mapped_key = (
                        mapping.get("physical_type") or cred_type,
                        mapping.get("physical_name") or cred_name,
                    )
                    if mapped_key not in target_cred_map:
                        blocking_issues.append(CredentialIssue(
                            workflow_id=workflow_id,
                            workflow_name=workflow_name,
                            logical_credential_key=logical_key,
                            issue_type="mapped_missing_in_target",
                            message=f"Mapped credential '{mapping.get('physical_name')}' not found in target",
                            is_blocking=True
                        ))
                        continue

                    # Successfully resolved
                    resolved_mappings.append(ResolvedMapping(
                        logical_key=logical_key,
                        source_physical_name=cred_name,
                        target_physical_name=mapping.get("physical_name") or cred_name,
                        target_physical_id=mapping.get("physical_credential_id") or ""
                    ))
                else:
                    # No logical credential defined - check direct match
                    cred_key = (cred_type, cred_name)
                    if cred_key not in target_cred_map:
                        # Warning: no logical credential and not in target
                        warnings.append(CredentialIssue(
                            workflow_id=workflow_id,
                            workflow_name=workflow_name,
                            logical_credential_key=logical_key,
                            issue_type="no_logical_credential",
                            message=f"'{logical_key}' not defined as logical credential and not found in target",
                            is_blocking=False
                        ))
                    else:
                        # Direct match found
                        target_cred = target_cred_map[cred_key]
                        resolved_mappings.append(ResolvedMapping(
                            logical_key=logical_key,
                            source_physical_name=cred_name,
                            target_physical_name=cred_name,
                            target_physical_id=target_cred.get("id", "")
                        ))

    # Deduplicate resolved mappings
    seen_keys = set()
    unique_resolved = []
    for mapping in resolved_mappings:
        if mapping.logical_key not in seen_keys:
            seen_keys.add(mapping.logical_key)
            unique_resolved.append(mapping)

    user = user_info.get("user", {})
    
    await create_audit_log(
        action_type=AuditActionType.CREDENTIAL_PREFLIGHT_CHECKED,
        action=f"Preflight check for {len(body.workflow_ids)} workflows",
        actor_id=user.get("id"),
        actor_email=user.get("email"),
        actor_name=user.get("name"),
        tenant_id=tenant_id,
        resource_type="promotion",
        provider=body.provider,
        metadata={
            "source_environment_id": body.source_environment_id,
            "target_environment_id": body.target_environment_id,
            "workflow_ids": body.workflow_ids,
            "blocking_issues_count": len(blocking_issues),
            "warnings_count": len(warnings),
            "resolved_mappings_count": len(unique_resolved),
            "valid": len(blocking_issues) == 0
        }
    )

    return CredentialPreflightResult(
        valid=len(blocking_issues) == 0,
        blocking_issues=blocking_issues,
        warnings=warnings,
        resolved_mappings=unique_resolved
    )


@router.get("/workflows/{workflow_id}/dependencies", response_model=WorkflowCredentialDependencyResponse)
async def get_workflow_dependencies(
    workflow_id: str,
    provider: str = "n8n",
    user_info: dict = Depends(require_platform_admin())
):
    """Get credential dependencies for a specific workflow."""
    tenant_id = get_current_tenant_id(user_info)

    # Get stored dependencies
    deps = await db_service.get_workflow_dependencies(workflow_id, provider)

    if not deps:
        return WorkflowCredentialDependencyResponse(
            workflow_id=workflow_id,
            provider=provider,
            logical_credential_ids=[],
            credentials=[]
        )

    logical_ids = deps.get("logical_credential_ids", [])

    # Enrich with mapping status
    credentials: List[CredentialDetail] = []
    all_mappings = await db_service.list_credential_mappings(tenant_id, provider=provider)

    for logical_key in logical_ids:
        parts = logical_key.split(":", 1)
        cred_type = parts[0] if len(parts) > 0 else ""
        cred_name = parts[1] if len(parts) > 1 else logical_key

        # Find logical credential
        logical = await db_service.find_logical_credential_by_name(tenant_id, logical_key)

        # Find environments with mappings
        target_envs = []
        mapping_status = "missing"

        if logical:
            for m in all_mappings:
                if m.get("logical_credential_id") == logical.get("id"):
                    target_envs.append(m.get("environment_id"))
                    if m.get("status") == "valid":
                        mapping_status = "valid"
            if target_envs and mapping_status != "valid":
                mapping_status = "invalid"

        credentials.append(CredentialDetail(
            logical_key=logical_key,
            credential_type=cred_type,
            credential_name=cred_name,
            is_mapped=len(target_envs) > 0,
            mapping_status=mapping_status if logical else None,
            target_environments=target_envs
        ))

    return WorkflowCredentialDependencyResponse(
        workflow_id=workflow_id,
        provider=provider,
        logical_credential_ids=logical_ids,
        credentials=credentials,
        updated_at=deps.get("updated_at")
    )


@router.post("/dependencies/refresh/{environment_id}")
async def refresh_environment_dependencies(
    environment_id: str,
    provider: Optional[str] = Query(None),
    user_info: dict = Depends(require_platform_admin())
):
    """Manually refresh workflow credential dependencies for an environment."""
    tenant_id = get_current_tenant_id(user_info)
    
    # Get environment
    env = await db_service.get_environment(environment_id, tenant_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    
    provider = provider or env.get("provider", "n8n") or "n8n"
    
    # Use existing refresh method
    await db_service.refresh_workflow_dependencies_for_env(
        tenant_id=tenant_id,
        environment_id=environment_id,
        provider=provider
    )
    
    return {"message": "Dependencies refreshed successfully"}


@router.post("/workflows/{workflow_id}/dependencies/refresh")
async def refresh_workflow_dependencies(
    workflow_id: str,
    environment_id: str,
    provider: str = "n8n",
    user_info: dict = Depends(require_platform_admin())
):
    """Re-extract credential dependencies from workflow data."""
    tenant_id = get_current_tenant_id(user_info)

    # Get workflow from cache
    workflow_record = await db_service.get_workflow(tenant_id, environment_id, workflow_id)
    if not workflow_record:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow_data = workflow_record.get("workflow_data", {})

    # Extract logical credentials using provider-specific adapter
    adapter_class = ProviderRegistry.get_adapter_class(provider)
    logical_keys = adapter_class.extract_logical_credentials(workflow_data)

    # Upsert dependencies
    await db_service.upsert_workflow_dependencies(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        provider=provider,
        logical_credential_ids=logical_keys,
    )

    return {"success": True, "logical_credential_ids": logical_keys}


@router.get("/health/{environment_id}")
@handle_db_errors
async def get_credential_health(
    environment_id: str,
    provider: Optional[str] = Query(None),
    user_info: dict = Depends(require_platform_admin())
):
    """Get credential health summary for an environment."""
    tenant_id = get_current_tenant_id(user_info)
    
    env = await db_service.get_environment(environment_id, tenant_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    
    provider = provider or env.get("provider", "n8n") or "n8n"
    
    # Get all logical credentials
    logical_creds = await db_service.list_logical_credentials(tenant_id)
    
    # Get all mappings for this environment
    mappings = await db_service.list_credential_mappings(
        tenant_id=tenant_id,
        environment_id=environment_id,
        provider=provider
    )
    
    # Get workflow dependencies (using canonical system)
    workflows = await db_service.get_workflows_from_canonical(
        tenant_id=tenant_id,
        environment_id=environment_id,
        include_deleted=False,
        include_ignored=False
    )
    all_required_logical_ids = set()
    workflows_with_missing_deps = []
    
    for wf in workflows:
        wf_id = wf.get("n8n_workflow_id") or wf.get("id")
        deps = await db_service.get_workflow_dependencies(
            tenant_id=tenant_id,
            workflow_id=str(wf_id),
            provider=provider
        )
        if deps:
            required_ids = deps.get("logical_credential_ids", [])
            all_required_logical_ids.update(required_ids)
            
            # Check if any required credentials are missing mappings
            missing_for_wf = []
            for logical_id in required_ids:
                has_mapping = any(m.get("logical_credential_id") == logical_id for m in mappings)
                if not has_mapping:
                    missing_for_wf.append(logical_id)
            
            if missing_for_wf:
                workflows_with_missing_deps.append({
                    "workflow_id": str(wf_id),
                    "workflow_name": wf.get("name", "Unknown"),
                    "missing_credential_ids": missing_for_wf
                })
    
    # Find missing mappings
    mapped_logical_ids = {m.get("logical_credential_id") for m in mappings}
    missing_mappings = all_required_logical_ids - mapped_logical_ids
    
    return {
        "status": "healthy" if len(missing_mappings) == 0 else "unhealthy",
        "total_logical_credentials": len(logical_creds),
        "mapped_credentials": len(mappings),
        "missing_mappings": len(missing_mappings),
        "workflows_affected": len(workflows_with_missing_deps),
        "workflows_with_issues": workflows_with_missing_deps[:10]  # Limit to first 10
    }


@router.get("/matrix", response_model=CredentialMatrixResponse)
@handle_db_errors
async def get_credential_matrix(user_info: dict = Depends(require_platform_admin())):
    """Get a matrix view of all logical credentials and their mappings across environments."""
    tenant_id = get_current_tenant_id(user_info)

    environments = await db_service.get_environments(tenant_id)
    logical_creds = await db_service.list_logical_credentials(tenant_id)
    all_mappings = await db_service.list_credential_mappings(tenant_id)

    matrix: Dict[str, Dict[str, Any]] = {}
    for lc in logical_creds:
        lc_id = lc.get("id")
        matrix[lc_id] = {}
        for env in environments:
            env_id = env.get("id")
            mapping = next(
                (m for m in all_mappings
                 if m.get("logical_credential_id") == lc_id and m.get("environment_id") == env_id),
                None
            )
            if mapping:
                matrix[lc_id][env_id] = {
                    "mapping_id": mapping.get("id"),
                    "physical_credential_id": mapping.get("physical_credential_id"),
                    "physical_name": mapping.get("physical_name"),
                    "physical_type": mapping.get("physical_type"),
                    "status": mapping.get("status"),
                }
            else:
                matrix[lc_id][env_id] = None

    env_list = [
        {"id": e.get("id"), "name": e.get("n8n_name"), "type": e.get("n8n_type")}
        for e in environments
    ]

    return CredentialMatrixResponse(
        logical_credentials=logical_creds,
        environments=env_list,
        matrix=matrix
    )


@router.post("/discover/{environment_id}")
@handle_db_errors
async def discover_credentials_from_workflows(
    environment_id: str,
    provider: str = "n8n",
    user_info: dict = Depends(require_platform_admin())
):
    """Scan all workflows in environment and return unique credential references."""
    tenant_id = get_current_tenant_id(user_info)

    env = await db_service.get_environment(environment_id, tenant_id)
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    workflows = await db_service.get_workflows_from_canonical(
        tenant_id=tenant_id,
        environment_id=environment_id,
        include_deleted=False,
        include_ignored=False
    )
    logical_creds = await db_service.list_logical_credentials(tenant_id)
    all_mappings = await db_service.list_credential_mappings(tenant_id, environment_id=environment_id, provider=provider)

    logical_by_name = {lc.get("name"): lc for lc in logical_creds}
    adapter_class = ProviderRegistry.get_adapter_class(provider)

    discovered: Dict[str, Dict[str, Any]] = {}

    for wf in workflows:
        wf_data = wf.get("workflow_data") or {}
        wf_id = str(wf.get("n8n_workflow_id") or wf.get("id"))
        wf_name = wf.get("name", "Unknown")

        keys = adapter_class.extract_logical_credentials(wf_data)
        for key in keys:
            parts = key.split(":", 1)
            cred_type = parts[0] if len(parts) > 0 else ""
            cred_name = parts[1] if len(parts) > 1 else key

            if key not in discovered:
                existing_logical = logical_by_name.get(key)
                mapping_status = "unmapped"
                if existing_logical:
                    has_mapping = any(
                        m.get("logical_credential_id") == existing_logical.get("id")
                        for m in all_mappings
                    )
                    mapping_status = "mapped" if has_mapping else "unmapped"

                discovered[key] = {
                    "type": cred_type,
                    "name": cred_name,
                    "logical_key": key,
                    "workflow_count": 0,
                    "workflows": [],
                    "existing_logical_id": existing_logical.get("id") if existing_logical else None,
                    "mapping_status": mapping_status,
                }

            discovered[key]["workflow_count"] += 1
            if {"id": wf_id, "name": wf_name} not in discovered[key]["workflows"]:
                discovered[key]["workflows"].append({"id": wf_id, "name": wf_name})

    return list(discovered.values())

