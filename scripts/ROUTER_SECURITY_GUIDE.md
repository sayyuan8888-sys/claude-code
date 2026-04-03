# Router & Network Security Investigation Guide

## CRITICAL: Read This First

If you suspect your home WiFi router has been compromised, **DO NOT** perform any sensitive actions (password changes, banking, email) over this network until it is secured. Use **mobile data only** for all sensitive activities.

---

## Step 1: Immediate Investigation

### 1.1 Run the Automated Audit

```bash
# Run from a trusted device (on the suspect WiFi):
python scripts/router_audit.py --full --output my_audit.json

# Compare with a run on mobile data (for baseline):
# Tether your computer to mobile data, then run again
python scripts/router_audit.py --full --output baseline_audit.json
```

### 1.2 Access Your Router Admin Panel

1. Open a browser and go to your router's admin page:
   - Try: `192.168.1.1`, `192.168.0.1`, `10.0.0.1`, or `192.168.1.254`
   - Check the sticker on the bottom of your router for the correct address

2. Log in with admin credentials:
   - Default credentials are usually on the router sticker
   - If you can't log in with known credentials, the password may have been changed by an attacker

3. **If you can't log in**: This is itself a sign of compromise. Skip to Step 3 (Factory Reset).

### 1.3 Check DNS Settings (MOST IMPORTANT)

**This is the #1 indicator of router compromise.**

1. Find DNS settings in your router admin panel:
   - Usually under: WAN Settings, Internet Settings, or DHCP Settings
   - Look for "DNS Server" or "Domain Name Server"

2. **What to look for:**
   - DNS should be set to "Automatic" (from ISP) or a known provider:
     - `8.8.8.8` / `8.8.4.4` (Google)
     - `1.1.1.1` / `1.0.0.1` (Cloudflare)
     - `9.9.9.9` (Quad9)
   - **RED FLAG**: If DNS is set to any unknown IP address, your DNS has been hijacked
   - **RED FLAG**: If DNS points to an IP in a foreign country you don't recognize

3. **Document the current DNS settings** before making any changes (screenshot)

### 1.4 Check Connected Devices

1. Find the "Connected Devices" or "DHCP Client List" in router admin
2. Document ALL connected devices (IP, MAC address, hostname)
3. **Match each device to a known device in your household:**
   - Phones, tablets, computers, smart TVs, game consoles, IoT devices
   - **RED FLAG**: Any device you cannot identify

### 1.5 Check Port Forwarding Rules

1. Find "Port Forwarding", "Virtual Server", or "NAT" settings
2. Document ALL rules
3. **RED FLAG**: Any port forwarding rule you didn't create
   - Attackers add these to maintain remote access
   - Common attacker ports: 22, 23, 3389, 4443, 5555, 8080

### 1.6 Check Remote Management

1. Find "Remote Management" or "Remote Access" settings
2. **This MUST be DISABLED**
3. **RED FLAG**: If remote management is enabled and you didn't enable it
4. Also check for "Cloud Management" or "DDNS" settings that could provide remote access

### 1.7 Check for Rogue VPN or Proxy

1. Look for VPN Server settings on the router
2. Look for Proxy settings
3. **RED FLAG**: Any VPN server or proxy configuration you didn't set up

### 1.8 Check UPnP Status

1. Find "UPnP" (Universal Plug and Play) settings
2. If enabled, check the UPnP port mapping table
3. **RED FLAG**: Unknown applications with open ports
4. UPnP should generally be **disabled** — it's a common attack vector

---

## Step 2: Document Everything

Before making changes, document (screenshot) the following:
- [ ] DNS settings
- [ ] All connected devices
- [ ] Port forwarding rules
- [ ] Remote management settings
- [ ] VPN/Proxy configurations
- [ ] UPnP mappings
- [ ] WiFi security settings (WPA2/WPA3, password)
- [ ] Firmware version
- [ ] Router model number
- [ ] Admin panel login credentials

Save these screenshots to a device NOT on the suspect network.

---

## Step 3: Factory Reset & Harden the Router

### 3.1 Factory Reset

1. **Find the reset button** on your router (usually a small pinhole on the back)
2. Press and hold it for **10-15 seconds** with a paperclip
3. Wait for the router to fully reboot (2-3 minutes)
4. The router will return to factory default settings

### 3.2 Initial Setup (Secure)

Do this from a **wired connection** (Ethernet cable) if possible.

