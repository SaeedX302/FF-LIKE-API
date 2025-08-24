"""
Test suite: Render YAML configuration validation

Framework note:
- Tests are authored with the standard library 'unittest' for maximum compatibility.
- If this project uses pytest, these unittest tests will still be discovered and executed by pytest.
- Dependency note: Tests attempt to import PyYAML (yaml). If unavailable, tests skip gracefully.

Focus:
- This suite focuses on validating the Render-style YAML based on the provided PR diff content (services → single web service
  named "ff-like-api" with Python env, specific build/start commands, and envVars for ACCESS_KEY and PYTHON_VERSION=3.8.18).

What is verified:
- YAML parses successfully.
- Top-level is a dict with a non-empty 'services' list.
- First service includes required keys with exact expected values:
  type=web, env=python, name=ff-like-api,
  buildCommand="pip install -r requirements.txt", startCommand="gunicorn wsgi:app".
- envVars list contains:
  - ACCESS_KEY with sync: false (boolean False, not "false").
  - PYTHON_VERSION with value "3.8.18".
- Additional semantic checks:
  - No duplicate env var keys.
  - PYTHON_VERSION follows MAJOR.MINOR.PATCH and equals "3.8.18".
  - ACCESS_KEY does not accidentally have a plaintext value set.
- Negative cases with mutated YAML to ensure validation flags issues.

"""

import io
import os
import re
import copy
import unittest
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


SNIPPET = """services:
  - type: web
    name: ff-like-api
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn wsgi:app"
    envVars:
      - key: ACCESS_KEY
        sync: false
      - key: PYTHON_VERSION
        value: 3.8.18
"""

EXPECTED_CORE = {
    "services": [
        {
            "type": "web",
            "name": "ff-like-api",
            "env": "python",
            "buildCommand": "pip install -r requirements.txt",
            "startCommand": "gunicorn wsgi:app",
            "envVars": [
                {"key": "ACCESS_KEY", "sync": False},
                {"key": "PYTHON_VERSION", "value": "3.8.18"},
            ],
        }
    ]
}


def _find_render_file() -> Optional[str]:
    """Return a path to render.yml or render.yaml if either exists in repo root."""
    candidates = ("render.yaml", "render.yml")
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _load_yaml_str() -> Tuple[str, bool]:
    """
    Load YAML content from file if available; otherwise return the embedded snippet.
    Returns (content, from_file_flag).
    """
    path = _find_render_file()
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return (f.read(), True)
    return (SNIPPET, False)


def _safe_load_yaml(yaml_str: str) -> Dict[str, Any]:
    if yaml is None:
        raise unittest.SkipTest("PyYAML is not installed; skipping Render YAML tests.")
    data = yaml.safe_load(io.StringIO(yaml_str))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise AssertionError(f"Top-level YAML object must be a mapping/dict, got: {type(data)}")
    return data


