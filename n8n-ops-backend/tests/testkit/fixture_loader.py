"""Utility for loading golden JSON fixtures."""
import json
import os
from pathlib import Path
from typing import Any, Dict


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(fixture_path: str) -> Dict[str, Any]:
    """
    Load a golden JSON fixture.
    
    Args:
        fixture_path: Relative path from fixtures/ directory (e.g., "n8n/workflow_simple.json")
    
    Returns:
        Parsed JSON content as dictionary
    
    Raises:
        FileNotFoundError: If fixture file doesn't exist
        json.JSONDecodeError: If fixture contains invalid JSON
    """
    full_path = FIXTURES_DIR / fixture_path
    
    if not full_path.exists():
        raise FileNotFoundError(
            f"Fixture not found: {fixture_path}\n"
            f"Expected at: {full_path}\n"
            f"Available fixtures: {list_fixtures()}"
        )
    
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_fixtures() -> list[str]:
    """List all available fixture files."""
    fixtures = []
    for root, _, files in os.walk(FIXTURES_DIR):
        for file in files:
            if file.endswith(".json"):
                rel_path = Path(root).relative_to(FIXTURES_DIR) / file
                fixtures.append(str(rel_path).replace("\\", "/"))
    return sorted(fixtures)


def deep_merge(base: Dict, overrides: Dict) -> Dict:
    """
    Deep merge overrides into base dictionary.
    
    Args:
        base: Base dictionary
        overrides: Dictionary with values to override
    
    Returns:
        New dictionary with merged values
    """
    result = base.copy()
    
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result

