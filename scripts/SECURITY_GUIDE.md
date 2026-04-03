# Device Security Hardening Guide

## Comprehensive guide for securing your devices after a suspected network compromise

---

## BEFORE YOU START

> **ALL password changes and sensitive actions MUST be done on MOBILE DATA, NOT your home WiFi, until the router is secured.** See ROUTER_SECURITY_GUIDE.md first.

### What you'll need:
- A trusted device (ideally one that was NOT on the compromised network)
- Mobile data connection (not WiFi)
- 1-2 hours of uninterrupted time
- Pen and paper for notes (not a digital document on a compromised device)

---

## Phase 1: Immediate Lockdown (Do RIGHT NOW)

### 1.1 Disconnect from Home WiFi
- On ALL devices: Turn off WiFi
- Use mobile/cellular data only
- Do NOT reconnect to home WiFi until router is secured (see ROUTER_SECURITY_GUIDE.md)

### 1.2 Enable Airplane Mode on Compromised Device
If a specific device is known to be compromised:
1. Enable Airplane Mode
2. Then re-enable mobile data only (keep WiFi OFF)
3. This prevents the device from communicating over WiFi while you investigate

### 1.3 Change Apple ID Password (FROM A TRUSTED DEVICE)
1. Go to https://appleid.apple.com from a DIFFERENT trusted device
2. Sign in and change your password
3. Choose "Sign out of all devices" when prompted
4. Use a strong, unique password you've never used before (16+ characters)

### 1.4 Enable Two-Factor Authentication Everywhere
Priority order:
1. **Apple ID** — Settings > [Your Name] > Sign-In & Security > Two-Factor Authentication
2. **Primary email** (Gmail/Outlook) — use an authenticator app, NOT SMS
3. **Banking apps** — enable biometric + 2FA
4. **Social media** — Instagram, Facebook, Twitter/X, etc.
5. **Messaging** — WhatsApp (two-step verification), Telegram, Signal

### 1.5 Revoke All Active Sessions
For EACH account:
- **Apple ID**: https://appleid.apple.com > Devices > Remove unknown devices
- **Google**: https://myaccount.google.com/device-activity
- **Microsoft**: https://account.microsoft.com/devices
- **Facebook**: Settings > Security > Where You're Logged In
- **Instagram**: Settings > Security > Login Activity
- **WhatsApp**: Settings > Linked Devices > Remove all
- **Telegram**: Settings > Devices > Terminate All Other Sessions

---

## Phase 2: iPhone Investigation

### 2.1 Check for Configuration Profiles
**This is the #1 thing to check on the iPhone.**

1. Go to: **Settings > General > VPN & Device Management**
2. If you see ANY profiles listed:
   - Tap each one to see details
   - If you didn't install it and it's not from your employer: **DELETE IT**
   - Tap the profile > "Remove Profile" > Enter passcode
3. If you don't see "VPN & Device Management" — that's normal (means no profiles installed)

**Why this matters:** Configuration profiles can silently install root certificates (enabling traffic interception), VPN configs (routing your traffic through an attacker), and change device settings.

### 2.2 Check for MDM Enrollment
Still in **Settings > General > VPN & Device Management**:
- If you see "Mobile Device Management" or "Device Management" section
- And this is NOT a work/company device
- **Your device is under someone else's control**
- MDM allows remote: app installation, data wiping, location tracking, configuration changes
- **Action: Factory reset is required** (see Phase 5)

### 2.3 Check Certificate Trust Settings
1. Go to: **Settings > General > About > Certificate Trust Settings**
2. Under "Enable Full Trust for Root Certificates":
   - You should see NO custom certificates enabled
   - If you see any: **DISABLE THEM ALL**
   - Custom root certs allow someone to intercept ALL your encrypted (HTTPS) traffic

### 2.4 Review All Installed Apps
1. Go to: **Settings > General > iPhone Storage**
2. Scroll through the ENTIRE list
3. Look for:
   - Apps you don't recognize
   - Apps with generic names (e.g., "System Service", "Phone Monitor")
   - Apps that use significant storage or mobile data but you never use
4. **Delete any app you don't recognize**: Long press > Delete App

**Known spyware app names to watch for:**
- mSpy, FlexiSpy, Cocospy, Spyic, Spyzie, Hoverwatch
- EyeZy, uMobix, XNSPY, ClevGuard, KidsGuard, TheOneSpy
- Any app named similar to a system process (e.g., "System Update", "WiFi Service")

### 2.5 Check App Permissions
Go to: **Settings > Privacy & Security** and check each:

| Permission | What to look for |
|-----------|------------------|
| Location Services | Apps with "Always" access that shouldn't have it |
| Microphone | Unknown apps with mic access |
| Camera | Unknown apps with camera access |
| Contacts | Unknown apps reading contacts |
| Photos | Apps with "Full Access" that don't need it |
| Bluetooth | Unknown apps using Bluetooth |
| Local Network | Unknown apps accessing local network |

### 2.6 Check Email Accounts
1. Go to: **Settings > Mail > Accounts**
2. Verify each account is yours
3. **Delete any account you didn't add**
4. An attacker may add an email account to silently forward/sync your data

