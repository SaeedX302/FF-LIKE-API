import re
from pathlib import Path

# Candidate license file locations (root-level is typical)
CANDIDATES = [
    Path("LICENSE"),
    Path("LICENSE.txt"),
    Path("LICENSE.md"),
]

DEFAULT_EXPECTED = {
    "title": "MIT License with Custom Clauses",
    "owner": "SaeedX302",
    "telegram": "@Saeedxdie",
    "important_section": "Important Usage Clauses",
    "unauthorized": "Unauthorized Use",
    "approval": "Approval for Use",
    "as_is": 'THE SOFTWARE IS PROVIDED "AS IS"',
}

def read_license_text():
    for p in CANDIDATES:
        if p.exists():
            return p.read_text(encoding="utf-8"), p
    # Fallback: If no standard LICENSE file is found, surface a clear error that tests will assert on.
    return "", None

def assert_license_header(text, expected=DEFAULT_EXPECTED):
    assert expected["title"] in text, f'Missing custom title: {expected["title"]}'
    # Year pattern: 4 digits; allow future years as given in diff (e.g., 2026)
    m = re.search(r"Copyright\s*\(c\)\s*(\d{4})\s+(.+)", text)
    assert m, "Missing copyright line with year"
    year = int(m.group(1))
    owner_line = m.group(2).strip()
    assert expected["owner"] in owner_line, f"Expected owner '{expected['owner']}' in header, got: {owner_line}"
    # Sanity on plausible year range (2000-2100)
    assert 2000 <= year <= 2100, f"Unreasonable year in license header: {year}"

def assert_custom_clauses(text, expected=DEFAULT_EXPECTED):
    # Section heading
    assert expected["important_section"] in text, f"Missing section heading '{expected['important_section']}'"
    # Clause 1 and 2 presence with key phrases
    assert expected["unauthorized"] in text, "Missing 'Unauthorized Use' clause"
    assert expected["approval"] in text, "Missing 'Approval for Use' clause"
    assert expected["telegram"] in text, "Missing Telegram contact handle for approval"

def assert_mit_disclaimer(text, expected=DEFAULT_EXPECTED):
    assert expected["as_is"] in text, "Missing standard MIT 'AS IS' disclaimer lead-in"
    # Check presence of common MIT disclaimers phrases
    for phrase in [
        "WITHOUT WARRANTY OF ANY KIND",
        "EXPRESS OR IMPLIED",
        "MERCHANTABILITY",
        "FITNESS FOR A PARTICULAR PURPOSE",
        "NONINFRINGEMENT",
        "IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE",
    ]:
        assert phrase in text, f"Missing MIT disclaimer phrase: {phrase}"

def assert_no_conflicting_license_markers(text):
    # Ensure it doesn't inadvertently include markers from other licenses
    forbidden = ["GNU GENERAL PUBLIC LICENSE", "Apache License, Version 2.0", "Mozilla Public License"]
    for marker in forbidden:
        assert marker not in text, f"Found conflicting license marker: '{marker}'"

def run_all_assertions():
    text, path = read_license_text()
    assert path is not None, "No LICENSE file found at repository root (LICENSE, LICENSE.txt, or LICENSE.md)."
    assert text.strip(), f"LICENSE file '{path}' is empty."
    assert_license_header(text)
    assert_custom_clauses(text)
    assert_mit_disclaimer(text)
    assert_no_conflicting_license_markers(text)
    return path