1. **Change the admin password FIRST:**
   - Use a strong, unique password (at least 16 characters)
   - Do NOT use the default password
   - Write it down and store it physically (not digitally on any compromised device)

2. **Update the firmware:**
   - Check the router manufacturer's website for the latest firmware
   - Go to the firmware update section in admin panel
   - Install the latest version
   - This patches known vulnerabilities

3. **Set DNS to a trusted provider:**
   - Primary: `1.1.1.1` (Cloudflare) or `8.8.8.8` (Google)
   - Secondary: `1.0.0.1` (Cloudflare) or `8.8.4.4` (Google)
   - Or use `9.9.9.9` (Quad9) for malware blocking

4. **Configure WiFi security:**
   - Use **WPA3** if supported, otherwise **WPA2-AES** (NOT WPA or TKIP)
   - Set a **new, strong WiFi password** (at least 20 characters)
   - Change the WiFi network name (SSID) to something new
   - **Do NOT use the old WiFi password**

5. **Disable dangerous features:**
   - [ ] **Remote Management** — DISABLE
   - [ ] **WPS** (WiFi Protected Setup) — DISABLE (easily brute-forced)
   - [ ] **UPnP** — DISABLE
   - [ ] **Telnet access** — DISABLE
   - [ ] **FTP access** — DISABLE
   - [ ] **HNAP** — DISABLE if available
   - [ ] **TR-069 / CWMP** — DISABLE if possible (ISP management protocol, often exploited)
   - [ ] **Ping from WAN** — DISABLE

6. **Enable security features:**
   - [ ] **SPI Firewall** — ENABLE
   - [ ] **DoS Protection** — ENABLE
   - [ ] **Access logging** — ENABLE if available
   - [ ] **Automatic firmware updates** — ENABLE if available

7. **Set up a guest network** (optional but recommended):
   - For IoT devices (smart speakers, cameras, etc.)
   - Isolated from your main network
   - Separate password

### 3.3 Reconnect Devices

1. On each device, **forget the old WiFi network**
2. Connect to the new network name with the new password
3. Verify each device can reach the internet
4. Check the connected devices list in the router to ensure only your devices are present

---

## Step 4: Post-Reset Verification

After hardening, run the audit tool again to verify:

```bash
python scripts/router_audit.py --full --output post_reset_audit.json
```

### Verify:
- [ ] No DNS hijacking detected
- [ ] No SSL interception detected
- [ ] No unexpected open ports
- [ ] Only recognized devices connected
- [ ] Router admin is not accessible from WAN

---

## Step 5: Ongoing Monitoring

### Weekly Checks
1. Log into router admin and review connected devices
2. Check DNS settings haven't been changed
3. Review port forwarding rules
4. Check for firmware updates

### Set Up Alerts (if your router supports it)
- New device connection alerts
- Admin login alerts
- Configuration change alerts

### Consider Upgrading
If your current router is old or from a brand with known security issues, consider upgrading to:
- A router with automatic security updates
- A router with built-in threat detection (e.g., ASUS AiProtection, Netgear Armor)
- A router that supports WPA3

---

## Known Router Vulnerabilities to Check

If you identified your router model, search for:
`[Your Router Model] vulnerability CVE`

Common router attack vectors:
1. **Default credentials** — Most common. If you never changed the admin password, attackers can walk right in.
2. **UPnP exploits** — Allows malware to open ports without authentication
3. **TR-069/CWMP** — ISP management protocol, exploited to change DNS
4. **DNS rebinding** — Allows websites to access your router admin panel
5. **CSRF attacks** — Malicious web pages that change router settings via your browser
6. **Firmware backdoors** — Some cheap routers have hardcoded backdoor accounts

---

## When to Get Professional Help

Contact a cybersecurity professional if:
- You found evidence of DNS hijacking AND account compromise
- The attacker appears to be targeting you specifically
- You've been locked out of important accounts
- You suspect financial fraud
- The compromise persists after factory reset (could indicate firmware-level rootkit)
- You find configuration profiles or MDM enrollment on your iPhone that you didn't install

### Resources
- **Apple Support**: If you find MDM profiles or enterprise certificates on your iPhone
- **Your ISP**: If the router firmware appears to be modified
- **Local law enforcement**: If you believe you're being stalked or targeted
- **CERT/CISA**: For sophisticated attacks — https://www.cisa.gov/report
