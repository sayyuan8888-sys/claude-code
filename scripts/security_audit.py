#!/usr/bin/env python3
"""
Device Security Investigation Toolkit

Scans for suspicious files, analyzes cloud storage directories,
checks network connections, and generates security reports.

Usage:
    python security_audit.py [--scan-dir PATH] [--analyze FILE] [--accounts] [--output report.json]
"""

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timed out", 1
    except Exception as e:
        return "", str(e), 1


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_finding(severity, message):
    icons = {"CRITICAL": "[!!!]", "WARNING": "[!!]", "INFO": "[i]", "OK": "[OK]"}
    icon = icons.get(severity, "[?]")
    print(f"  {icon} {severity}: {message}")


# --- Suspicious File Extensions ---

SUSPICIOUS_EXTENSIONS = {
    # Mobile malware
    ".apk": ("Android app package", "CRITICAL"),
    ".ipa": ("iOS app package", "CRITICAL"),
    ".deb": ("Debian package (jailbroken iOS)", "CRITICAL"),
    # Configuration/profile attacks
    ".mobileconfig": ("iOS configuration profile", "CRITICAL"),
    ".mobileprovision": ("iOS provisioning profile", "WARNING"),
    ".p12": ("Certificate bundle (PKCS12)", "WARNING"),
    ".cer": ("Certificate file", "WARNING"),
    ".crt": ("Certificate file", "WARNING"),
    ".pem": ("PEM certificate", "WARNING"),
    ".der": ("DER certificate", "WARNING"),
    # Executable malware
    ".exe": ("Windows executable", "WARNING"),
    ".dll": ("Windows library", "WARNING"),
    ".bat": ("Windows batch script", "WARNING"),
    ".cmd": ("Windows command script", "WARNING"),
    ".ps1": ("PowerShell script", "WARNING"),
    ".vbs": ("VBScript", "WARNING"),
    ".scr": ("Windows screensaver (executable)", "WARNING"),
    ".msi": ("Windows installer", "WARNING"),
    # macOS threats
    ".dmg": ("macOS disk image", "WARNING"),
    ".pkg": ("macOS package", "WARNING"),
    ".app": ("macOS application", "WARNING"),
    ".command": ("macOS terminal command", "WARNING"),
    # Scripts
    ".sh": ("Shell script", "INFO"),
    ".py": ("Python script", "INFO"),
    ".js": ("JavaScript file", "INFO"),
    # Archives (could contain anything)
    ".zip": ("Archive", "INFO"),
    ".rar": ("Archive", "INFO"),
    ".7z": ("Archive", "INFO"),
    ".tar": ("Archive", "INFO"),
    ".gz": ("Archive", "INFO"),
}


# --- File Scanner ---

def scan_directory(scan_path, max_depth=5):
    """Scan a directory for suspicious files."""
    print_section("File Scanner")

    if not os.path.exists(scan_path):
        print_finding("WARNING", f"Path does not exist: {scan_path}")
        return []

    print_finding("INFO", f"Scanning: {scan_path}")
    print_finding("INFO", f"Max depth: {max_depth}")

    findings = []
    file_count = 0

    for root, dirs, files in os.walk(scan_path):
        # Limit depth
        depth = root.replace(scan_path, "").count(os.sep)
        if depth >= max_depth:
            dirs.clear()
            continue

        for filename in files:
            file_count += 1
            filepath = os.path.join(root, filename)
            ext = os.path.splitext(filename)[1].lower()

            if ext in SUSPICIOUS_EXTENSIONS:
                desc, severity = SUSPICIOUS_EXTENSIONS[ext]
                try:
                    size = os.path.getsize(filepath)
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                except OSError:
                    size = 0
                    mtime = None

                finding = {
                    "path": filepath,
                    "extension": ext,
                    "description": desc,
                    "severity": severity,
                    "size_bytes": size,
                    "modified": mtime.isoformat() if mtime else "unknown",
                }
                findings.append(finding)
                print_finding(
                    severity,
                    f"Found {desc}: {filepath} ({size:,} bytes)"
                )

    print()
    print_finding("INFO", f"Scanned {file_count:,} files")
    print_finding("INFO", f"Found {len(findings)} suspicious files")

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    if critical:
        print()
        print_finding(
            "CRITICAL",
            f"{len(critical)} CRITICAL file(s) found! Review immediately:"
        )
        for f in critical:
            print(f"    -> {f['path']}")

    return findings


# --- File Analyzer ---

