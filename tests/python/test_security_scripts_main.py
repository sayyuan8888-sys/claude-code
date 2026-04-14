"""End-to-end integration tests for the standalone scripts/*.py security tools.

Companion to ``test_security_scripts_smoke.py`` (which exercises only pure
helpers). These tests drive each script's ``main()`` entrypoint through at
least one realistic path, with subprocess and network calls replaced by
monkeypatches so the suite stays offline and deterministic.

Scope is deliberately narrow — one happy-path and one error-path per script
where practical. The goal is detecting silent breakage of the argparse →
orchestration → report-write pipeline, not exhaustive coverage of every
branch.
"""

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO_ROOT / "scripts"


def _load(name: str, rel_path: str):
    """Load a standalone script as a module. Mirrors the pattern used in
    ``test_security_scripts_smoke.py`` so both test files see the same
    ``scripts/`` resolution."""
    path = SCRIPTS / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def analyze_apk_mod():
    return _load("analyze_apk_main", "analyze_apk.py")


@pytest.fixture(scope="module")
def security_audit_mod():
    return _load("security_audit_main", "security_audit.py")


@pytest.fixture(scope="module")
def router_audit_mod():
    return _load("router_audit_main", "router_audit.py")


@pytest.fixture(scope="module")
def iphone_mod():
    return _load("iphone_security_checklist_main", "iphone_security_checklist.py")


# ── analyze_apk.py ────────────────────────────────────────────────


def _write_fake_apk(path: Path) -> None:
    """Create a minimal valid ZIP with the files analyze_apk() inspects.

    The real script looks for AndroidManifest.xml (binary format), classes*.dex,
    resources.arsc, and lib/ entries. A ZIP with just the manifest is enough
    for main() to run to completion — the risk analysis paths all degrade
    gracefully on missing sections.
    """
    manifest_blob = (
        b"\x00com.example.fake\x00"
        b"android.permission.INTERNET\x00"
        b"android.permission.CAMERA\x00"
        b"MainActivity\x00"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("AndroidManifest.xml", manifest_blob)
        zf.writestr("classes.dex", b"\x00" * 16)
        zf.writestr("resources.arsc", b"\x00" * 16)


class TestAnalyzeApkMain:
    def test_missing_file_exits_1(self, analyze_apk_mod, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["analyze_apk.py", str(tmp_path / "nope.apk")])
        with pytest.raises(SystemExit) as exc:
            analyze_apk_mod.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "File not found" in out

    def test_happy_path_writes_json_report(
        self, analyze_apk_mod, tmp_path, monkeypatch
    ):
        apk = tmp_path / "fake.apk"
        _write_fake_apk(apk)
        report_path = tmp_path / "report.json"
        monkeypatch.setattr(
            sys, "argv", ["analyze_apk.py", str(apk), "-o", str(report_path)]
        )
        analyze_apk_mod.main()
        assert report_path.is_file(), "main() should have written a JSON report"
        data = json.loads(report_path.read_text())
        # Minimum fields the script always populates (before any risk analysis).
        assert data["file"] == "fake.apk"
        assert "hashes" in data
        assert "size_bytes" in data


# ── security_audit.py ─────────────────────────────────────────────


class TestSecurityAuditMain:
    def test_no_flags_prints_help(self, security_audit_mod, monkeypatch, capsys):
        """With no action flags, main() should print help and return
        without error rather than crashing."""
        monkeypatch.setattr(sys, "argv", ["security_audit.py"])
        security_audit_mod.main()
        out = capsys.readouterr().out
        assert "usage:" in out.lower() or "Examples:" in out

    def test_scan_dir_flags_apk_as_critical(
        self, security_audit_mod, tmp_path, monkeypatch, capsys
    ):
        # Drop a single .apk into a tmpdir and verify it shows up as CRITICAL.
        (tmp_path / "benign.txt").write_text("hello")
        (tmp_path / "suspicious.apk").write_bytes(b"PK\x03\x04dummy")

        out_path = tmp_path / "report.json"
        monkeypatch.setattr(
            sys, "argv",
            [
                "security_audit.py",
                "--scan-dir", str(tmp_path),
                "--output", str(out_path),
            ],
        )
        security_audit_mod.main()

        assert out_path.is_file()
        data = json.loads(out_path.read_text())
        scan = data["results"]["file_scan"]
        assert any(
            f["extension"] == ".apk" and f["severity"] == "CRITICAL" for f in scan
        ), f"expected a CRITICAL .apk finding, got {scan!r}"


# ── router_audit.py ───────────────────────────────────────────────


class TestRouterAuditMain:
    def test_end_to_end_with_all_phases_mocked(
        self, router_audit_mod, tmp_path, monkeypatch
    ):
        """main() runs a 7-phase pipeline with real network/SSL calls. We
        monkeypatch each phase to a no-op/empty result and assert the
        final report file is written with the expected top-level shape
        — enough to catch argparse regressions and phase re-orderings."""
        monkeypatch.setattr(router_audit_mod, "discover_gateway", lambda: "192.168.1.1")
        monkeypatch.setattr(
            router_audit_mod,
            "check_dns_hijacking",
            lambda: {"hijack_detected": False, "configured_servers": []},
        )
        monkeypatch.setattr(router_audit_mod, "scan_connected_devices", lambda gw: [])
        monkeypatch.setattr(router_audit_mod, "scan_router_ports", lambda gw: [])
        monkeypatch.setattr(router_audit_mod, "check_ssl_interception", lambda: False)
        monkeypatch.setattr(router_audit_mod, "check_router_dns_config", lambda: {})

        out_path = tmp_path / "router.json"
        monkeypatch.setattr(
            sys, "argv",
            ["router_audit.py", "--gateway", "192.168.1.1", "-o", str(out_path)],
        )
        router_audit_mod.main()

        assert out_path.is_file()
        data = json.loads(out_path.read_text())
        # generate_report() writes its own structure; just verify it's
        # populated and references the gateway we mocked.
        assert data, "report JSON should not be empty"
        text = json.dumps(data)
        assert "192.168.1.1" in text


# ── iphone_security_checklist.py ──────────────────────────────────


class TestIphoneChecklistMain:
    def test_eof_during_checklist_exits_1(
        self, iphone_mod, tmp_path, monkeypatch, capsys
    ):
        """run_checklist() uses input() heavily. With closed stdin it raises
        EOFError, which main() is supposed to catch and exit 1 on."""
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        out_path = tmp_path / "iphone.json"
        monkeypatch.setattr(
            sys, "argv",
            ["iphone_security_checklist.py", "--output", str(out_path)],
        )
        with pytest.raises(SystemExit) as exc:
            iphone_mod.main()
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "interrupted" in out.lower()
        # Nothing should have been written on the error path.
        assert not out_path.exists()
