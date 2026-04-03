#!/usr/bin/env python3
"""
APK (Android Package) Analyzer

Extracts and analyzes an APK file to identify:
- Package name and app identity
- Requested permissions (especially dangerous ones)
- App components (services, receivers — spyware indicators)
- File hashes for malware lookup
- Embedded URLs and IP addresses

Usage:
    python analyze_apk.py <path_to_apk>
    python analyze_apk.py base.apk --output report.json

No external dependencies required — uses Python standard library only.
APKs are ZIP files containing Android app data.
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import zipfile
from datetime import datetime
from xml.etree import ElementTree


# Android binary XML constants
CHUNK_AXML_FILE = 0x00080003
CHUNK_STRING_POOL = 0x001C0001
CHUNK_RESOURCE_MAP = 0x00080180
CHUNK_START_NAMESPACE = 0x00100100
CHUNK_END_NAMESPACE = 0x00100101
CHUNK_START_TAG = 0x00100102
CHUNK_END_TAG = 0x00100103
CHUNK_TEXT = 0x00100104


# Dangerous Android permissions that indicate spyware/malware
DANGEROUS_PERMISSIONS = {
    # Location tracking
    "android.permission.ACCESS_FINE_LOCATION": ("Precise GPS location", "HIGH"),
    "android.permission.ACCESS_COARSE_LOCATION": ("Approximate location", "HIGH"),
    "android.permission.ACCESS_BACKGROUND_LOCATION": ("Background location tracking", "CRITICAL"),
    # Camera & Microphone
    "android.permission.CAMERA": ("Camera access", "HIGH"),
    "android.permission.RECORD_AUDIO": ("Microphone recording", "CRITICAL"),
    # Contacts & Call logs
    "android.permission.READ_CONTACTS": ("Read contacts", "HIGH"),
    "android.permission.WRITE_CONTACTS": ("Modify contacts", "HIGH"),
    "android.permission.READ_CALL_LOG": ("Read call history", "CRITICAL"),
    "android.permission.WRITE_CALL_LOG": ("Modify call history", "CRITICAL"),
    # SMS
    "android.permission.READ_SMS": ("Read text messages", "CRITICAL"),
    "android.permission.SEND_SMS": ("Send text messages", "CRITICAL"),
    "android.permission.RECEIVE_SMS": ("Intercept incoming SMS", "CRITICAL"),
    "android.permission.READ_PHONE_NUMBERS": ("Read phone numbers", "HIGH"),
    # Phone
    "android.permission.READ_PHONE_STATE": ("Read phone state/identity", "HIGH"),
    "android.permission.CALL_PHONE": ("Make phone calls", "HIGH"),
    "android.permission.ANSWER_PHONE_CALLS": ("Answer calls automatically", "CRITICAL"),
    "android.permission.PROCESS_OUTGOING_CALLS": ("Monitor outgoing calls", "CRITICAL"),
    # Storage
    "android.permission.READ_EXTERNAL_STORAGE": ("Read files/photos", "HIGH"),
    "android.permission.WRITE_EXTERNAL_STORAGE": ("Write files", "HIGH"),
    "android.permission.MANAGE_EXTERNAL_STORAGE": ("Full file access", "CRITICAL"),
    # Network
    "android.permission.INTERNET": ("Internet access", "INFO"),
    "android.permission.ACCESS_NETWORK_STATE": ("Network state", "INFO"),
    "android.permission.ACCESS_WIFI_STATE": ("WiFi state/info", "MEDIUM"),
    "android.permission.CHANGE_WIFI_STATE": ("Change WiFi settings", "HIGH"),
    "android.permission.CHANGE_NETWORK_STATE": ("Change network settings", "HIGH"),
    # System
    "android.permission.RECEIVE_BOOT_COMPLETED": ("Start on boot", "HIGH"),
    "android.permission.FOREGROUND_SERVICE": ("Background service", "MEDIUM"),
    "android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS": ("Prevent battery saving", "HIGH"),
    "android.permission.SYSTEM_ALERT_WINDOW": ("Draw over other apps", "HIGH"),
    "android.permission.BIND_ACCESSIBILITY_SERVICE": ("Accessibility service (can read screen)", "CRITICAL"),
    "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE": ("Read all notifications", "CRITICAL"),
    "android.permission.BIND_DEVICE_ADMIN": ("Device administrator", "CRITICAL"),
    "android.permission.READ_CALENDAR": ("Read calendar", "HIGH"),
    "android.permission.BODY_SENSORS": ("Body sensors", "HIGH"),
    "android.permission.ACTIVITY_RECOGNITION": ("Activity recognition", "MEDIUM"),
    "android.permission.USE_BIOMETRIC": ("Biometric access", "MEDIUM"),
    # Highly suspicious
    "android.permission.INSTALL_PACKAGES": ("Install other apps", "CRITICAL"),
    "android.permission.DELETE_PACKAGES": ("Delete apps", "CRITICAL"),
    "android.permission.GET_ACCOUNTS": ("List device accounts", "HIGH"),
    "android.permission.AUTHENTICATE_ACCOUNTS": ("Authenticate accounts", "CRITICAL"),
    "android.permission.READ_LOGS": ("Read system logs", "CRITICAL"),
    "android.permission.DUMP": ("Dump system state", "CRITICAL"),
    "android.permission.PACKAGE_USAGE_STATS": ("App usage stats", "HIGH"),
}

KNOWN_SPYWARE_PACKAGES = [
    "com.mspy", "org.mspy",
    "com.flexispy",
    "com.cocospy",
    "com.spyic",
    "com.spyzie",
    "com.hoverwatch",
    "com.eyezy",
    "com.umobix",
    "com.xnspy",
    "com.clevguard",
    "com.kidsguard",
    "com.thetruthspy",
    "com.spyfone",
    "com.cerberusapp",
    "com.prey",
    "com.trackview",
    "com.androidmonitor",
    "com.spyera",
    "com.iKeymonitor",
    "com.mobile.spy",
    "com.spyphone",
    "com.phonespy",
    "com.sms.tracker",
    "com.call.recorder.spy",
]


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_finding(severity, message):
    icons = {"CRITICAL": "[!!!]", "WARNING": "[!!]", "HIGH": "[!]", "MEDIUM": "[~]", "INFO": "[i]", "OK": "[OK]"}
    icon = icons.get(severity, "[?]")
    print(f"  {icon} {severity}: {message}")


def compute_hashes(filepath):
    """Compute MD5, SHA1, SHA256 of a file."""
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()

    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)

    return {
        "md5": md5.hexdigest(),
        "sha1": sha1.hexdigest(),
        "sha256": sha256.hexdigest(),
    }


def parse_binary_xml_strings(data):
    """Extract string pool from Android binary XML.

    Android's binary XML format stores all strings in a pool at the beginning.
    This is a simplified parser that extracts the readable strings.
    """
    strings = []
    try:
        # Try to find string-like content in the binary data
        # Android binary XML uses UTF-16LE or UTF-8 encoded strings
        i = 0
        while i < len(data):
            # Look for readable ASCII/UTF-8 sequences
            if 0x20 <= data[i] <= 0x7e:
                start = i
                while i < len(data) and 0x20 <= data[i] <= 0x7e:
                    i += 1
                s = data[start:i].decode("ascii", errors="ignore")
                if len(s) >= 3:  # Only keep strings of length 3+
                    strings.append(s)
            else:
                i += 1
    except Exception:
        pass

    return strings


def analyze_manifest_binary(data):
    """Parse binary AndroidManifest.xml to extract key information."""
    info = {
        "package": None,
        "permissions": [],
        "activities": [],
        "services": [],
        "receivers": [],
        "providers": [],
        "min_sdk": None,
        "target_sdk": None,
    }

    # Extract all readable strings from the binary XML
    strings = parse_binary_xml_strings(data)

    # Find package name (usually follows specific patterns)
    for s in strings:
        if "." in s and not s.startswith("android.") and not s.startswith("http"):
            parts = s.split(".")
            if len(parts) >= 2 and all(p.isidentifier() for p in parts if p):
                if not info["package"] or len(s) > len(info["package"]):
                    # Prefer longer package-like names
                    if not any(x in s for x in ["xml", "schema", "layout", "attr"]):
                        info["package"] = s

    # Find permissions
    for s in strings:
        if "android.permission." in s:
            perm = s.strip()
            if perm not in info["permissions"]:
                info["permissions"].append(perm)
        elif s.startswith("android.permission."):
            if s not in info["permissions"]:
                info["permissions"].append(s)

    # Find components
    for s in strings:
        if s.endswith("Activity"):
            info["activities"].append(s)
        elif s.endswith("Service"):
            info["services"].append(s)
        elif s.endswith("Receiver") or s.endswith("BroadcastReceiver"):
            info["receivers"].append(s)
        elif s.endswith("Provider") or s.endswith("ContentProvider"):
            info["providers"].append(s)

    return info


def extract_urls_and_ips(data):
    """Extract URLs and IP addresses from binary data."""
    text = data.decode("ascii", errors="ignore")

    urls = list(set(re.findall(r'https?://[^\s<>"\'\\]+', text)))
    ips = list(set(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text)))

    # Filter out common non-routable IPs
    ips = [ip for ip in ips if not ip.startswith(("0.", "127.", "255.", "224."))]

    return urls, ips


def analyze_apk(filepath):
    """Full APK analysis."""
    report = {
        "file": os.path.basename(filepath),
        "path": filepath,
        "timestamp": datetime.now().isoformat(),
    }

    # --- File Info & Hashes ---
    print_section("File Information")

    size = os.path.getsize(filepath)
    report["size_bytes"] = size
    report["size_human"] = f"{size / 1024 / 1024:.2f} MB"
    print_finding("INFO", f"File: {filepath}")
    print_finding("INFO", f"Size: {report['size_human']} ({size:,} bytes)")

    hashes = compute_hashes(filepath)
    report["hashes"] = hashes
    print_finding("INFO", f"MD5:    {hashes['md5']}")
    print_finding("INFO", f"SHA1:   {hashes['sha1']}")
    print_finding("INFO", f"SHA256: {hashes['sha256']}")

    # --- ZIP Contents ---
    print_section("APK Contents")

    if not zipfile.is_zipfile(filepath):
        print_finding("CRITICAL", "This file is NOT a valid ZIP/APK!")
        print_finding("CRITICAL", "It may be a disguised malware binary.")
        report["valid_apk"] = False
        return report

    report["valid_apk"] = True

    with zipfile.ZipFile(filepath, "r") as zf:
        file_list = zf.namelist()
        report["file_count"] = len(file_list)
        print_finding("INFO", f"Contains {len(file_list)} files")

        # List key files
        key_files = [
            "AndroidManifest.xml",
            "classes.dex",
            "resources.arsc",
        ]
        for kf in key_files:
            if kf in file_list:
                info = zf.getinfo(kf)
                print_finding("INFO", f"  {kf} ({info.file_size:,} bytes)")
            else:
                if kf == "AndroidManifest.xml":
                    print_finding("WARNING", f"  {kf} — MISSING (unusual)")
                elif kf == "classes.dex":
                    print_finding("WARNING", f"  {kf} — MISSING (no code?)")

        # Count DEX files (multiple = multidex = larger app)
        dex_files = [f for f in file_list if f.endswith(".dex")]
        report["dex_count"] = len(dex_files)
        if len(dex_files) > 1:
            print_finding("INFO", f"  {len(dex_files)} DEX files (multidex app)")

        # Check for native libraries
        native_libs = [f for f in file_list if f.startswith("lib/") and f.endswith(".so")]
        report["native_libs"] = len(native_libs)
        if native_libs:
            print_finding("WARNING", f"  {len(native_libs)} native libraries (harder to analyze)")
            archs = set()
            for lib in native_libs:
                parts = lib.split("/")
                if len(parts) >= 2:
                    archs.add(parts[1])
            print_finding("INFO", f"  Architectures: {', '.join(archs)}")

        # Check for suspicious files
        suspicious_files = []
        for f in file_list:
            lower = f.lower()
            if any(lower.endswith(ext) for ext in [".sh", ".py", ".so", ".bin"]):
                suspicious_files.append(f)
            if "exploit" in lower or "payload" in lower or "shell" in lower:
                suspicious_files.append(f)
            if "root" in lower and not lower.startswith("res/"):
                suspicious_files.append(f)

        if suspicious_files:
            print_finding("WARNING", "Suspicious files found in APK:")
            for sf in suspicious_files[:20]:
                print(f"      {sf}")

        # --- Parse AndroidManifest.xml ---
        print_section("AndroidManifest.xml Analysis")

        manifest_info = {}
        if "AndroidManifest.xml" in file_list:
            manifest_data = zf.read("AndroidManifest.xml")

            # Android manifests in APKs are in binary XML format
            manifest_info = analyze_manifest_binary(manifest_data)
            report["manifest"] = manifest_info

            # Package name
            if manifest_info.get("package"):
                print_finding("INFO", f"Package: {manifest_info['package']}")

                # Check against known spyware
                pkg = manifest_info["package"].lower()
                is_spyware = any(
                    known.lower() in pkg for known in KNOWN_SPYWARE_PACKAGES
                )
                if is_spyware:
                    print_finding(
                        "CRITICAL",
                        f"Package '{manifest_info['package']}' matches KNOWN SPYWARE!"
                    )
                    report["is_known_spyware"] = True
                else:
                    report["is_known_spyware"] = False

        # --- Permission Analysis ---
        print_section("Permission Analysis")

        permissions = manifest_info.get("permissions", [])
        report["permissions"] = []

        critical_perms = []
        high_perms = []

        for perm in sorted(permissions):
            short_name = perm.replace("android.permission.", "")
            if perm in DANGEROUS_PERMISSIONS:
                desc, level = DANGEROUS_PERMISSIONS[perm]
                report["permissions"].append({
                    "permission": perm,
                    "description": desc,
                    "risk_level": level,
                })
                if level == "CRITICAL":
                    critical_perms.append((short_name, desc))
                    print_finding("CRITICAL", f"{short_name} — {desc}")
                elif level == "HIGH":
                    high_perms.append((short_name, desc))
                    print_finding("WARNING", f"{short_name} — {desc}")
                else:
                    print_finding("INFO", f"{short_name} — {desc}")
            else:
                print_finding("INFO", f"{short_name}")
                report["permissions"].append({
                    "permission": perm,
                    "description": "Standard permission",
                    "risk_level": "INFO",
                })

        if not permissions:
            print_finding("INFO", "No permissions found (binary XML parsing may be limited)")
            print_finding("INFO", "Try uploading the APK to VirusTotal for complete analysis")

        # --- Spyware Score ---
        print_section("Threat Assessment")

        score = 0
        reasons = []

        if report.get("is_known_spyware"):
            score += 100
            reasons.append("Matches known spyware package name")

        if critical_perms:
            score += len(critical_perms) * 15
            reasons.append(f"{len(critical_perms)} critical permissions")

        if high_perms:
            score += len(high_perms) * 5
            reasons.append(f"{len(high_perms)} high-risk permissions")

        # Spyware permission combos
        perm_set = set(permissions)
        spyware_combos = [
            ({"android.permission.READ_SMS", "android.permission.RECORD_AUDIO"},
             "SMS reading + audio recording"),
            ({"android.permission.ACCESS_FINE_LOCATION", "android.permission.RECORD_AUDIO"},
             "Location tracking + audio recording"),
            ({"android.permission.READ_CONTACTS", "android.permission.READ_SMS",
              "android.permission.READ_CALL_LOG"},
             "Full contact/SMS/call surveillance"),
            ({"android.permission.CAMERA", "android.permission.RECORD_AUDIO",
              "android.permission.ACCESS_FINE_LOCATION"},
             "Camera + mic + location (full surveillance)"),
        ]

        for combo, desc in spyware_combos:
            if combo.issubset(perm_set):
                score += 25
                reasons.append(f"Spyware combo: {desc}")

        if manifest_info.get("services"):
            score += 5
            reasons.append(f"{len(manifest_info['services'])} background services")

        if manifest_info.get("receivers"):
            score += 5
            reasons.append(f"{len(manifest_info['receivers'])} broadcast receivers")

        if native_libs:
            score += 10
            reasons.append("Contains native code")

        report["threat_score"] = min(score, 100)
        report["threat_reasons"] = reasons

        # Display score
        if score >= 75:
            print_finding("CRITICAL", f"THREAT SCORE: {min(score, 100)}/100 — HIGHLY LIKELY MALWARE/SPYWARE")
        elif score >= 50:
            print_finding("WARNING", f"THREAT SCORE: {min(score, 100)}/100 — SUSPICIOUS")
        elif score >= 25:
            print_finding("INFO", f"THREAT SCORE: {min(score, 100)}/100 — MODERATE RISK")
        else:
            print_finding("OK", f"THREAT SCORE: {score}/100 — LOW RISK")

        if reasons:
            print("\n  Reasons:")
            for r in reasons:
                print(f"    - {r}")

        # --- URLs and IPs ---
        print_section("Embedded URLs & IP Addresses")

        all_urls = []
        all_ips = []

        for fname in file_list:
            if fname.endswith((".dex", ".xml", ".json", ".txt", ".properties")):
                try:
                    data = zf.read(fname)
                    urls, ips = extract_urls_and_ips(data)
                    all_urls.extend(urls)
                    all_ips.extend(ips)
                except Exception:
                    pass

        all_urls = list(set(all_urls))[:50]  # Limit output
        all_ips = list(set(all_ips))[:30]

        report["urls"] = all_urls
        report["ips"] = all_ips

        if all_urls:
            print_finding("INFO", f"Found {len(all_urls)} unique URL(s):")
            for url in all_urls[:20]:
                print(f"      {url}")
            if len(all_urls) > 20:
                print(f"      ... and {len(all_urls) - 20} more")

        if all_ips:
            print_finding("INFO", f"Found {len(all_ips)} unique IP address(es):")
            for ip in all_ips[:15]:
                print(f"      {ip}")

        if not all_urls and not all_ips:
            print_finding("INFO", "No embedded URLs or IPs found in scanned files")

    # --- Final Recommendations ---
    print_section("RECOMMENDATIONS")

    print("  1. Check the SHA256 hash on VirusTotal:")
    print(f"     https://www.virustotal.com/gui/search/{hashes['sha256']}")
    print()
    print("  2. DO NOT install this APK on any device")
    print()

    if report.get("threat_score", 0) >= 50:
        print("  3. This APK is SUSPICIOUS. Treat it as malware.")
        print("  4. Delete it from all devices and cloud storage")
        print("  5. If it was installed on any device, that device is compromised")
        print("  6. Check the SECURITY_GUIDE.md for remediation steps")
    else:
        print("  3. While the automated score is low, the binary XML parser")
        print("     may not have captured all permissions. Upload to VirusTotal")
        print("     for a definitive analysis.")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="APK (Android Package) Analyzer — Identify spyware and malware"
    )
    parser.add_argument(
        "apk_file", type=str,
        help="Path to the APK file to analyze"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save report to JSON file"
    )
    args = parser.parse_args()

    if not os.path.exists(args.apk_file):
        print(f"Error: File not found: {args.apk_file}")
        sys.exit(1)

    print("=" * 60)
    print("  APK SECURITY ANALYZER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    report = analyze_apk(args.apk_file)

    # Save report
    output_file = args.output or f"apk_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  Full report saved to: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
