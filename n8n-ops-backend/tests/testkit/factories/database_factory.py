"""Factory for seeding database test data."""
from typing import Any, Dict, List, Optional
from datetime import datetime
import uuid


class DatabaseSeeder:
    """Factory for creating test database records."""
    
    @staticmethod
    def tenant(tenant_id: Optional[str] = None, **overrides) -> Dict[str, Any]:
        """
        Create tenant data.
        
        Args:
            tenant_id: Optional tenant ID (generates UUID if not provided)
            **overrides: Additional fields to override
        
        Returns:
            Tenant dictionary
        """
        base = {
            "id": tenant_id or str(uuid.uuid4()),
            "name": "Test Organization",
            "email": "test@example.com",
            "subscription_tier": "pro",
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return {**base, **overrides}
    
    @staticmethod
    def environment(
        tenant_id: str,
        env_type: str = "development",
        **overrides
    ) -> Dict[str, Any]:
        """
        Create environment data.
        
        Args:
            tenant_id: Tenant ID
            env_type: Environment type (development, staging, production)
            **overrides: Additional fields to override
        
        Returns:
            Environment dictionary
        """
        env_names = {
            "development": "Development",
            "staging": "Staging",
            "production": "Production"
        }
        
        base = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "n8n_name": env_names.get(env_type, "Development"),
            "n8n_type": env_type,
            "n8n_base_url": f"https://{env_type}.n8n.example.com",
            "n8n_api_key": f"fake-api-key-{env_type}",
            "provider": "n8n",
            "env_class": env_type,
            "is_active": True,
            "workflow_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return {**base, **overrides}
    
    @staticmethod
    def pipeline(
        tenant_id: str,
        source_env_id: str,
        target_env_id: str,
        **overrides
    ) -> Dict[str, Any]:
        """
        Create pipeline data.
        
        Args:
            tenant_id: Tenant ID
            source_env_id: Source environment ID
            target_env_id: Target environment ID
            **overrides: Additional fields to override
        
        Returns:
            Pipeline dictionary
        """
        base = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "provider": "n8n",
            "name": "Dev to Prod Pipeline",
            "description": "Promote workflows from development to production",
            "is_active": True,
            "stages": [
                {
                    "source_environment_id": source_env_id,
                    "target_environment_id": target_env_id,
                    "gates": {
                        "require_clean_drift": False,
                        "run_pre_flight_validation": True,
                        "credentials_exist_in_target": False,
                        "nodes_supported_in_target": False,
                        "webhooks_available": False,
                        "target_environment_healthy": False,
                        "max_allowed_risk_level": "High",
                    },
                    "approvals": {
                        "require_approval": False,
                        "approver_role": None,
                        "approver_group": None,
                        "required_approvals": None,
                    },
                    "policy_flags": {
                        "allow_placeholder_credentials": True,
                        "allow_overwriting_hotfixes": True,
                        "allow_force_promotion_on_conflicts": True,
                    },
                },
            ],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return {**base, **overrides}
    
    @staticmethod
    def workflow(
        tenant_id: str,
        environment_id: str,
        n8n_workflow_id: str,
        **overrides
    ) -> Dict[str, Any]:
        """
        Create workflow data.
        
        Args:
            tenant_id: Tenant ID
            environment_id: Environment ID
            n8n_workflow_id: n8n workflow ID
            **overrides: Additional fields to override
        
        Returns:
            Workflow dictionary
        """
        base = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "environment_id": environment_id,
            "n8n_workflow_id": n8n_workflow_id,
            "name": "Test Workflow",
            "active": True,
            "workflow_data": {
                "id": n8n_workflow_id,
                "name": "Test Workflow",
                "nodes": [],
                "connections": {},
            },
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return {**base, **overrides}
    
    @staticmethod
    def create_full_tenant_setup(tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a full tenant setup with environments and pipeline.
        
        Args:
            tenant_id: Optional tenant ID
        
        Returns:
            Dictionary with tenant, environments, and pipeline data
        """
        tenant = DatabaseSeeder.tenant(tenant_id)
        dev_env = DatabaseSeeder.environment(tenant["id"], "development")
        prod_env = DatabaseSeeder.environment(tenant["id"], "production")
        pipeline = DatabaseSeeder.pipeline(
            tenant["id"],
            dev_env["id"],
            prod_env["id"]
        )
        
        return {
            "tenant": tenant,
            "environments": {
                "dev": dev_env,
                "prod": prod_env,
            },
            "pipeline": pipeline,
        }
    
    @staticmethod
    def user(tenant_id: str, role: str = "admin", **overrides) -> Dict[str, Any]:
        """
        Create user data.
        
        Args:
            tenant_id: Tenant ID
            role: User role (admin, developer, viewer)
            **overrides: Additional fields to override
        
        Returns:
            User dictionary
        """
        base = {
            "id": str(uuid.uuid4()),
            "email": f"{role}@example.com",
            "name": f"{role.capitalize()} User",
            "role": role,
            "status": "active",
            "tenant_id": tenant_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return {**base, **overrides}
    
    @staticmethod
    def platform_admin(user_id: str) -> Dict[str, Any]:
        """
        Create platform admin record.
        
        Args:
            user_id: User ID
        
        Returns:
            Platform admin dictionary
        """
        return {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

