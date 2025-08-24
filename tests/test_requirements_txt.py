import re
import pathlib
import pytest

# Testing library and framework: pytest

REQ_PATH_CANDIDATES = [
    pathlib.Path("requirements.txt"),
    # If the repo uses alternative names, add here. We keep scope focused per instructions.
]

EXPECTED_PACKAGES = [
    "Flask[async]",
    "requests",
    "aiohttp",
    "protobuf",
    "googleapis-common-protos",
    "pycryptodome",
    "Werkzeug",
    "gunicorn",
]

PKG_NAME_NORMALIZE = re.compile(r"[^A-Za-z0-9]+")  # PEP 503 normalization helper


def find_requirements_file():
    for p in REQ_PATH_CANDIDATES:
        if p.exists():
            return p
    pytest.skip("No requirements.txt found at repository root; skipping requirements tests.")


def parse_requirements_lines(text):
    """
    Basic parser for requirements-style files.
    - Strips comments (# ...)
    - Keeps extras (e.g., Flask[async])
    - Splits markers (e.g., ; python_version < "3.11") but retains left-hand side for presence checks
    - Ignores empty lines after stripping
    """
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Strip inline comments while respecting URLs (rare in requirements)
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()

        # Split environment marker
        if ";" in line:
            line = line.split(";", 1)[0].strip()

        lines.append(line)
    return lines


def normalized_name(req_line):
    """
    Normalize package "distribution" name for duplicate and presence checks:
    - Split any version specifier or extras: pkg[extra] ==1.2.3 -> pkg[extra]
    - For presence of the exact target (which may include extras), we compare raw tokens first.
    - For duplicate detection, we normalize distribution name ignoring version specifiers.
    """
    # Keep extras for presence checks; for duplicate detection, reduce to distribution name w/o extras
    # Split version specifiers by comparison operators
    base = re.split(r"(==|>=|<=|~=|!=|>|<)", req_line, maxsplit=1)[0].strip()

    # Distribution name may include extras: dist[extras]
    dist = base.split("[", 1)[0]
    # PEP 503 normalization: lowercase and replace non-alnum with hyphens
    return PKG_NAME_NORMALIZE.sub("-", dist).strip("-").lower()


def has_version_pins(req_line):
    return bool(re.search(r"(==|>=|<=|~=|!=|>|<)", req_line))


class TestRequirementsContent:
    def test_expected_packages_present_case_insensitive(self):
        req_file = find_requirements_file()
        content = req_file.read_text(encoding="utf-8")
        lines = parse_requirements_lines(content)

        # Direct raw presence (case-sensitive) first
        missing_raw = [p for p in EXPECTED_PACKAGES if p not in lines]

        # If any missing by raw, attempt case-insensitive/extras-insensitive comparison
        by_lower = [ln.lower() for ln in lines]
        still_missing = []
        for p in missing_raw:
            # Compare by lowercase raw line
            if p.lower() in by_lower:
                continue
            # Compare by normalized distribution + extras (lowercased)
            p_lower = p.lower()
            p_dist = p_lower.split("[", 1)[0]
            # Accept any line that starts with the distribution name and optional extras match
            matched = any(
                ln.startswith(p_lower) or ln.split("[", 1)[0] == p_dist
                for ln in by_lower
            )
            if not matched:
                still_missing.append(p)

        assert not still_missing, f"Missing expected packages from requirements.txt: {still_missing}"

    def test_no_duplicate_distributions_after_normalization(self):
        req_file = find_requirements_file()
        content = req_file.read_text(encoding="utf-8")
        lines = parse_requirements_lines(content)

        seen = {}
        dups = set()
        for ln in lines:
            name = normalized_name(ln)
            if not name:
                # non-package line; ignore
                continue
            if name in seen:
                dups.add(name)
            else:
                seen[name] = ln

        assert not dups, f"Duplicate distributions detected (normalized): {sorted(dups)}"

    def test_line_formatting_no_trailing_spaces_or_blank_noise(self):
        req_file = find_requirements_file()
        raw = req_file.read_text(encoding="utf-8")
        issues = []
        for idx, line in enumerate(raw.splitlines(), start=1):
            if line.endswith(" "):
                issues.append(f"Line {idx} has trailing space")
            if line.strip() == "" and line != "":
                # a line of only spaces (not empty) counts as formatting noise
                issues.append(f"Line {idx} is whitespace-only")
        assert not issues, "Formatting issues in requirements.txt:\n" + "\n".join(issues)

    def test_expected_packages_not_version_pinned_unnecessarily(self):
        """
        Focused on the diff entries: ensure they are not version-pinned unless intentionally required.
        We allow extras like [async] but flag comparator pins for these specific packages to keep them flexible.
        """
        req_file = find_requirements_file()
        content = req_file.read_text(encoding="utf-8")
        lines = parse_requirements_lines(content)

        # Map normalized target names for quick matching
        target_norm = {normalized_name(p): p for p in EXPECTED_PACKAGES}

        pinned = []
        for ln in lines:
            n = normalized_name(ln)
            if n in target_norm and has_version_pins(ln):
                pinned.append(ln)
        assert not pinned, (
            "The following diff-focused packages appear version-pinned; "
            "consider unpinning unless required:\n- " + "\n- ".join(pinned)
        )

    @pytest.mark.parametrize(
        "pkg",
        [
            "Flask[async]",
            "requests",
            "aiohttp",
            "protobuf",
            "googleapis-common-protos",
            "pycryptodome",
            "Werkzeug",
            "gunicorn",
        ],
    )
    def test_each_expected_package_has_valid_identifier(self, pkg):
        """
        Validate that each expected package identifier conforms to simple rules:
        - Distribution part normalized to PEP 503 constraints on allowed characters
        - Extras (if present) are bracketed and non-empty
        """
        dist = pkg.split("[", 1)[0]
        assert re.match(r"^[A-Za-z0-9._-]+$", dist), f"Invalid distribution name in: {pkg}"
        if "[" in pkg:
            assert pkg.endswith("]"), f"Extras must end with closing bracket in: {pkg}"
            extras = pkg.split("[", 1)[1][:-1]
            assert extras, f"Extras cannot be empty in: {pkg}"
            assert re.match(r"^[A-Za-z0-9._,-]+$", extras), f"Invalid extras list in: {pkg}"