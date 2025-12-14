from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import httpx

from app.services.database import db_service
from app.schemas.support import (
    SupportRequestCreate,
    SupportRequestResponse,
    IssueContractV1,
    IssueContractApp,
    IssueContractSource,
    IssueContractActor,
    IssueContractIntent,
    IssueContractContext,
    IssueContractImpact,
    IssueContractEvidence,
    IssueContractAutomation,
    IntentKind,
    SupportConfigResponse,
    SupportConfigUpdate,
)
from app.core.config import settings


class SupportService:
    """Service for support request intake and n8n forwarding"""

    def build_issue_contract(
        self,
        request: SupportRequestCreate,
        user_email: str,
        user_id: Optional[str],
        tenant_id: str,
        diagnostics: Optional[Dict[str, Any]] = None
    ) -> IssueContractV1:
        """Build Issue Contract v1 from support request data"""

        event_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat() + "Z"

        # Extract diagnostics or use defaults
        diag = diagnostics or request.diagnostics or {}
        app_env = diag.get("app_env", "unknown")
        app_version = diag.get("app_version")
        git_sha = diag.get("git_sha")
        route = diag.get("route")
        correlation_id = diag.get("correlation_id", str(uuid.uuid4()))

        # Build intent based on request type
        if request.intent_kind == IntentKind.BUG and request.bug_report:
            bug = request.bug_report
            description = f"**What happened:**\n{bug.what_happened}\n\n**Expected behavior:**\n{bug.expected_behavior}"
            if bug.steps_to_reproduce:
                description += f"\n\n**Steps to reproduce:**\n{bug.steps_to_reproduce}"

            intent = IssueContractIntent(
                kind=IntentKind.BUG,
                title=bug.title,
                description=description,
                requested_outcome=bug.expected_behavior
            )
            impact = IssueContractImpact(
                severity=bug.severity,
                frequency=bug.frequency
            )
            attachments = bug.attachments

        elif request.intent_kind == IntentKind.FEATURE and request.feature_request:
            feature = request.feature_request
            description = f"**Problem/Goal:**\n{feature.problem_goal}\n\n**Desired outcome:**\n{feature.desired_outcome}"
            if feature.who_is_this_for:
                description += f"\n\n**Who is this for:**\n{feature.who_is_this_for}"

            intent = IssueContractIntent(
                kind=IntentKind.FEATURE,
                title=feature.title,
                description=description,
                requested_outcome=feature.desired_outcome,
                acceptance_criteria=feature.acceptance_criteria
            )
            impact = None
            attachments = None

        elif request.intent_kind == IntentKind.TASK and request.help_request:
            help_req = request.help_request
            intent = IssueContractIntent(
                kind=IntentKind.TASK,
                title=help_req.title,
                description=help_req.details
            )
            impact = None
            attachments = help_req.attachments

        else:
            raise ValueError(f"Invalid request: intent_kind {request.intent_kind} missing corresponding data")

        # Build evidence
        evidence = None
        if attachments:
            evidence = IssueContractEvidence(attachments=attachments)

        return IssueContractV1(
            schema_version="1.0",
            event_id=event_id,
            created_at=created_at,
            app=IssueContractApp(
                app_id="workflow-ops",
                app_env=app_env,
                app_version=app_version,
                git_sha=git_sha
            ),
            source=IssueContractSource(
                channel="in_app",
                actor_type="user",
                actor=IssueContractActor(
                    user_id=user_id,
                    email=user_email
                )
            ),
            intent=intent,
            context=IssueContractContext(
                tenant_id=tenant_id,
                environment=app_env,
                route=route,
                correlation_id=correlation_id
            ),
            impact=impact,
            evidence=evidence,
            automation=IssueContractAutomation(
                ai_autonomy="approval_required",
                risk="low"
            )
        )

    async def forward_to_n8n(
        self,
        contract: IssueContractV1,
        tenant_id: str
    ) -> SupportRequestResponse:
        """Forward Issue Contract to n8n webhook and return JSM key"""

        # Get support config for tenant
        config = await self.get_config(tenant_id)
        webhook_url = config.n8n_webhook_url if config else None

        if not webhook_url:
            # For development/testing, return a mock JSM key
            mock_key = f"SUP-{uuid.uuid4().hex[:6].upper()}"
            return SupportRequestResponse(jsm_request_key=mock_key)

        # Forward to n8n
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Content-Type": "application/json"}

            # Add API key if configured
            if config and config.n8n_api_key:
                headers["Authorization"] = f"Bearer {config.n8n_api_key}"

            response = await client.post(
                webhook_url,
                json=contract.model_dump(),
                headers=headers
            )
            response.raise_for_status()

            # n8n should return { "jsmRequestKey": "SUP-123" }
            result = response.json()
            jsm_key = result.get("jsmRequestKey") or result.get("jsm_request_key")

            if not jsm_key:
                # Fallback if n8n doesn't return expected format
                jsm_key = f"SUP-{uuid.uuid4().hex[:6].upper()}"

            return SupportRequestResponse(jsm_request_key=jsm_key)

    async def get_config(self, tenant_id: str) -> Optional[SupportConfigResponse]:
        """Get support configuration for tenant"""
        result = await db_service.get_support_config(tenant_id)
        if not result:
            return None

        return SupportConfigResponse(
            tenant_id=result.get("tenant_id", tenant_id),
            n8n_webhook_url=result.get("n8n_webhook_url"),
            n8n_api_key=result.get("n8n_api_key"),
            jsm_portal_url=result.get("jsm_portal_url"),
            jsm_cloud_instance=result.get("jsm_cloud_instance"),
            jsm_api_token=result.get("jsm_api_token"),
            jsm_project_key=result.get("jsm_project_key"),
            jsm_bug_request_type_id=result.get("jsm_bug_request_type_id"),
            jsm_feature_request_type_id=result.get("jsm_feature_request_type_id"),
            jsm_help_request_type_id=result.get("jsm_help_request_type_id"),
            jsm_widget_embed_code=result.get("jsm_widget_embed_code"),
            updated_at=result.get("updated_at")
        )

    async def update_config(
        self,
        tenant_id: str,
        data: SupportConfigUpdate
    ) -> SupportConfigResponse:
        """Update support configuration for tenant"""
        update_data = data.model_dump(exclude_unset=True)
        update_data["tenant_id"] = tenant_id
        update_data["updated_at"] = datetime.utcnow().isoformat()

        result = await db_service.upsert_support_config(tenant_id, update_data)

        return SupportConfigResponse(
            tenant_id=tenant_id,
            n8n_webhook_url=result.get("n8n_webhook_url"),
            n8n_api_key=result.get("n8n_api_key"),
            jsm_portal_url=result.get("jsm_portal_url"),
            jsm_cloud_instance=result.get("jsm_cloud_instance"),
            jsm_api_token=result.get("jsm_api_token"),
            jsm_project_key=result.get("jsm_project_key"),
            jsm_bug_request_type_id=result.get("jsm_bug_request_type_id"),
            jsm_feature_request_type_id=result.get("jsm_feature_request_type_id"),
            jsm_help_request_type_id=result.get("jsm_help_request_type_id"),
            jsm_widget_embed_code=result.get("jsm_widget_embed_code"),
            updated_at=result.get("updated_at")
        )

    async def test_n8n_connection(self, tenant_id: str) -> Dict[str, Any]:
        """Test n8n webhook connection"""
        config = await self.get_config(tenant_id)

        if not config or not config.n8n_webhook_url:
            return {
                "success": False,
                "message": "n8n webhook URL not configured"
            }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Content-Type": "application/json"}
                if config.n8n_api_key:
                    headers["Authorization"] = f"Bearer {config.n8n_api_key}"

                # Send a test ping
                test_payload = {
                    "test": True,
                    "timestamp": datetime.utcnow().isoformat()
                }

                response = await client.post(
                    config.n8n_webhook_url,
                    json=test_payload,
                    headers=headers
                )

                if response.status_code < 400:
                    return {
                        "success": True,
                        "message": f"Connection successful (status {response.status_code})"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Connection failed with status {response.status_code}"
                    }

        except httpx.TimeoutException:
            return {
                "success": False,
                "message": "Connection timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }


# Singleton instance
support_service = SupportService()
