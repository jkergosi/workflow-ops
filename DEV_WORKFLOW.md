# Development Workflow Guide

## Hot-Reload vs Manual Restart

### ✅ Hot-Reload Handles These Automatically (No Restart Needed)

**Frontend (Vite):**
- Changes to `.tsx`, `.ts`, `.css` files
- Component updates
- State management changes
- Most code changes

**Backend (uvicorn --reload):**
- Changes to Python files (`.py`)
- Route modifications
- Schema updates
- Most code changes

### ⚠️ Manual Restart Required For

**Frontend:**
- Installing new npm packages
- Changes to `vite.config.ts`
- Changes to `package.json` scripts
- Changes to environment variables (`.env` files)
- Major dependency updates

**Backend:**
- Installing new Python packages
- Database migrations (though these run automatically on start)
- Changes to `requirements.txt`
- Changes to environment variables (`.env` files)
- Major dependency updates

## Quick Commands

### Start Servers

```powershell
# Frontend (port 3000)
cd n8n-ops-ui
npm run dev

# Backend (port 4000)
cd n8n-ops-backend
python scripts/start_with_migrations.py
```

### Stop Servers (When Needed)

```powershell
# Kill both ports 3000 and 4000
.\scripts\kill-ports.ps1

# Kill only frontend (port 3000)
.\scripts\kill-ports.ps1 -Port 3000

# Kill only backend (port 4000)
.\scripts\kill-ports.ps1 -Port 4000

# Or from frontend directory
cd n8n-ops-ui
npm run kill
```

### Port Enforcement

Port enforcement runs automatically before starting servers. If ports are in use, processes are killed automatically. If you need to manually free ports:

```powershell
.\scripts\kill-ports.ps1
```

## Troubleshooting

### "Port already in use" Error

1. Run `.\scripts\kill-ports.ps1` to free the ports
2. Try starting again

### Hot-Reload Not Working

**Frontend:**
- Check browser console for errors
- Hard refresh (Ctrl+Shift+R)
- Check if Vite is watching files (look for file change messages in terminal)

**Backend:**
- Check terminal for uvicorn reload messages
- Verify `--reload` flag is present in startup command
- Check for Python syntax errors (reload won't work with syntax errors)

### When in Doubt

If hot-reload seems broken:
1. Save your file and wait 2-3 seconds
2. Check terminal for reload messages
3. If still not working, restart: `.\scripts\kill-ports.ps1` then start again

## Best Practice

**Start servers once, let hot-reload handle changes.**

Only restart when:
- Installing dependencies
- Changing config files
- Hot-reload clearly isn't working
- After pulling major changes from git

