"""
Tests for src/core/env_schema.py

Covers EnvVar dataclass (required/defaults, sensitive flag);
ENV_SCHEMA list (count, all EnvVar, categories, required/optional vars);
validate_environment() (returns list, no crashes, missing-required warning).
No network, no Tkinter, no file I/O.
"""

import sys
import os
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from core.env_schema import EnvVar, ENV_SCHEMA, validate_environment


# ===========================================================================
# EnvVar dataclass
# ===========================================================================

class TestEnvVar:
    def test_name_stored(self):
        e = EnvVar(name="MY_VAR", description="test")
        assert e.name == "MY_VAR"

    def test_description_stored(self):
        e = EnvVar(name="X", description="Some description")
        assert e.description == "Some description"

    def test_required_default_false(self):
        e = EnvVar(name="X", description="desc")
        assert e.required is False

    def test_default_none_by_default(self):
        e = EnvVar(name="X", description="desc")
        assert e.default is None

    def test_category_default_general(self):
        e = EnvVar(name="X", description="desc")
        assert e.category == "general"

    def test_sensitive_default_false(self):
        e = EnvVar(name="X", description="desc")
        assert e.sensitive is False

    def test_required_can_be_set(self):
        e = EnvVar(name="X", description="desc", required=True)
        assert e.required is True

    def test_default_can_be_set(self):
        e = EnvVar(name="X", description="desc", default="value")
        assert e.default == "value"

    def test_category_can_be_set(self):
        e = EnvVar(name="X", description="desc", category="ai_provider")
        assert e.category == "ai_provider"

    def test_sensitive_can_be_set(self):
        e = EnvVar(name="SECRET", description="desc", sensitive=True)
        assert e.sensitive is True


# ===========================================================================
# ENV_SCHEMA list
# ===========================================================================

class TestEnvSchema:
    def test_is_list(self):
        assert isinstance(ENV_SCHEMA, list)

    def test_non_empty(self):
        assert len(ENV_SCHEMA) > 0

    def test_exactly_35_entries(self):
        assert len(ENV_SCHEMA) == 35

    def test_all_are_env_var_instances(self):
        for e in ENV_SCHEMA:
            assert isinstance(e, EnvVar)

    def test_all_names_non_empty(self):
        for e in ENV_SCHEMA:
            assert len(e.name.strip()) > 0

    def test_all_descriptions_non_empty(self):
        for e in ENV_SCHEMA:
            assert len(e.description.strip()) > 0, f"{e.name} has empty description"

    def test_has_openai_api_key(self):
        names = [e.name for e in ENV_SCHEMA]
        assert "OPENAI_API_KEY" in names

    def test_has_anthropic_api_key(self):
        names = [e.name for e in ENV_SCHEMA]
        assert "ANTHROPIC_API_KEY" in names

    def test_has_medical_assistant_env(self):
        names = [e.name for e in ENV_SCHEMA]
        assert "MEDICAL_ASSISTANT_ENV" in names

    def test_categories_include_ai_provider(self):
        cats = {e.category for e in ENV_SCHEMA}
        assert "ai_provider" in cats

    def test_categories_include_app_config(self):
        cats = {e.category for e in ENV_SCHEMA}
        assert "app_config" in cats

    def test_categories_include_database(self):
        cats = {e.category for e in ENV_SCHEMA}
        assert "database" in cats

    def test_sensitive_vars_exist(self):
        sensitive = [e for e in ENV_SCHEMA if e.sensitive]
        assert len(sensitive) > 0

    def test_api_keys_are_sensitive(self):
        api_keys = [e for e in ENV_SCHEMA if "API_KEY" in e.name]
        for key in api_keys:
            assert key.sensitive is True, f"{key.name} should be sensitive"

    def test_no_duplicate_names(self):
        names = [e.name for e in ENV_SCHEMA]
        assert len(names) == len(set(names))

    def test_required_vars_have_no_default_or_description(self):
        # Required vars that have no default should have a description
        for e in ENV_SCHEMA:
            if e.required:
                assert len(e.description.strip()) > 0

    def test_all_names_are_strings(self):
        for e in ENV_SCHEMA:
            assert isinstance(e.name, str)

    def test_sensitive_count(self):
        sensitive = [e for e in ENV_SCHEMA if e.sensitive]
        assert len(sensitive) >= 10  # Several API keys


# ===========================================================================
# validate_environment
# ===========================================================================

class TestValidateEnvironment:
    def test_returns_list(self):
        result = validate_environment()
        assert isinstance(result, list)

    def test_no_crash_in_default_environment(self):
        # Should not raise even with no env vars set
        try:
            validate_environment()
        except Exception as exc:
            pytest.fail(f"validate_environment raised: {exc}")

    def test_all_warnings_are_strings(self):
        result = validate_environment()
        for w in result:
            assert isinstance(w, str)

    def test_missing_required_var_produces_warning(self, monkeypatch):
        """Add a required var to ENV_SCHEMA and verify warning is generated."""
        import core.env_schema as env_module
        original = env_module.ENV_SCHEMA[:]
        # Add a required var with no default
        test_var = EnvVar(
            name="TEST_REQUIRED_VAR_XYZ",
            description="Test required variable",
            required=True,
        )
        env_module.ENV_SCHEMA.append(test_var)
        # Ensure env var is not set
        monkeypatch.delenv("TEST_REQUIRED_VAR_XYZ", raising=False)
        try:
            result = validate_environment()
            assert any("TEST_REQUIRED_VAR_XYZ" in w for w in result)
        finally:
            env_module.ENV_SCHEMA[:] = original

    def test_set_var_not_in_warnings(self, monkeypatch):
        """A required var that IS set should not appear in warnings."""
        import core.env_schema as env_module
        original = env_module.ENV_SCHEMA[:]
        test_var = EnvVar(
            name="TEST_SET_VAR_XYZ",
            description="Test set variable",
            required=True,
        )
        env_module.ENV_SCHEMA.append(test_var)
        monkeypatch.setenv("TEST_SET_VAR_XYZ", "some_value")
        try:
            result = validate_environment()
            assert not any("TEST_SET_VAR_XYZ" in w for w in result)
        finally:
            env_module.ENV_SCHEMA[:] = original

    def test_optional_missing_var_not_in_warnings(self, monkeypatch):
        """Optional (required=False) missing vars should never appear in warnings."""
        import core.env_schema as env_module
        original = env_module.ENV_SCHEMA[:]
        test_var = EnvVar(
            name="TEST_OPTIONAL_VAR_XYZ",
            description="Test optional variable",
            required=False,
        )
        env_module.ENV_SCHEMA.append(test_var)
        monkeypatch.delenv("TEST_OPTIONAL_VAR_XYZ", raising=False)
        try:
            result = validate_environment()
            assert not any("TEST_OPTIONAL_VAR_XYZ" in w for w in result)
        finally:
            env_module.ENV_SCHEMA[:] = original
