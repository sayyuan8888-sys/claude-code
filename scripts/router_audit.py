#!/usr/bin/env python3
"""
Router & Network Security Audit Tool

Investigates home network for signs of compromise:
- DNS hijacking detection
- Rogue device scanning
- Router port scanning
- SSL/TLS interception detection
- Default gateway identification

Usage:
    python router_audit.py [--full] [--output report.json]

IMPORTANT: Run this from a device you trust, ideally on mobile data first
to establish a baseline, then on the suspect WiFi to compare.
"""

import argparse
import json
import os
import platform
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime


# --- Utility ---

def run_cmd(cmd, timeout=10):
    """Run a shell command and return stdout, stderr, returncode."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
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


# --- Phase 1: Gateway Discovery ---

def discover_gateway():
    """Find the default gateway (router) IP address."""
    print_section("Phase 1: Default Gateway Discovery")

    gateway = None
    system = platform.system().lower()

    if system == "darwin":  # macOS
        out, _, rc = run_cmd("netstat -rn | grep default | head -1 | awk '{print $2}'")
        if rc == 0 and out:
            gateway = out.split()[0] if out.split() else None
    elif system == "linux":
        out, _, rc = run_cmd("ip route | grep default | head -1 | awk '{print $3}'")
        if rc == 0 and out:
            gateway = out
    else:  # Windows
        out, _, rc = run_cmd("ipconfig | findstr /i \"Default Gateway\"")
        if rc == 0 and out:
            match = re.search(r'(\d+\.\d+\.\d+\.\d+)', out)
            if match:
                gateway = match.group(1)

    if not gateway:
        # Fallback: try common gateway IPs
        for candidate in ["192.168.1.1", "192.168.0.1", "10.0.0.1", "192.168.1.254"]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex((candidate, 80))
                sock.close()
                if result == 0:
                    gateway = candidate
                    break
            except Exception:
                continue

    if gateway:
        print_finding("INFO", f"Default gateway: {gateway}")
    else:
        print_finding("WARNING", "Could not determine default gateway")

    return gateway


# --- Phase 2: DNS Hijack Detection ---

def check_dns_hijacking():
    """Compare DNS resolution from local resolver vs trusted public DNS."""
    print_section("Phase 2: DNS Hijack Detection")

    test_domains = [
        "google.com",
        "apple.com",
        "microsoft.com",
        "cloudflare.com",
        "github.com",
    ]

    trusted_dns_servers = ["8.8.8.8", "1.1.1.1"]
    findings = []
    hijack_detected = False

    for domain in test_domains:
        # Resolve using system DNS (potentially compromised router)
        try:
            local_ips = sorted(
                set(addr[4][0] for addr in socket.getaddrinfo(domain, None))
            )
        except socket.gaierror:
            local_ips = []
            print_finding("WARNING", f"Failed to resolve {domain} via local DNS")
            continue

        # Resolve using trusted DNS via nslookup
        for dns_server in trusted_dns_servers:
            out, _, rc = run_cmd(f"nslookup {domain} {dns_server}", timeout=5)
            if rc != 0:
                continue

            trusted_ips = []
            for line in out.split("\n"):
                match = re.search(r'Address:\s*(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    ip = match.group(1)
                    if ip != dns_server:
                        trusted_ips.append(ip)

            trusted_ips = sorted(set(trusted_ips))

            if local_ips and trusted_ips:
                # Check if there's ANY overlap (CDNs may return different IPs)
                overlap = set(local_ips) & set(trusted_ips)
                if not overlap:
                    # Different IPs could be CDN, but flag it
                    print_finding(
                        "WARNING",
                        f"{domain}: Local DNS={local_ips} vs {dns_server}={trusted_ips} - MISMATCH"
                    )
                    findings.append({
                        "domain": domain,
                        "local": local_ips,
                        "trusted": trusted_ips,
                        "dns_server": dns_server,
                    })
                    hijack_detected = True
                else:
                    print_finding("OK", f"{domain}: DNS resolution consistent")
            break  # Only need one trusted server to compare

    if not hijack_detected:
        print_finding("OK", "No DNS hijacking detected for test domains")
    else:
        print_finding(
            "CRITICAL",
            "DNS resolution mismatches detected! Your router DNS may be hijacked."
        )
        print_finding(
            "CRITICAL",
            "Log into your router and check DNS settings immediately."
        )

    return {"hijack_detected": hijack_detected, "mismatches": findings}


# --- Phase 3: Connected Device Scanner ---

def scan_connected_devices(gateway):
    """Use ARP table to list all devices on the local network."""
    print_section("Phase 3: Connected Device Scanner")

    devices = []
    system = platform.system().lower()

    # Get ARP table
    if system == "windows":
        out, _, rc = run_cmd("arp -a")
    else:
        out, _, rc = run_cmd("arp -a")

    if rc != 0 or not out:
        # Try ip neigh on Linux
        out, _, rc = run_cmd("ip neigh show")

    if not out:
        print_finding("WARNING", "Could not read ARP table. May need elevated privileges.")
        return devices

    # Parse ARP entries
    for line in out.split("\n"):
        # Match patterns like: 192.168.1.5 (incomplete) or with MAC
        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
        mac_match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', line)

        if ip_match:
            ip = ip_match.group(0)
            mac = mac_match.group(0) if mac_match else "unknown"

            # Try to get hostname
            try:
                hostname = socket.gethostbyaddr(ip)[0]
            except (socket.herror, socket.gaierror, OSError):
                hostname = "unknown"

            devices.append({"ip": ip, "mac": mac, "hostname": hostname})

    print_finding("INFO", f"Found {len(devices)} devices on the network:")
    print()
    print(f"    {'IP Address':<18} {'MAC Address':<20} {'Hostname'}")
    print(f"    {'-'*18} {'-'*20} {'-'*30}")
    for dev in devices:
        is_gateway = " (GATEWAY)" if dev["ip"] == gateway else ""
        print(f"    {dev['ip']:<18} {dev['mac']:<20} {dev['hostname']}{is_gateway}")

    print()
    print_finding(
        "INFO",
        "Review the list above. Flag any devices you don't recognize."
    )
    print_finding(
        "INFO",
        "Unknown devices with active connections could be rogue/attacker devices."
    )

    return devices


# --- Phase 4: Router Port Scan ---

def scan_router_ports(gateway):
    """Scan common ports on the router to identify exposed services."""
    print_section("Phase 4: Router Port Scan")

    if not gateway:
        print_finding("WARNING", "No gateway IP — skipping port scan")
        return []

    # Common ports that should/shouldn't be open on a router
    ports = {
        21: ("FTP", "CRITICAL", "FTP is insecure — should be disabled"),
        22: ("SSH", "WARNING", "SSH open — verify this is intentional"),
        23: ("Telnet", "CRITICAL", "Telnet is insecure — MUST be disabled"),
        53: ("DNS", "INFO", "DNS service (normal for router)"),
        80: ("HTTP Admin", "INFO", "Router web admin panel"),
        443: ("HTTPS Admin", "INFO", "Router web admin panel (HTTPS)"),
        445: ("SMB", "CRITICAL", "SMB file sharing — should NOT be on router"),
        548: ("AFP", "WARNING", "Apple Filing Protocol — unusual on router"),
        1080: ("SOCKS Proxy", "CRITICAL", "SOCKS proxy — sign of compromise"),
        1723: ("PPTP VPN", "WARNING", "VPN server — verify this is intentional"),
        3128: ("HTTP Proxy", "CRITICAL", "HTTP proxy — sign of MITM/compromise"),
        3389: ("RDP", "CRITICAL", "Remote Desktop — should NOT be on router"),
        4443: ("Alt HTTPS", "WARNING", "Alternate HTTPS — verify this is intentional"),
        5555: ("ADB", "CRITICAL", "Android Debug Bridge — sign of compromise"),
        7547: ("TR-069", "CRITICAL", "ISP management — can be exploited"),
        8080: ("Alt HTTP", "WARNING", "Alternate HTTP — could be malicious proxy"),
        8443: ("Alt HTTPS", "WARNING", "Alternate HTTPS service"),
        8888: ("Alt HTTP", "WARNING", "Alternate HTTP — could be malicious service"),
        9090: ("Web Panel", "WARNING", "Unknown web panel"),
    }

    open_ports = []
    print_finding("INFO", f"Scanning {len(ports)} common ports on {gateway}...")
    print()

    for port, (service, severity, note) in sorted(ports.items()):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            result = sock.connect_ex((gateway, port))
            sock.close()

            if result == 0:
                open_ports.append({"port": port, "service": service, "severity": severity})
                print_finding(severity, f"Port {port} ({service}) is OPEN — {note}")
        except Exception:
            pass

    if not open_ports:
        print_finding("OK", "No common ports are open (router may have firewall)")
    else:
        critical_ports = [p for p in open_ports if p["severity"] == "CRITICAL"]
        if critical_ports:
            print()
            print_finding(
                "CRITICAL",
                f"{len(critical_ports)} dangerous port(s) open! "
                "This strongly suggests compromise."
            )

    return open_ports


# --- Phase 5: SSL/TLS Interception Test ---

def check_ssl_interception():
    """Check if HTTPS connections are being intercepted (MITM)."""
    print_section("Phase 5: SSL/TLS Interception Detection")

    test_hosts = [
        ("www.google.com", 443),
        ("www.apple.com", 443),
        ("github.com", 443),
    ]

    intercepted = False

    for host, port in test_hosts:
        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    issuer = dict(x[0] for x in cert.get("issuer", []))
                    subject = dict(x[0] for x in cert.get("subject", []))

                    issuer_org = issuer.get("organizationName", "Unknown")
                    subject_cn = subject.get("commonName", "Unknown")

                    # Known legitimate CAs
                    legitimate_issuers = [
                        "Google Trust Services",
                        "DigiCert",
                        "Let's Encrypt",
                        "GlobalSign",
                        "Sectigo",
                        "GeoTrust",
                        "Comodo",
                        "Amazon",
                        "Apple",
                        "Microsoft",
                        "Baltimore",
                        "Starfield",
                        "Entrust",
                        "ISRG",
                        "Cloudflare",
                    ]

                    is_legit = any(
                        known.lower() in issuer_org.lower()
                        for known in legitimate_issuers
                    )

                    if is_legit:
                        print_finding("OK", f"{host}: Certificate from '{issuer_org}' (legitimate)")
                    else:
                        print_finding(
                            "CRITICAL",
                            f"{host}: Certificate from '{issuer_org}' — "
                            "NOT a known CA! Possible MITM interception!"
                        )
                        intercepted = True

        except ssl.SSLCertVerificationError as e:
            print_finding(
                "CRITICAL",
                f"{host}: SSL verification FAILED — {e}. Possible MITM!"
            )
            intercepted = True
        except Exception as e:
            print_finding("WARNING", f"{host}: Connection failed — {e}")

    if intercepted:
        print()
        print_finding(
            "CRITICAL",
            "SSL interception detected! Someone may be reading your encrypted traffic."
        )
        print_finding(
            "CRITICAL",
            "Do NOT use this network for sensitive activities until resolved."
        )

    return intercepted


# --- Phase 6: Router Admin Fingerprint ---

def fingerprint_router(gateway):
    """Try to identify the router model/firmware from its admin page."""
    print_section("Phase 6: Router Identification")

    if not gateway:
        print_finding("WARNING", "No gateway IP — skipping router fingerprint")
        return {}

    info = {}

    for protocol in ["http", "https"]:
        url = f"{protocol}://{gateway}/"
        try:
            if protocol == "https":
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=5, context=ctx)
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=5)

            # Check headers
            server = resp.headers.get("Server", "")
            if server:
                info["server"] = server
                print_finding("INFO", f"Router web server: {server}")

            # Read first chunk of HTML for clues
            body = resp.read(8192).decode("utf-8", errors="ignore").lower()

            # Look for router brand indicators
            brands = {
                "netgear": "Netgear",
                "tp-link": "TP-Link",
                "tplink": "TP-Link",
                "linksys": "Linksys",
                "asus": "ASUS",
                "d-link": "D-Link",
                "dlink": "D-Link",
                "huawei": "Huawei",
                "zte": "ZTE",
                "mikrotik": "MikroTik",
                "ubiquiti": "Ubiquiti",
                "arris": "Arris",
                "motorola": "Motorola",
                "cisco": "Cisco",
                "technicolor": "Technicolor",
                "sagemcom": "Sagemcom",
                "comtrend": "Comtrend",
                "actiontec": "Actiontec",
            }

            for keyword, brand in brands.items():
                if keyword in body:
                    info["brand"] = brand
                    print_finding("INFO", f"Router brand detected: {brand}")
                    break

            # Check for firmware version strings
            fw_match = re.search(
                r'(firmware|version|fw)[:\s]*v?(\d+[\.\d]+)',
                body
            )
            if fw_match:
                info["firmware"] = fw_match.group(0)
                print_finding("INFO", f"Firmware hint: {fw_match.group(0)}")

            break  # Got what we need

        except Exception:
            continue

    if not info:
        print_finding("INFO", "Could not fingerprint router via web admin")
        print_finding("INFO", "Try accessing your router admin panel manually")

    # Check for remote management
    print()
    print_finding("INFO", "Checking for WAN-side remote management...")
    try:
        # Get public IP
        pub_ip, _, rc = run_cmd(
            "python3 -c \"import urllib.request; "
            "print(urllib.request.urlopen('https://api.ipify.org', timeout=5).read().decode())\"",
            timeout=10
        )
        if rc == 0 and pub_ip:
            info["public_ip"] = pub_ip
            print_finding("INFO", f"Your public IP: {pub_ip}")

            # Check if router admin is accessible from WAN (it shouldn't be)
            for port in [80, 443, 8080]:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    result = sock.connect_ex((pub_ip, port))
                    sock.close()
                    if result == 0:
                        print_finding(
                            "CRITICAL",
                            f"Port {port} is reachable on your PUBLIC IP! "
                            "Remote management may be enabled."
                        )
                except Exception:
                    pass
    except Exception:
        print_finding("INFO", "Could not check for remote management")

    return info


# --- Phase 7: Check Router DNS Settings ---

def check_router_dns_config():
    """Check what DNS servers the system is using (from router DHCP)."""
    print_section("Phase 7: DNS Configuration Check")

    system = platform.system().lower()
    dns_servers = []

    if system == "darwin":
        out, _, _ = run_cmd("scutil --dns | grep nameserver | head -10")
        if out:
            for line in out.split("\n"):
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    dns_servers.append(match.group(1))
    elif system == "linux":
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.strip().startswith("nameserver"):
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if match:
                            dns_servers.append(match.group(1))
        except FileNotFoundError:
            pass
        # Also check systemd-resolved
        out, _, _ = run_cmd("resolvectl status 2>/dev/null | grep 'DNS Servers' | head -5")
        if out:
            for line in out.split("\n"):
                for match in re.finditer(r'(\d+\.\d+\.\d+\.\d+)', line):
                    dns_servers.append(match.group(1))
    else:
        out, _, _ = run_cmd("ipconfig /all | findstr /i \"DNS Servers\"")
        if out:
            for match in re.finditer(r'(\d+\.\d+\.\d+\.\d+)', out):
                dns_servers.append(match.group(1))

    dns_servers = list(dict.fromkeys(dns_servers))  # deduplicate preserving order

    # Known safe DNS servers
    safe_dns = {
        "8.8.8.8": "Google Public DNS",
        "8.8.4.4": "Google Public DNS",
        "1.1.1.1": "Cloudflare DNS",
        "1.0.0.1": "Cloudflare DNS",
        "9.9.9.9": "Quad9 DNS",
        "149.112.112.112": "Quad9 DNS",
        "208.67.222.222": "OpenDNS",
        "208.67.220.220": "OpenDNS",
    }

    if dns_servers:
        print_finding("INFO", f"Configured DNS servers: {dns_servers}")
        for dns in dns_servers:
            if dns in safe_dns:
                print_finding("OK", f"  {dns} — {safe_dns[dns]} (trusted)")
            elif dns.startswith(("192.168.", "10.", "172.16.")):
                print_finding("INFO", f"  {dns} — Local/router DNS (check router settings)")
            else:
                print_finding(
                    "WARNING",
                    f"  {dns} — Unknown DNS server! Verify this is your ISP's DNS."
                )
                print_finding(
                    "WARNING",
                    "  If you don't recognize this DNS, it may be hijacked."
                )
    else:
        print_finding("WARNING", "Could not determine DNS servers")

    return dns_servers


# --- Report Generation ---

def generate_report(results, output_file=None):
    """Generate a JSON report of all findings."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "platform": platform.system(),
        "hostname": socket.gethostname(),
        "results": results,
    }

    if output_file:
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\n  Report saved to: {output_file}")

    return report


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Router & Network Security Audit Tool",
        epilog=(
            "IMPORTANT: Run on mobile data first to establish a baseline, "
            "then on suspect WiFi to compare results."
        ),
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run all checks including slower scans"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Save report to JSON file"
    )
    parser.add_argument(
        "--gateway", "-g", type=str, default=None,
        help="Manually specify gateway IP (skip auto-discovery)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ROUTER & NETWORK SECURITY AUDIT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    print("  WARNING: For best results, run this tool TWICE:")
    print("  1. First on MOBILE DATA (trusted baseline)")
    print("  2. Then on your HOME WIFI (suspect network)")
    print("  Compare the results to identify discrepancies.")

    results = {}

    # Phase 1: Gateway Discovery
    gateway = args.gateway or discover_gateway()
    results["gateway"] = gateway

    # Phase 2: DNS Hijack Detection
    results["dns"] = check_dns_hijacking()

    # Phase 3: Connected Devices
    results["devices"] = scan_connected_devices(gateway)

    # Phase 4: Router Port Scan
    results["ports"] = scan_router_ports(gateway)

    # Phase 5: SSL Interception
    results["ssl_intercepted"] = check_ssl_interception()

    # Phase 6: Router Fingerprint
    if args.full:
        results["router_info"] = fingerprint_router(gateway)

    # Phase 7: DNS Config Check
    results["dns_config"] = check_router_dns_config()

    # Summary
    print_section("SUMMARY")

    critical_count = 0
    if results["dns"].get("hijack_detected"):
        print_finding("CRITICAL", "DNS hijacking detected")
        critical_count += 1
    if results.get("ssl_intercepted"):
        print_finding("CRITICAL", "SSL/TLS interception detected")
        critical_count += 1
    if any(p["severity"] == "CRITICAL" for p in results.get("ports", [])):
        print_finding("CRITICAL", "Dangerous ports open on router")
        critical_count += 1

    if critical_count > 0:
        print()
        print_finding(
            "CRITICAL",
            f"{critical_count} critical finding(s)! Your network is likely compromised."
        )
        print()
        print("  RECOMMENDED IMMEDIATE ACTIONS:")
        print("  1. Disconnect all devices from this WiFi immediately")
        print("  2. Use mobile data for all sensitive activities")
        print("  3. Do NOT change passwords over this network")
        print("  4. Factory reset your router")
        print("  5. See ROUTER_SECURITY_GUIDE.md for full remediation steps")
    else:
        print_finding("OK", "No critical findings detected")
        print_finding("INFO", "Run with --full flag for deeper analysis")

    # Generate report
    default_output = f"router_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file = args.output or default_output
    generate_report(results, output_file)

    print()
    print("=" * 60)
    print("  Audit complete. Review findings above carefully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