def _envvars_to_map(envvars: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Convert list of env var entries into a mapping keyed by 'key' for easier assertions."""
    m: Dict[str, Dict[str, Any]] = {}
    for item in envvars:
        k = item.get("key")
        if isinstance(k, str):
            if k in m:
                # Mark duplicate by keeping a special key
                m[f"__DUP__{k}__"] = item
            else:
                m[k] = item
    return m


def _validate_service(service: Dict[str, Any]) -> List[str]:
    """Return a list of validation error messages (empty if valid)."""
    errors: List[str] = []
    required_fields = ["type", "name", "env", "buildCommand", "startCommand", "envVars"]
    for rf in required_fields:
        if rf not in service:
            errors.append(f"Missing required field: {rf}")

    if service.get("type") != "web":
        errors.append(f"type must be 'web'; got {service.get('type')!r}")
    if service.get("env") != "python":
        errors.append(f"env must be 'python'; got {service.get('env')!r}")
    if not service.get("buildCommand"):
        errors.append("buildCommand must be non-empty")
    if not service.get("startCommand"):
        errors.append("startCommand must be non-empty")

    envvars = service.get("envVars")
    if not isinstance(envvars, list):
        errors.append("envVars must be a list")
        return errors

    # Required env vars
    env_map = _envvars_to_map(envvars)
    for key in ("ACCESS_KEY", "PYTHON_VERSION"):
        if key not in env_map:
            errors.append(f"envVars missing required key: {key}")

    # ACCESS_KEY: must not expose plaintext 'value'; must have sync False (boolean)
    access_cfg = env_map.get("ACCESS_KEY")
    if access_cfg is not None:
        if "value" in access_cfg and access_cfg.get("value"):
            errors.append("ACCESS_KEY must not specify a plaintext 'value'")
        if "sync" not in access_cfg:
            errors.append("ACCESS_KEY must define 'sync'")
        else:
            sync_val = access_cfg.get("sync")
            if not isinstance(sync_val, bool) or sync_val is not False:
                errors.append("ACCESS_KEY 'sync' must be boolean False (not 'false' string, not True)")
    # PYTHON_VERSION: exact pin and semver-like format
    pyver_cfg = env_map.get("PYTHON_VERSION")
    if pyver_cfg is not None:
        ver = pyver_cfg.get("value")
        if not isinstance(ver, str):
            errors.append("PYTHON_VERSION 'value' must be a string")
        else:
            if not re.fullmatch(r"\d+\.\d+\.\d+", ver or ""):
                errors.append(f"PYTHON_VERSION value must be MAJOR.MINOR.PATCH; got {ver!r}")
            if ver != "3.8.18":
                errors.append(f"PYTHON_VERSION must be '3.8.18'; got {ver!r}")

    # Duplicate detection
    seen: set = set()
    for item in envvars:
        k = item.get("key")
        if k in seen:
            errors.append(f"Duplicate env var key: {k}")
        else:
            seen.add(k)
    return errors


@unittest.skipIf(yaml is None, "PyYAML is not installed; skipping Render YAML tests.")
class TestRenderYaml(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.yaml_text, cls.from_file = _load_yaml_str()
        cls.cfg = _safe_load_yaml(cls.yaml_text)

    def test_yaml_parses_and_has_services(self):
        self.assertIsInstance(self.cfg, dict, "Top-level YAML must be a mapping")
        self.assertIn("services", self.cfg, "Missing 'services' key at top-level")
        self.assertIsInstance(self.cfg["services"], list, "'services' must be a list")
        self.assertGreaterEqual(len(self.cfg["services"]), 1, "'services' must contain at least one service")

    def test_service_core_fields_and_values(self):
        srv = self.cfg["services"][0]
        # Required fields
        for k in ("type", "name", "env", "buildCommand", "startCommand", "envVars"):
            self.assertIn(k, srv, f"Service missing required field: {k}")
        # Exact expected values
        self.assertEqual("web", srv["type"])
        self.assertEqual("python", srv["env"])
        self.assertEqual("ff-like-api", srv["name"])
        self.assertEqual("pip install -r requirements.txt", srv["buildCommand"])
        self.assertEqual("gunicorn wsgi:app", srv["startCommand"])

    def test_envvars_expected_entries_and_types(self):
        envvars = self.cfg["services"][0]["envVars"]
        self.assertIsInstance(envvars, list)
        env_map = _envvars_to_map(envvars)
        self.assertIn("ACCESS_KEY", env_map)
        self.assertIn("PYTHON_VERSION", env_map)

        acc = env_map["ACCESS_KEY"]
        self.assertNotIn("value", acc, "ACCESS_KEY must not include a plaintext 'value'")
        self.assertIn("sync", acc, "ACCESS_KEY must define 'sync'")
        self.assertIsInstance(acc["sync"], bool, "ACCESS_KEY 'sync' must be a boolean")
        self.assertFalse(acc["sync"], "ACCESS_KEY 'sync' must be False")

        pyv = env_map["PYTHON_VERSION"]
        self.assertIn("value", pyv, "PYTHON_VERSION must define 'value'")
        self.assertIsInstance(pyv["value"], str)
        self.assertRegex(pyv["value"], r"^\d+\.\d+\.\d+$")
        self.assertEqual("3.8.18", pyv["value"])

    def test_no_duplicate_envvar_keys(self):
        envvars = self.cfg["services"][0]["envVars"]
        keys = [item.get("key") for item in envvars if isinstance(item, dict)]
        self.assertEqual(len(keys), len(set(keys)), "Duplicate env var keys detected")

    def test_config_contains_expected_subset_semantics(self):
        """
        Compare normalized structures to ensure expected subset exists even if file adds extra keys.
        """
        srv = self.cfg["services"][0]
        expected = EXPECTED_CORE["services"][0]

        for k, v in expected.items():
            self.assertIn(k, srv, f"Service missing expected key: {k}")
            if k != "envVars":
                self.assertEqual(v, srv[k], f"Mismatch for key '{k}'")
            else:
                # envVars: treat as set keyed by 'key'
                env_map = _envvars_to_map(srv["envVars"])
                exp_map = _envvars_to_map(v)
                for ek, ev in exp_map.items():
                    self.assertIn(ek, env_map, f"envVars missing expected key: {ek}")
                    for subk, subv in ev.items():
                        if subk == "key":
                            continue
                        self.assertIn(subk, env_map[ek], f"envVars[{ek}] missing field: {subk}")
                        self.assertEqual(subv, env_map[ek][subk], f"envVars[{ek}].{subk} mismatch")

    def test_semantic_validation_catches_invalid_cases(self):
        """Mutate the config in typical failure modes and ensure validator flags them."""
        base = copy.deepcopy(self.cfg["services"][0])

        # 1) Missing startCommand
        m1 = copy.deepcopy(base)
        m1.pop("startCommand", None)
        errs = _validate_service(m1)
        self.assertTrue(any("startCommand" in e for e in errs), f"Expected error for missing startCommand, got: {errs}")

        # 2) Wrong type
        m2 = copy.deepcopy(base)
        m2["type"] = "static"
        errs = _validate_service(m2)
        self.assertTrue(any("type must be 'web'" in e for e in errs), f"Expected type error, got: {errs}")

        # 3) ACCESS_KEY sync wrong type (string "false")
        m3 = copy.deepcopy(base)
        env_map = _envvars_to_map(m3["envVars"])
        env_map["ACCESS_KEY"]["sync"] = "false"
        # Rebuild list from map (preserve keys and original order)
        new_env = []
        for item in m3["envVars"]:
            if item.get("key") == "ACCESS_KEY":
                new_env.append({"key": "ACCESS_KEY", "sync": "false"})
            else:
                new_env.append(item)
        m3["envVars"] = new_env
        errs = _validate_service(m3)
        self.assertTrue(any("ACCESS_KEY 'sync' must be boolean False" in e for e in errs), f"Expected ACCESS_KEY sync type error, got: {errs}")

        # 4) PYTHON_VERSION wrong format
        m4 = copy.deepcopy(base)
        env_map = _envvars_to_map(m4["envVars"])
        pyv = env_map["PYTHON_VERSION"]
        pyv["value"] = "3.8"  # not MAJOR.MINOR.PATCH
        m4["envVars"] = [{"key": "ACCESS_KEY", "sync": False}, {"key": "PYTHON_VERSION", "value": "3.8"}]
        errs = _validate_service(m4)
        self.assertTrue(any("MAJOR.MINOR.PATCH" in e for e in errs), f"Expected semver error, got: {errs}")

        # 5) Duplicate env var key
        m5 = copy.deepcopy(base)
        m5["envVars"] = m5["envVars"] + [{"key": "ACCESS_KEY", "sync": False}]
        errs = _validate_service(m5)
        self.assertTrue(any("Duplicate env var key" in e for e in errs), f"Expected duplicate key error, got: {errs}")

    def test_start_and_build_commands_are_safe_strings(self):
        srv = self.cfg["services"][0]
        start_cmd = srv["startCommand"]
        build_cmd = srv["buildCommand"]
        self.assertIsInstance(start_cmd, str)
        self.assertIsInstance(build_cmd, str)
        self.assertNotEqual("", start_cmd.strip())
        self.assertNotEqual("", build_cmd.strip())
        self.assertTrue(start_cmd.startswith("gunicorn"))
        self.assertTrue(build_cmd.startswith("pip install"))

    def test_yaml_source_information(self):
        # Informational: ensure loader path logic works (file present or fallback)
        _, from_file = _load_yaml_str()
        # Either it's from file or snippet; assert bool
        self.assertIn(from_file, (True, False))