### 2.7 Check VPN Configuration
1. Go to: **Settings > General > VPN & Device Management > VPN**
2. Delete any VPN configuration you didn't install
3. Unknown VPNs can route ALL your traffic through an attacker's server

### 2.8 Check Keyboard Settings
1. Go to: **Settings > General > Keyboard > Keyboards**
2. You should only see standard Apple keyboards (and any you intentionally installed)
3. **Delete unknown third-party keyboards** — malicious keyboards can log everything you type

### 2.9 Check Screen Time for Unusual Activity
1. Go to: **Settings > Screen Time > See All App & Website Activity**
2. Look for apps showing usage that you don't recognize
3. High background activity from unknown apps = spyware communicating with its server

### 2.10 Check Safari/Browser Data
1. **Safari**: Settings > Safari > Advanced > Website Data
   - Look for unusual domains
2. **Chrome** (if installed): History
   - Look for sites you didn't visit (phishing pages, login pages)
3. Check for unknown browser extensions

---

## Phase 3: iCloud Security Audit

### 3.1 Review Devices on Your Apple ID
1. Go to: **Settings > [Your Name]** > scroll down
2. Every device listed has access to your iCloud data
3. **Remove any device you don't recognize**: Tap it > "Remove from Account"

### 3.2 Review iCloud Services
1. **Settings > [Your Name] > iCloud**
2. Check what's being synced — an attacker with your Apple ID can access all of this
3. Consider temporarily disabling:
   - iCloud Backup (until device is clean)
   - iCloud Drive (if suspicious files were found)
   - Notes, Reminders, Contacts (if sharing sensitive data)

### 3.3 Check iCloud Drive for Suspicious Files
1. Open the **Files** app > Browse > iCloud Drive
2. Look for files you didn't create:
   - `.apk` files (Android apps — like the `base.apk` found)
   - `.mobileconfig` files (configuration profiles)
   - `.cer`, `.p12`, `.pem` files (certificates)
   - Unknown scripts or executables

### 3.4 Check Find My
1. **Settings > [Your Name] > Find My**
2. Verify only YOUR devices are listed
3. Check "Share My Location" — who can see your location?
4. Disable if concerned about tracking

### 3.5 Check Shared Albums & Notes
1. Open **Photos** > Albums > Shared Albums — check for unknown shared albums
2. Open **Notes** > check for shared notes you didn't create
3. These can be used for data exfiltration

### 3.6 Check iCloud Keychain
1. **Settings > Passwords**
2. Check "Security Recommendations"
3. Look for compromised, reused, or weak passwords
4. Change ALL compromised passwords (from a trusted device on mobile data)

---

## Phase 4: Network Security (After Router is Secured)

Only do this AFTER completing the ROUTER_SECURITY_GUIDE.md steps.

### 4.1 Forget Old WiFi Networks
1. **Settings > Wi-Fi**
2. Tap the (i) next to your home network > "Forget This Network"
3. Also forget any other unknown/suspicious networks
4. Reconnect with the NEW WiFi password (set during router hardening)

### 4.2 Check for Rogue WiFi Networks
1. In **Settings > Wi-Fi**, look at available networks
2. Watch for duplicate or similar names to your home network
   - e.g., "HomeWiFi" and "HomeWiFi_5G" when you only have one
   - This could be an "Evil Twin" access point

### 4.3 Configure DNS
On iPhone:
1. **Settings > Wi-Fi** > tap (i) on your network > Configure DNS
2. Change from "Automatic" to "Manual"
3. Add trusted DNS servers:
   - `1.1.1.1` (Cloudflare)
   - `1.0.0.1` (Cloudflare backup)
4. This ensures DNS goes to a trusted provider regardless of router settings

### 4.4 Check for Proxy Configuration
1. **Settings > Wi-Fi** > tap (i) on your network > scroll to HTTP Proxy
2. Should be set to "Off"
3. If set to "Manual" or "Automatic" and you didn't configure it: **turn it off**
4. A proxy routes all your web traffic through another server

---

## Phase 5: Nuclear Option — Factory Reset

