# pytest tests validating the MIT License with Custom Clauses
# Testing framework: pytest

import os
import re
from _license_assertions import run_all_assertions, read_license_text, DEFAULT_EXPECTED

def test_license_file_exists_and_not_empty():
    text, path = read_license_text()
    assert path is not None, "Expected a LICENSE file at repo root."
    assert text.strip(), f"LICENSE file '{path}' should not be empty."

def test_license_contains_custom_title_and_owner():
    text, _ = read_license_text()
    assert DEFAULT_EXPECTED["title"] in text
    assert DEFAULT_EXPECTED["owner"] in text

def test_license_contains_custom_usage_clauses_and_contact():
    text, _ = read_license_text()
    for key in ("important_section", "unauthorized", "approval", "telegram"):
        assert DEFAULT_EXPECTED[key] in text, f"Missing expected section or contact: {key}"

def test_license_contains_mit_disclaimer_phrases():
    text, _ = read_license_text()
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text
    assert "WITHOUT WARRANTY OF ANY KIND" in text

def test_license_year_looks_valid_and_reasonable():
    text, _ = read_license_text()
    m = re.search(r"Copyright\s*\(c\)\s*(\d{4})", text)
    assert m, "Missing copyright year"
    year = int(m.group(1))
    assert 2000 <= year <= 2100

def test_license_has_no_conflicting_license_markers():
    text, _ = read_license_text()
    forbidden = ["GNU GENERAL PUBLIC LICENSE", "Apache License, Version 2.0", "Mozilla Public License"]
    assert not any(marker in text for marker in forbidden)

def test_license_full_validation_happy_path():
    path = run_all_assertions()
    assert os.path.exists(path)