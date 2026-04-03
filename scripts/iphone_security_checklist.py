#!/usr/bin/env python3
"""
iPhone Security Checklist — Interactive CLI Tool

Walks you through a comprehensive security audit of an iPhone,
documenting findings and generating a report.

Usage:
    python iphone_security_checklist.py [--output report.json]
"""

import argparse
import json
import os
import sys
from datetime import datetime


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title, subtitle=""):
    print(f"\n{'='*60}")
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print(f"{'='*60}\n")


def ask_yes_no(question, default=None):
    """Ask a yes/no question and return True/False."""
    suffix = " [Y/n]: " if default is True else " [y/N]: " if default is False else " [y/n]: "
    while True:
        answer = input(f"  {question}{suffix}").strip().lower()
        if not answer and default is not None:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please answer y or n.")


def ask_choice(question, options):
    """Ask a multiple choice question."""
    print(f"  {question}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt}")
    while True:
        try:
            answer = int(input("  Enter number: ").strip())
            if 1 <= answer <= len(options):
                return answer - 1, options[answer - 1]
        except (ValueError, EOFError):
            pass
        print(f"  Please enter a number between 1 and {len(options)}.")


def ask_text(question, allow_empty=True):
    """Ask for text input."""
    answer = input(f"  {question}: ").strip()
    if not allow_empty and not answer:
        return ask_text(question, allow_empty)
    return answer


def print_alert(severity, message):
    icons = {"CRITICAL": "[!!!]", "WARNING": "[!!]", "INFO": "[i]", "OK": "[OK]"}
    icon = icons.get(severity, "[?]")
    print(f"\n  {icon} {severity}: {message}")


