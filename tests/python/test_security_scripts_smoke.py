"""Smoke tests for the standalone security audit scripts in scripts/.

These scripts are documented in CLAUDE.md as "example/utility scripts that
aren't wired into any workflow" — so full coverage is overkill, but they still
contain substantial pure-Python logic that can silently rot if nothing
imports them. These tests verify:

  - Every script loads without ImportError.
  - A few pure helpers return plausible values on known-good inputs.
"""

import hashlib
import importlib.util
import io
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _load(name: str, rel_path: str):
    """Load a standalone script as a module (no __init__.py, no package)."""
    path = SCRIPTS / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Module fixtures ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def analyze_apk():
    return _load("analyze_apk", "analyze_apk.py")


@pytest.fixture(scope="module")
def security_audit():
    return _load("security_audit", "security_audit.py")


@pytest.fixture(scope="module")
def router_audit():
    return _load("router_audit", "router_audit.py")


@pytest.fixture(scope="module")
def iphone_security_checklist():
    return _load("iphone_security_checklist", "iphone_security_checklist.py")


# ── Module-load smoke tests ───────────────────────────────────────


def test_all_scripts_import_cleanly(
    analyze_apk, security_audit, router_audit, iphone_security_checklist
):
    """Just importing each script is already meaningful coverage."""
    for mod in (analyze_apk, security_audit, router_audit, iphone_security_checklist):
        assert hasattr(mod, "main"), f"{mod.__name__} missing main()"


# ── analyze_apk pure helpers ──────────────────────────────────────


class TestAnalyzeApkHelpers:
    def test_compute_hashes_matches_hashlib(self, analyze_apk, tmp_path):
        payload = b"hello world" * 100
        f = tmp_path / "sample.bin"
        f.write_bytes(payload)

        result = analyze_apk.compute_hashes(str(f))
        assert result["md5"] == hashlib.md5(payload).hexdigest()
        assert result["sha1"] == hashlib.sha1(payload).hexdigest()
        assert result["sha256"] == hashlib.sha256(payload).hexdigest()

    def test_parse_binary_xml_strings_extracts_ascii(self, analyze_apk):
        data = b"\x00\x01com.example.app\x00\x02android.permission.INTERNET\x00"
        strings = analyze_apk.parse_binary_xml_strings(data)
        assert "com.example.app" in strings
        assert "android.permission.INTERNET" in strings

    def test_parse_binary_xml_strings_skips_short(self, analyze_apk):
        # Strings under 3 chars are filtered out.
        data = b"\x00ab\x00xyz123\x00"
        strings = analyze_apk.parse_binary_xml_strings(data)
        assert "ab" not in strings
        assert "xyz123" in strings

    def test_extract_urls_and_ips(self, analyze_apk):
        blob = (
            b"random\x00https://example.com/foo"
            b" some text\x00"
            b"10.0.0.1 and 8.8.8.8 also 127.0.0.1"
        )
        urls, ips = analyze_apk.extract_urls_and_ips(blob)
        assert "https://example.com/foo" in urls
        assert "10.0.0.1" in ips
        assert "8.8.8.8" in ips
        # Non-routable IPs should be filtered out.
        assert "127.0.0.1" not in ips

    def test_analyze_manifest_binary_finds_permissions(self, analyze_apk):
        data = (
            b"\x00com.example.cool.app\x00"
            b"android.permission.CAMERA\x00"
            b"android.permission.INTERNET\x00"
            b"MainActivity\x00BackgroundService\x00"
        )
        info = analyze_apk.analyze_manifest_binary(data)
        assert "android.permission.CAMERA" in info["permissions"]
        assert "android.permission.INTERNET" in info["permissions"]
        assert any(a.endswith("Activity") for a in info["activities"])
        assert any(s.endswith("Service") for s in info["services"])


# ── security_audit pure helpers ───────────────────────────────────


class TestSecurityAuditHelpers:
    def test_run_cmd_success(self, security_audit):
        stdout, stderr, code = security_audit.run_cmd("echo hello")
        assert code == 0
        assert stdout == "hello"

    def test_run_cmd_failure_returns_nonzero(self, security_audit):
        _, _, code = security_audit.run_cmd("false")
        assert code != 0

    def test_run_cmd_timeout(self, security_audit):
        _, stderr, code = security_audit.run_cmd("sleep 5", timeout=1)
        assert code != 0
        assert "Timed out" in stderr

    def test_analyze_file_missing_returns_empty(self, security_audit, capsys):
        result = security_audit.analyze_file("/nonexistent/path/to/nothing")
        assert result == {}

    def test_analyze_file_populates_hashes(self, security_audit, tmp_path, capsys):
        payload = b"abcdefghij" * 1000
        f = tmp_path / "data.bin"
        f.write_bytes(payload)
        info = security_audit.analyze_file(str(f))
        assert info["sha256"] == hashlib.sha256(payload).hexdigest()
        assert info["size_bytes"] == len(payload)