def analyze_file(filepath):
    """Compute hashes and extract metadata from a file."""
    print_section("File Analysis")

    if not os.path.exists(filepath):
        print_finding("WARNING", f"File not found: {filepath}")
        return {}

    info = {"path": filepath, "filename": os.path.basename(filepath)}

    # File size
    size = os.path.getsize(filepath)
    info["size_bytes"] = size
    info["size_human"] = f"{size / 1024 / 1024:.2f} MB" if size > 1024 * 1024 else f"{size / 1024:.1f} KB"
    print_finding("INFO", f"File: {filepath}")
    print_finding("INFO", f"Size: {info['size_human']} ({size:,} bytes)")

    # Timestamps
    try:
        stat = os.stat(filepath)
        info["created"] = datetime.fromtimestamp(stat.st_ctime).isoformat()
        info["modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
        print_finding("INFO", f"Modified: {info['modified']}")
    except OSError:
        pass

    # Hashes
    print_finding("INFO", "Computing file hashes...")
    hash_md5 = hashlib.md5()
    hash_sha1 = hashlib.sha1()
    hash_sha256 = hashlib.sha256()

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            hash_md5.update(chunk)
            hash_sha1.update(chunk)
            hash_sha256.update(chunk)

    info["md5"] = hash_md5.hexdigest()
    info["sha1"] = hash_sha1.hexdigest()
    info["sha256"] = hash_sha256.hexdigest()

    print_finding("INFO", f"MD5:    {info['md5']}")
    print_finding("INFO", f"SHA1:   {info['sha1']}")
    print_finding("INFO", f"SHA256: {info['sha256']}")

    # File magic bytes
    with open(filepath, "rb") as f:
        magic = f.read(16)

    info["magic_bytes"] = magic.hex()

    # Identify file type from magic bytes
    magic_signatures = {
        b"PK\x03\x04": "ZIP archive (APK, JAR, DOCX, etc.)",
        b"\x89PNG": "PNG image",
        b"\xff\xd8\xff": "JPEG image",
        b"GIF8": "GIF image",
        b"%PDF": "PDF document",
        b"\x7fELF": "Linux ELF binary",
        b"MZ": "Windows PE executable",
        b"\xca\xfe\xba\xbe": "macOS Mach-O / Java class",
        b"\xfe\xed\xfa": "macOS Mach-O binary",
        b"\xcf\xfa\xed\xfe": "macOS Mach-O 64-bit binary",
        b"dex\n": "Android DEX (Dalvik Executable)",
        b"Rar!\x1a\x07": "RAR archive",
        b"\x1f\x8b": "GZIP archive",
        b"BZ": "BZIP2 archive",
        b"\xfd7zXZ": "XZ archive",
        b"7z\xbc\xaf": "7-Zip archive",
    }

    file_type = "Unknown"
    for sig, desc in magic_signatures.items():
        if magic.startswith(sig):
            file_type = desc
            break

    info["file_type"] = file_type
    print_finding("INFO", f"File type: {file_type}")

    # If it's a ZIP/APK, list contents
    ext = os.path.splitext(filepath)[1].lower()
    if magic.startswith(b"PK\x03\x04") or ext in (".apk", ".zip", ".ipa"):
        print()
        print_finding("INFO", "This is a ZIP-based archive. Use analyze_apk.py for deeper analysis.")

    print()
    print_finding("INFO", "To check these hashes against known malware:")
    print(f"    1. Go to https://www.virustotal.com/gui/search")
    print(f"    2. Search for the SHA256 hash: {info['sha256']}")
    print(f"    3. VirusTotal will show if this file is known malware")

    return info


# --- Network Connection Checker ---

def check_network_connections():
    """List active network connections and flag suspicious ones."""
    print_section("Active Network Connections")

    system = platform.system().lower()

    if system == "darwin":
        out, _, rc = run_cmd("netstat -an -p tcp 2>/dev/null | head -100")
        if not out:
            out, _, rc = run_cmd("lsof -i -n -P 2>/dev/null | head -100")
    elif system == "linux":
        out, _, rc = run_cmd("ss -tunap 2>/dev/null | head -100")
        if not out:
            out, _, rc = run_cmd("netstat -tunap 2>/dev/null | head -100")
    else:
        out, _, rc = run_cmd("netstat -an | head -100")

    if not out:
        print_finding("WARNING", "Could not list network connections (may need elevated privileges)")
        return []

    print_finding("INFO", "Active connections:")
    print()

    connections = []
    suspicious_ports = {
        1080, 3128, 4444, 4443, 5555, 6666, 6667, 7777, 8888, 9090,
        31337, 12345, 54321,  # Known backdoor ports
    }

    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Extract remote IP:port pairs
        ip_port_matches = re.findall(r'(\d+\.\d+\.\d+\.\d+):(\d+)', line)
        for ip, port in ip_port_matches:
            port = int(port)
            if ip.startswith(("127.", "0.0.0.0", "192.168.", "10.", "172.16.")):
                continue  # Skip local

            conn = {"ip": ip, "port": port, "raw": line}
            connections.append(conn)

            if port in suspicious_ports:
                print_finding("WARNING", f"Connection to suspicious port: {ip}:{port}")
                print(f"      {line}")

    print_finding("INFO", f"Found {len(connections)} external connections")

    return connections


# --- Account Security Checklist ---

def generate_account_checklist():
    """Generate a comprehensive account security audit checklist."""
    print_section("Account Security Checklist")

    checklist = [
        {
            "category": "Apple ID / iCloud",
            "priority": "CRITICAL",
            "steps": [
                "Change Apple ID password (from trusted device on mobile data)",
                "Enable two-factor authentication if not already on",
                "Review trusted phone numbers (Settings > Apple ID > Sign-In & Security)",
                "Review trusted devices (Settings > Apple ID > scroll down)",
                "Remove any devices you don't recognize",
                "Check for app-specific passwords and revoke unknown ones",
                "Review iCloud settings — check what's being synced",
                "Check account recovery contacts and remove unknown ones",
                "Review Sign in with Apple — revoke unknown apps",
            ],
        },
        {
            "category": "Email (Gmail / Outlook / etc.)",
            "priority": "CRITICAL",
            "steps": [
                "Change password immediately",
                "Enable 2FA (use authenticator app, NOT SMS)",
                "Review recent login activity / sign-in history",
                "Check email forwarding rules — attackers add hidden forwards",
                "Check connected apps and revoke unknown ones",
                "Check recovery email and phone number",
                "Review filters/rules for any that delete or redirect emails",
                "Search for password reset emails you didn't request",
            ],
        },
        {
            "category": "Banking / Financial",
            "priority": "CRITICAL",
            "steps": [
                "Change passwords for ALL banking apps",
                "Enable biometric authentication",
                "Review recent transactions for unauthorized activity",
                "Set up transaction alerts if not already enabled",
                "Contact bank if suspicious transactions found",
                "Consider freezing credit (Equifax, Experian, TransUnion)",
                "Check for new accounts opened in your name",
            ],
        },
        {
            "category": "Social Media",
            "priority": "HIGH",
            "steps": [
                "Change passwords for all social media accounts",
                "Enable 2FA on all platforms",
                "Review active sessions and log out all devices",
                "Check for unauthorized posts or messages sent",
                "Review connected/authorized apps",
                "Check privacy settings haven't been changed",
                "Review login notification settings",
            ],
        },
        {
            "category": "Messaging Apps (WhatsApp, Telegram, Signal, etc.)",
            "priority": "HIGH",
            "steps": [
                "WhatsApp: Settings > Linked Devices — remove unknown devices",
                "WhatsApp: Enable two-step verification",
                "Telegram: Settings > Devices — terminate unknown sessions",
                "Telegram: Enable two-step verification",
                "Signal: Check linked devices",
                "Review recent messages for anything sent without your knowledge",
            ],
        },
        {
            "category": "Password Manager",
            "priority": "CRITICAL",
            "steps": [
                "If you use one: Change the master password immediately",
                "Review active sessions",
                "Check the breach/compromise report for exposed passwords",
                "Rotate ALL passwords stored in the manager",
                "If you don't use one: START using one (1Password, Bitwarden)",
            ],
        },
        {
            "category": "Cloud Storage (Google Drive, Dropbox, OneDrive)",
            "priority": "HIGH",
            "steps": [
                "Change passwords",
                "Review sharing settings",
                "Check for files you didn't upload",
                "Review connected apps with access",
                "Check trash/recycle bin for deleted evidence",
                "Review activity/audit log if available",
            ],
        },
    ]

    for item in checklist:
        print(f"\n  [{item['priority']}] {item['category']}")
        print(f"  {'-' * 50}")
        for i, step in enumerate(item["steps"], 1):
            print(f"    [ ] {i}. {step}")

    print()
    print_finding(
        "INFO",
        "Work through this list systematically. Do CRITICAL items first."
    )
    print_finding(
        "CRITICAL",
        "Do all password changes from a TRUSTED device on MOBILE DATA."
    )

    return checklist


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Device Security Investigation Toolkit"
    )
    parser.add_argument(
        "--scan-dir", type=str, default=None,
        help="Directory to scan for suspicious files"
    )
    parser.add_argument(
        "--analyze", type=str, default=None,
        help="Analyze a specific suspicious file"
    )
    parser.add_argument(
        "--network", action="store_true",
        help="Check active network connections"
    )
    parser.add_argument(
        "--accounts", action="store_true",
        help="Generate account security checklist"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all checks"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save report to JSON file"
    )
    args = parser.parse_args()

    # If no specific flags, show help
    if not any([args.scan_dir, args.analyze, args.network, args.accounts, args.all]):
        parser.print_help()
        print("\nExamples:")
        print("  python security_audit.py --scan-dir ~/Library/Mobile\\ Documents/")
        print("  python security_audit.py --analyze base.apk")
        print("  python security_audit.py --network")
        print("  python security_audit.py --accounts")
        print("  python security_audit.py --all --scan-dir ~/Downloads/")
        return

    print("=" * 60)
    print("  DEVICE SECURITY INVESTIGATION TOOLKIT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {}

    if args.scan_dir or args.all:
        scan_path = args.scan_dir or os.path.expanduser("~")
        results["file_scan"] = scan_directory(scan_path)

    if args.analyze:
        results["file_analysis"] = analyze_file(args.analyze)

    if args.network or args.all:
        results["network"] = check_network_connections()

    if args.accounts or args.all:
        results["account_checklist"] = generate_account_checklist()

    # Save report
    if args.output:
        report = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.system(),
            "results": results,
        }
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n  Report saved to: {args.output}")

    print()
    print("=" * 60)
    print("  Investigation complete. Review all findings carefully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
