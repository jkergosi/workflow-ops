# Cloudflare Setup Guide for Hostinger VPS + PaaS
This guide provides the minimal, correct setup for using Cloudflare Free with a Hostinger VPS and a self‑hosted PaaS (Coolify, Dokploy, CapRover). It includes DNS, SSL/TLS, security, and environment separation (staging/prod).

---
Cloudflare Free
https://dash.cloudflare.com/68aa74f1532449bb1cc6ef4edfa66b6c/welcome

## 1. Add Your Domain to Cloudflare
1. Log into Cloudflare Dashboard → **Add a Site**.  
2. Enter your domain (e.g., `example.com`).  
3. Select the **Free** plan.  
4. Cloudflare scans DNS; accept defaults for now.

---

## 2. Change Your Domain’s Nameservers
Cloudflare provides two nameservers like:

```
ns1.cloudflare.com
ns2.cloudflare.com
```

Update your domain registrar to use these nameservers.  
Cloudflare will activate once it detects the change.

---

## 3. Point DNS to Your Hostinger VPS
Create these A records in Cloudflare DNS:

| Name | Type | Value | Proxy | Purpose |
|------|------|--------|--------|---------|
| `ops` | A | `<YOUR_VPS_IP>` | Proxied | n8n‑ops prod |
| `ops-staging` | A | `<YOUR_VPS_IP>` | Proxied | n8n‑ops staging |
| `bbf` | A | `<YOUR_VPS_IP>` | Proxied | Business By Faith prod |
| `bbf-staging` | A | `<YOUR_VPS_IP>` | Proxied | Business By Faith staging |
| `n8n` | A | `<YOUR_VPS_IP>` | Proxied | n8n prod |
| `n8n-staging` | A | `<YOUR_VPS_IP>` | Proxied | n8n staging |
| `ssh-private` | A | `<YOUR_VPS_IP>` | DNS Only | SSH access (restrict by IP) |

**Orange cloud = ON** for apps.  
**Grey cloud = DNS only** for SSH/VPN endpoints.

---

## 4. SSL/TLS Settings (Critical)
Cloudflare → **SSL/TLS → Overview**

Set to:

### **Full (Strict)**  
Ensures Cloudflare connects securely to your VPS using a trusted certificate.

Additional settings (recommended):

- **Always Use HTTPS** → ON  
- **Automatic HTTPS Rewrites** → ON  
- **TLS 1.3** → ON  
- **HSTS** → optional (enable only once everything works)

---

## 5. Configure Your PaaS (Coolify, Dokploy, CapRover)
For each app:

1. Add the domain (e.g., `ops.example.com`).
2. Enable HTTPS via:
   - **Let’s Encrypt**, or  
   - Cloudflare Origin Certs.
3. Ensure reverse proxy (Traefik/Nginx) listens on ports **80** and **443**.

Environment separation:

- `ops-staging` → staging DB  
- `ops` → prod DB  
- `bbf-staging` and `bbf-prod` similar  
- `n8n-staging` and `n8n-prod` separate if needed

---

## 6. VPS Security
### Firewall (UFW or provider firewall)
Allow only:

```
80/tcp
443/tcp
22/tcp (only from your IP)
```

Deny everything else.

### SSH Hardening
- Use SSH keys only.  
- Disable password auth.  
- Optional: change SSH port.  
- Optional: install fail2ban.  

---

## 7. Optional Cloudflare Firewall Rules
Recommended free-tier rules:

### Block non‑trusted access to staging
```
if (hostname contains "staging") and (ip not in {YOUR_IP}) → Block
```

### Block bad bots
```
if (cf.client.bot) = false and (cf.threat_score > 40) → Block
```

### Country block example
```
if (ip.geoip.country eq "CN") → Block
```

---

## 8. Verification Checklist
1. Visit `https://ops.example.com` → should show Cloudflare SSL.  
2. Run:

```
curl -I https://ops.example.com
```

Look for header: `cf-ray` = Cloudflare proxy is active.

3. Ensure staging domains load over HTTPS.

---

## 9. Summary
- Cloudflare Free is ideal for your stage.  
- DNS + HTTPS + WAF + DDoS protection at no cost.  
- Perfect for your multi‑app setup (n8n, n8n‑ops, Business by Faith).  
- No impact on hosting costs.  
- Easiest path to future scaling.