def run_checklist():
    """Run the interactive security checklist."""
    findings = []
    report = {
        "timestamp": datetime.now().isoformat(),
        "device": {},
        "checks": [],
    }

    print_header(
        "iPHONE SECURITY CHECKLIST",
        "Walk through each step on the iPhone being investigated"
    )

    print("  This checklist will guide you through checking your iPhone")
    print("  for signs of compromise. Have the iPhone nearby and follow")
    print("  each step carefully.\n")
    print("  IMPORTANT: If this is the compromised device, do password")
    print("  changes from a DIFFERENT trusted device.\n")

    input("  Press Enter to begin...")

    # --- Device Info ---
    print_header("Section 1: Device Information")

    device_model = ask_text("iPhone model (e.g., iPhone 16 Pro)")
    ios_version = ask_text("iOS version (Settings > General > About > iOS Version)")
    report["device"]["model"] = device_model
    report["device"]["ios_version"] = ios_version

    # --- Configuration Profiles ---
    print_header("Section 2: Configuration Profiles (CRITICAL)")
    print("  Go to: Settings > General > VPN & Device Management")
    print("  (On older iOS: Settings > General > Profiles & Device Management)\n")

    has_profiles = ask_yes_no("Do you see any configuration profiles listed?", default=False)
    if has_profiles:
        print_alert("CRITICAL", "Configuration profiles found!")
        print("  Configuration profiles can give an attacker deep control over your device.")
        print("  They can install certificates, VPNs, and change security settings.\n")

        profiles_text = ask_text(
            "List all profile names you see (comma-separated)"
        )
        profiles = [p.strip() for p in profiles_text.split(",") if p.strip()]

        for profile in profiles:
            is_known = ask_yes_no(f"Did YOU or your employer install '{profile}'?")
            if not is_known:
                findings.append({
                    "severity": "CRITICAL",
                    "category": "Configuration Profile",
                    "detail": f"Unknown profile: {profile}",
                    "action": "Remove this profile immediately (tap it > Remove Profile)",
                })
                print_alert("CRITICAL", f"Unknown profile '{profile}' — REMOVE IT NOW")
                print(f"    Tap on '{profile}' > Remove Profile > Enter passcode")
    else:
        print_alert("OK", "No configuration profiles found (good)")

    report["checks"].append({
        "section": "Configuration Profiles",
        "has_profiles": has_profiles,
        "findings": [f for f in findings if f["category"] == "Configuration Profile"],
    })

    # --- MDM Enrollment ---
    print_header("Section 3: MDM (Mobile Device Management)")
    print("  Still in: Settings > General > VPN & Device Management\n")

    has_mdm = ask_yes_no(
        "Do you see 'Device Management' or 'Mobile Device Management' section?",
        default=False
    )
    if has_mdm:
        is_work = ask_yes_no("Is this a work/company device with intentional MDM?")
        if not is_work:
            findings.append({
                "severity": "CRITICAL",
                "category": "MDM",
                "detail": "Unknown MDM enrollment detected",
                "action": "This gives someone remote control of your device. Factory reset required.",
            })
            print_alert(
                "CRITICAL",
                "Unknown MDM enrollment! Someone can remotely control this device."
            )
            print("  This is a serious compromise indicator.")
            print("  The device should be factory reset (see SECURITY_GUIDE.md)")
    else:
        print_alert("OK", "No MDM enrollment detected (good)")

    report["checks"].append({
        "section": "MDM",
        "has_mdm": has_mdm,
        "findings": [f for f in findings if f["category"] == "MDM"],
    })

    # --- Installed Apps ---
    print_header("Section 4: Installed Apps")
    print("  Go to: Settings > General > iPhone Storage")
    print("  Scroll through the list of ALL installed apps.\n")

    unknown_apps = ask_yes_no("Do you see any apps you don't recognize?")
    if unknown_apps:
        apps_text = ask_text("List the unknown app names (comma-separated)")
        apps = [a.strip() for a in apps_text.split(",") if a.strip()]

        known_spyware = [
            "mspy", "flexispy", "cocospy", "spyic", "spyzie", "hoverwatch",
            "eyezy", "umobix", "xnspy", "clevguard", "kidsguard", "thetruthspy",
            "spyfone", "cerberus", "trackview", "life360",
        ]

        for app in apps:
            is_spyware = any(sw in app.lower() for sw in known_spyware)
            severity = "CRITICAL" if is_spyware else "WARNING"
            findings.append({
                "severity": severity,
                "category": "Unknown App",
                "detail": f"Unrecognized app: {app}" + (" (KNOWN SPYWARE)" if is_spyware else ""),
                "action": f"Delete '{app}' — press and hold > Delete App",
            })
            if is_spyware:
                print_alert("CRITICAL", f"'{app}' matches known spyware! Delete immediately.")
            else:
                print_alert("WARNING", f"Unknown app '{app}' — investigate and delete if not recognized")

    # Check for Cydia/Sileo (jailbreak indicators)
    print()
    has_jailbreak_apps = ask_yes_no(
        "Do you see 'Cydia', 'Sileo', 'Zebra', 'Installer', or 'Unc0ver'?",
        default=False
    )
    if has_jailbreak_apps:
        findings.append({
            "severity": "CRITICAL",
            "category": "Jailbreak",
            "detail": "Jailbreak indicators found (Cydia/Sileo/etc.)",
            "action": "Device has been jailbroken. Factory reset required.",
        })
        print_alert("CRITICAL", "Device appears to be JAILBROKEN!")
        print("  A jailbroken iPhone has no security protections.")
        print("  Factory reset is REQUIRED. See SECURITY_GUIDE.md")

    report["checks"].append({
        "section": "Installed Apps",
        "has_unknown_apps": unknown_apps,
        "has_jailbreak": has_jailbreak_apps,
    })

    # --- Privacy Permissions ---
    print_header("Section 5: Privacy & Security Permissions")
    print("  Go to: Settings > Privacy & Security\n")

    privacy_checks = [
        ("Location Services", "Which apps have 'Always' location access?"),
        ("Microphone", "Which apps have microphone access?"),
        ("Camera", "Which apps have camera access?"),
        ("Contacts", "Which apps have contacts access?"),
        ("Photos", "Which apps have full photo library access?"),
    ]

    for permission, question in privacy_checks:
        print(f"\n  Check: Settings > Privacy & Security > {permission}")
        has_suspicious = ask_yes_no(
            f"Any apps with {permission.lower()} access that shouldn't have it?"
        )
        if has_suspicious:
            apps_text = ask_text(f"Which apps? (comma-separated)")
            for app in [a.strip() for a in apps_text.split(",") if a.strip()]:
                findings.append({
                    "severity": "WARNING",
                    "category": "Privacy Permission",
                    "detail": f"Suspicious {permission.lower()} access: {app}",
                    "action": f"Revoke {permission.lower()} access for '{app}'",
                })
                print_alert("WARNING", f"Revoke {permission.lower()} for '{app}'")

    report["checks"].append({"section": "Privacy Permissions"})

    # --- Certificates ---
    print_header("Section 6: Certificate Trust Settings")
    print("  Go to: Settings > General > About > Certificate Trust Settings\n")

    has_custom_certs = ask_yes_no(
        "Do you see any certificates listed under 'Enable Full Trust for Root Certificates'?",
        default=False
    )
    if has_custom_certs:
        findings.append({
            "severity": "CRITICAL",
            "category": "Certificates",
            "detail": "Custom root certificates installed",
            "action": "These allow MITM attacks. Disable all unknown certificates.",
        })
        print_alert(
            "CRITICAL",
            "Custom certificates found! These allow someone to intercept your encrypted traffic."
        )
        print("  Disable ALL certificates you don't recognize.")
        print("  If unsure, disable all of them.")
    else:
        print_alert("OK", "No custom certificates found (good)")

    report["checks"].append({
        "section": "Certificates",
        "has_custom_certs": has_custom_certs,
    })

    # --- VPN ---
    print_header("Section 7: VPN Configuration")
    print("  Go to: Settings > General > VPN & Device Management > VPN\n")

    has_vpn = ask_yes_no("Are any VPN configurations listed?")
    if has_vpn:
        vpn_known = ask_yes_no("Did you install all listed VPN configurations?")
        if not vpn_known:
            findings.append({
                "severity": "CRITICAL",
                "category": "VPN",
                "detail": "Unknown VPN configuration found",
                "action": "Delete unknown VPN configs. They can route all traffic through an attacker.",
            })
            print_alert("CRITICAL", "Unknown VPN configuration — delete it!")
            print("  Tap the (i) next to each unknown VPN > Delete VPN")

    report["checks"].append({"section": "VPN", "has_vpn": has_vpn})

    # --- Mail Accounts ---
    print_header("Section 8: Email Accounts")
    print("  Go to: Settings > Mail > Accounts\n")

    has_unknown_mail = ask_yes_no("Are there any email accounts you didn't add?")
    if has_unknown_mail:
        findings.append({
            "severity": "CRITICAL",
            "category": "Email",
            "detail": "Unknown email account added to device",
            "action": "Delete the unknown account. It may be forwarding your data.",
        })
        print_alert("CRITICAL", "Unknown email account — delete it immediately!")

    report["checks"].append({"section": "Email Accounts"})

    # --- Screen Time / App Usage ---
    print_header("Section 9: Screen Time Analysis")
    print("  Go to: Settings > Screen Time > See All App & Website Activity\n")

    has_unusual_activity = ask_yes_no(
        "Do you see high usage for apps you don't recognize?"
    )
    if has_unusual_activity:
        findings.append({
            "severity": "WARNING",
            "category": "Screen Time",
            "detail": "Unusual app activity detected in Screen Time",
            "action": "Note the app names and usage times. Investigate these apps.",
        })

    report["checks"].append({"section": "Screen Time"})

    # --- Apple ID Devices ---
    print_header("Section 10: Apple ID Devices")
    print("  Go to: Settings > [Your Name] > scroll down to see all devices\n")

    has_unknown_devices = ask_yes_no(
        "Are there any devices listed that you don't recognize?"
    )
    if has_unknown_devices:
        findings.append({
            "severity": "CRITICAL",
            "category": "Apple ID",
            "detail": "Unknown device on Apple ID",
            "action": "Tap the unknown device > Remove from Account. Then change your Apple ID password.",
        })
        print_alert("CRITICAL", "Unknown device on your Apple ID!")
        print("  Remove it: Tap the device > Remove from Account")
        print("  Then change your Apple ID password from a trusted device.")

    report["checks"].append({"section": "Apple ID Devices"})

    # --- Summary ---
    print_header("CHECKLIST COMPLETE — SUMMARY")

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]

    if critical:
        print_alert("CRITICAL", f"{len(critical)} CRITICAL finding(s):")
        for f in critical:
            print(f"    -> {f['detail']}")
            print(f"       Action: {f['action']}")
        print()

    if warnings:
        print_alert("WARNING", f"{len(warnings)} warning(s):")
        for f in warnings:
            print(f"    -> {f['detail']}")
        print()

    if not critical and not warnings:
        print_alert("OK", "No suspicious findings detected!")
        print("  Your iPhone appears clean based on this checklist.")
        print("  For extra safety, consider enabling Lockdown Mode.")

    if critical:
        print("\n  RECOMMENDED NEXT STEPS:")
        print("  1. Follow the actions listed above for each CRITICAL finding")
        print("  2. Change your Apple ID password from a TRUSTED device")
        print("  3. If MDM or jailbreak detected: Factory reset (DFU mode)")
        print("  4. See SECURITY_GUIDE.md for complete remediation steps")
        print("  5. Consider enabling Lockdown Mode after remediation")

    report["summary"] = {
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "findings": findings,
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="iPhone Security Checklist")
    parser.add_argument(
        "--output", "-o", type=str,
        default=f"iphone_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        help="Save report to JSON file"
    )
    args = parser.parse_args()

    try:
        report = run_checklist()
    except (KeyboardInterrupt, EOFError):
        print("\n\n  Checklist interrupted. Partial results not saved.")
        sys.exit(1)

    # Save report
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n  Report saved to: {args.output}")
    print("  Keep this report for your records.\n")


if __name__ == "__main__":
    main()
