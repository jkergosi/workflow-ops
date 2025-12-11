# n8n_credential_instructions.md
Comprehensive instructions for correctly configuring `N8N_ENCRYPTION_KEY` on a **new** n8n instance and for handling the scenario where an **existing** instance is missing or changing the key.

---

# 1. Purpose of the Encryption Key
n8n uses `N8N_ENCRYPTION_KEY` to encrypt and decrypt all saved credentials.  
Without this key:

- Credentials cannot be decrypted.  
- If the key is missing or changes later, **all stored credentials become unusable**.  
- The key must remain stable for the lifetime of the instance.

---

# 2. Requirements
- A 32-byte (256-bit) secure random value.  
- Must be set **before n8n starts for the first time** or **before credentials are created**.

Valid formats: Base64 or Hex.

Examples:

## Generate Base64 Key (Linux/macOS)
```
openssl rand -base64 32
```

## Generate Base64 Key (Windows PowerShell)
```
[Convert]::ToBase64String((New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes(32))
```

## Generate Hex Key
```
openssl rand -hex 32
```

Keep this key stored securely (password manager, secrets vault, etc.).

---

# 3. How to Install on a New n8n Instance

## Step 1 — Generate your encryption key  
Use one of the commands above to produce your 32-byte key.

## Step 2 — Add the key to the environment variables  
In your hosting provider (e.g., RepoCloud), locate the container's environment variable section and add:

```
N8N_ENCRYPTION_KEY=<your-generated-key>
```

Recommended additional vars:

```
N8N_SECURE_COOKIE=true
```

If you use a domain:

```
N8N_HOST=<your-domain>
WEBHOOK_URL=https://<your-domain>/
```

## Step 3 — Start the n8n instance  
Once the key is set, start n8n.  
Credentials created from this point forward will be encrypted using this key.

## Step 4 — Never rotate or delete this key  
If the key changes, stored credentials immediately become invalid and cannot be recovered.

---

# 4. Installing When n8n Already Exists (No Credentials Created)
If the server is already running **but no credentials have been created yet**, you can safely add the key now.

### Steps:
1. Stop the n8n container.  
2. Add `N8N_ENCRYPTION_KEY` to environment variables.  
3. Restart the container.  
4. You may now create credentials normally.

---

# 5. Installing When n8n Already Exists (Credentials Already Created Without a Key)
If the instance was started **without** `N8N_ENCRYPTION_KEY`, n8n auto-generates an ephemeral key internally.

This means:
- Existing credentials were encrypted with that unknown ephemeral key.  
- You cannot retrieve or decrypt them.  
- Setting a new key makes all existing credentials permanently invalid.

You have two possible approaches below.

---

# 6. Recovery Options for Existing Instances

## Option A — KEEP Existing Credentials (Not Possible Without Original Key)
n8n **does not** expose or persist the ephemeral encryption key.  
If you did not set a key originally, there is **no possible way** to recover the stored credentials.

This is a hard design constraint for security.

If credential preservation is required, you must:

- Extract each credential in plaintext manually from the UI  
- Re-enter them after setting your real encryption key  

No automation is possible here because the API never returns decrypted secrets.

---

## Option B — Reset Credentials and Start Clean (Recommended When Early in Deployment)

### Steps:
1. Export any workflows if needed (workflows do not contain decrypted secrets).  
2. Delete all existing credentials inside n8n.  
3. Stop the n8n server.  
4. Add the environment variable:
   ```
   N8N_ENCRYPTION_KEY=<your-generated-key>
   ```
5. Restart the server.  
6. Recreate credentials manually.  

This gives you a stable, long-term foundation.

---

# 7. Verifying the Key Is Active

You can verify that encryption is correctly configured by checking:

### Method A — API
Call:
```
GET /rest/credentials
```
If credentials can be created and updated normally and persist across container restarts, the key is functioning.

### Method B — Server Log
On startup, n8n logs whether the encryption system is initialized.

---

# 8. Best Practices

1. **Always set `N8N_ENCRYPTION_KEY` before first launch.**  
2. Store the key somewhere safe (password manager or secrets vault).  
3. Never rotate the key unless clearing all credentials intentionally.  
4. When using hosting services (RepoCloud, Hostinger, Render, etc.), set the key in the container environment before running migrations or creating any credentials.  
5. Back up workflow metadata separately; never back up decrypted credentials.  

---

# 9. Summary

| Scenario | Action Required |
|---------|-----------------|
| New n8n install | Generate key → set `N8N_ENCRYPTION_KEY` → start instance |
| Existing install but **no credentials yet** | Add key now → restart |
| Existing install **with credentials but no key** | Must delete & recreate credentials; old ones cannot be recovered |
| Key is changed later | All credentials break permanently |