**Do this if any of the following are true:**
- MDM enrollment was found (and it's not a work device)
- Jailbreak indicators found (Cydia, Sileo, etc.)
- Multiple configuration profiles from unknown sources
- Custom root certificates that keep reappearing
- Device continues to behave suspiciously after remediation

### 5.1 Before Reset
1. **Back up important data** (photos, contacts) to a trusted computer
   - Do NOT use iCloud backup (it may contain the compromise)
   - Use a wired connection to a Mac/PC
2. Document your findings (screenshot or write down)
3. Note which apps you need to reinstall

### 5.2 DFU Mode Reset (Most Thorough)

DFU (Device Firmware Update) mode completely reinstalls iOS from scratch.

**iPhone 8 and later (including iPhone 16 Pro):**
1. Connect iPhone to a Mac/PC with a USB cable
2. Open Finder (Mac) or iTunes (Windows)
3. Quick press Volume Up
4. Quick press Volume Down
5. Press and hold Side button until screen goes black
6. While holding Side button, also hold Volume Down for 5 seconds
7. Release Side button, keep holding Volume Down for 10 seconds
8. The screen should remain black (if Apple logo appears, start over)
9. Finder/iTunes will detect a device in recovery mode
10. Click "Restore" (NOT "Update")

### 5.3 After Reset
1. Set up as NEW iPhone (do NOT restore from backup)
2. Sign in with your Apple ID (password already changed)
3. Enable 2FA if not already on
4. Reinstall apps ONLY from the official App Store
5. Do NOT install any apps that were sent via messages or links
6. Configure all security settings (see Phase 6)

---

## Phase 6: Ongoing Protection

### 6.1 Enable Lockdown Mode
**Settings > Privacy & Security > Lockdown Mode > Turn On Lockdown Mode**

Lockdown Mode provides the strongest protection against sophisticated attacks:
- Blocks most message attachment types
- Disables complex web technologies
- Blocks incoming FaceTime from unknown callers
- Blocks wired connections when locked
- Blocks configuration profiles
- Some apps may work differently

**This is the single most effective protection for a targeted device.**

### 6.2 Enable Advanced Data Protection
**Settings > [Your Name] > iCloud > Advanced Data Protection > Turn On**

Encrypts nearly all iCloud data end-to-end, so even Apple can't access it.

### 6.3 Enable Stolen Device Protection
**Settings > Face ID & Passcode > Stolen Device Protection > Turn On**

Requires biometric authentication for sensitive changes when away from familiar locations.

### 6.4 Additional Hardening
- [ ] Set a strong alphanumeric passcode (not just 6 digits)
- [ ] Enable "Erase Data" after 10 failed passcode attempts
- [ ] Disable Siri on Lock Screen
- [ ] Disable Control Center on Lock Screen
- [ ] Disable USB Accessories when locked (Settings > Face ID & Passcode)
- [ ] Disable notification previews on Lock Screen
- [ ] Enable automatic iOS updates (Settings > General > Software Update > Automatic Updates)
- [ ] Use Safari or a privacy-focused browser (not Chrome)
- [ ] Install a trusted ad/tracker blocker (e.g., 1Blocker, AdGuard)
- [ ] Use encrypted DNS: Settings > Wi-Fi > (i) > Configure DNS > Manual > 1.1.1.1

### 6.5 Regular Security Checks
Perform these weekly:
1. Check Settings > General > VPN & Device Management for new profiles
2. Check Settings > General > About > Certificate Trust Settings
3. Review installed apps in Settings > General > iPhone Storage
4. Check Settings > [Your Name] > Devices for unknown devices
5. Review Settings > Passwords > Security Recommendations
6. Check Screen Time for unusual app activity

---

## Appendix A: Account Security Checklist

Run `python scripts/security_audit.py --accounts` for an interactive version.

### Critical Priority
- [ ] Apple ID — password changed, 2FA enabled, unknown devices removed
- [ ] Primary email — password changed, 2FA enabled, forwarding rules checked
- [ ] Banking — passwords changed, transactions reviewed, alerts enabled
- [ ] Password manager — master password changed, breach report reviewed

### High Priority
- [ ] Social media — all passwords changed, sessions revoked
- [ ] WhatsApp — two-step verification enabled, linked devices checked
- [ ] Telegram — two-step verification enabled, sessions terminated
- [ ] Cloud storage (Google Drive, Dropbox, OneDrive) — passwords changed

### Standard
- [ ] Shopping accounts (Amazon, etc.)
- [ ] Streaming accounts (Netflix, Spotify, etc.)
- [ ] Any account that uses the same password as a compromised account

---

## Appendix B: Using the Security Tools

### Router Audit
```bash
# Quick scan
python scripts/router_audit.py

# Full scan with report
python scripts/router_audit.py --full --output router_report.json
```

### File Scanner
```bash
# Scan downloads folder
python scripts/security_audit.py --scan-dir ~/Downloads/

# Analyze a specific file
python scripts/security_audit.py --analyze base.apk

# Full audit
python scripts/security_audit.py --all --scan-dir ~/
```

### APK Analyzer
```bash
# Analyze the suspicious APK
python scripts/analyze_apk.py base.apk --output apk_report.json
```

### iPhone Checklist
```bash
# Interactive walkthrough
python scripts/iphone_security_checklist.py
```

---

## Appendix C: When to Seek Professional Help

Contact a cybersecurity professional or law enforcement if:
- Evidence of sustained, targeted surveillance
- Financial accounts have been accessed or funds stolen
- Identity theft indicators (new accounts, credit applications)
- The compromise persists after factory reset
- You find enterprise MDM enrollment from an unknown organization
- You suspect domestic abuse or stalking (contact the National Domestic Violence Hotline: 1-800-799-7233)

### Resources
- **Apple Support**: https://support.apple.com — for MDM/profile issues
- **Have I Been Pwned**: https://haveibeenpwned.com — check if your email/passwords are in breaches
- **CISA**: https://www.cisa.gov/report — report sophisticated cyber attacks
- **FBI IC3**: https://www.ic3.gov — report internet crimes
- **FTC Identity Theft**: https://identitytheft.gov — if identity theft is suspected
