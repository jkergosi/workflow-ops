"""Provider registry for resolving provider adapters.

This module provides the ProviderRegistry class which resolves the correct
adapter implementation based on the provider type and configuration.
"""
from typing import Dict, Any, Type, Union
from app.core.provider import Provider
from app.services.provider_adapter import ProviderAdapter
from app.services.adapters.n8n_adapter import N8NProviderAdapter


class ProviderRegistry:
    """Registry for provider adapters.

    Resolves the correct adapter implementation based on provider type.
    This is the central point for obtaining provider adapters throughout
    the application.

    Example:
        # From environment config
        adapter = ProviderRegistry.get_adapter_for_environment(env_config)
        workflows = await adapter.get_workflows()

        # From explicit provider and config
        adapter = ProviderRegistry.get_adapter(
            provider=Provider.N8N,
            config={"base_url": "...", "api_key": "..."}
        )
    """

    # Map of provider types to adapter classes
    _adapter_classes: Dict[Provider, Type] = {
        Provider.N8N: N8NProviderAdapter,
        # Provider.MAKE: MakeProviderAdapter,  # Future implementation
    }

    @classmethod
    def get_adapter(
        cls,
        provider: Union[Provider, str],
        config: Dict[str, Any]
    ) -> ProviderAdapter:
        """Get a provider adapter instance for the given provider type.

        Args:
            provider: Provider enum or string value
            config: Provider configuration containing connection details

        Returns:
            Instantiated provider adapter

        Raises:
            ValueError: If provider is not supported
        """
        # Convert string to Provider enum if needed
        if isinstance(provider, str):
            provider = Provider.from_string(provider)

        adapter_class = cls._adapter_classes.get(provider)
        if not adapter_class:
            supported = [p.value for p in cls._adapter_classes.keys()]
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {supported}"
            )

        # Extract config based on provider type
        if provider == Provider.N8N:
            return cls._create_n8n_adapter(config)

        # Future providers would have their own config extraction
        raise ValueError(f"No config handler for provider: {provider}")

    @classmethod
    def _create_n8n_adapter(cls, config: Dict[str, Any]) -> N8NProviderAdapter:
        """Create an N8N adapter from configuration.

        Handles both new-style provider_config and legacy n8n_* fields.

        Args:
            config: Environment or provider configuration

        Returns:
            Configured N8NProviderAdapter instance
        """
        print(f"ProviderRegistry._create_n8n_adapter - config keys: {list(config.keys())}", flush=True)

        # Try provider_config first (new style)
        provider_config = config.get("provider_config", {})
        print(f"ProviderRegistry._create_n8n_adapter - provider_config: {provider_config}", flush=True)
        if provider_config:
            base_url = provider_config.get("base_url")
            api_key = provider_config.get("api_key")
            print(f"ProviderRegistry._create_n8n_adapter - from provider_config: base_url={base_url}, api_key_present={bool(api_key)}", flush=True)
            if base_url and api_key:
                return N8NProviderAdapter(base_url=base_url, api_key=api_key)

        # Fall back to legacy n8n_* fields
        base_url = config.get("n8n_base_url") or config.get("base_url")
        api_key = config.get("n8n_api_key") or config.get("api_key")
        print(f"ProviderRegistry._create_n8n_adapter - from legacy: base_url={base_url}, api_key_present={bool(api_key)}, api_key_len={len(api_key) if api_key else 0}", flush=True)

        if not base_url:
            raise ValueError("Missing required configuration: base_url or n8n_base_url")
        if not api_key:
            raise ValueError("Missing required configuration: api_key or n8n_api_key")

        print(f"ProviderRegistry._create_n8n_adapter - creating adapter with base_url={base_url}", flush=True)
        return N8NProviderAdapter(base_url=base_url, api_key=api_key)

    @classmethod
    def get_adapter_for_environment(
        cls,
        env_config: Dict[str, Any]
    ) -> ProviderAdapter:
        """Convenience method to get adapter from environment configuration.

        This is the primary method used throughout the codebase when
        working with environment-specific provider operations.

        Args:
            env_config: Environment record from database

        Returns:
            Instantiated provider adapter configured for the environment

        Raises:
            ValueError: If environment has unsupported provider or missing config
        """
        provider = env_config.get("provider", "n8n")
        return cls.get_adapter(provider, env_config)

    @classmethod
    def is_provider_supported(cls, provider: Union[Provider, str]) -> bool:
        """Check if a provider is supported.

        Args:
            provider: Provider enum or string value

        Returns:
            True if provider is supported, False otherwise
        """
        if isinstance(provider, str):
            try:
                provider = Provider.from_string(provider)
            except ValueError:
                return False

        return provider in cls._adapter_classes

    @classmethod
    def get_supported_providers(cls) -> list[str]:
        """Get list of all supported provider values.

        Returns:
            List of provider string values that have adapter implementations
        """
        return [p.value for p in cls._adapter_classes.keys()]

    @classmethod
    def get_adapter_class(cls, provider: Union[Provider, str]) -> Type:
        """Get the adapter class for a provider (for static method access).

        Use this when you need to call static methods on the adapter class
        without instantiating it (e.g., extract_logical_credentials).

        Args:
            provider: Provider enum or string value

        Returns:
            The adapter class (not instance)

        Raises:
            ValueError: If provider is not supported
        """
        if isinstance(provider, str):
            provider = Provider.from_string(provider)

        adapter_class = cls._adapter_classes.get(provider)
        if not adapter_class:
            supported = [p.value for p in cls._adapter_classes.keys()]
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported providers: {supported}"
            )

        return adapter_class
