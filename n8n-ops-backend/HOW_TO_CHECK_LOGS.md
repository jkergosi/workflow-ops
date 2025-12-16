# How to Check Backend Logs (Local Development)

## Where Logs Appear

When you run the backend locally, **all logs appear in the terminal/console window where you started the server**.

## Starting the Backend

The backend is typically started with:

```bash
cd n8n-ops-backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 4000
```

Or if you're using the PowerShell script:
```powershell
# The backend starts automatically in a background job
```

## Viewing Logs

### Option 1: Terminal Window (Recommended)
1. **Find the terminal window** where you ran the `uvicorn` command
2. **All logs will appear there** in real-time as requests are processed
3. Look for:
   - `INFO` messages (normal operation)
   - `ERROR` messages (problems)
   - `[Job {job_id}]` messages (deployment progress)
   - `ERROR:` messages (detailed error information)

### Option 2: PowerShell Background Jobs
If you're using the PowerShell script that starts jobs in the background:

```powershell
# List all background jobs
Get-Job

# View logs from a specific job (replace 1 with job ID)
Receive-Job -Id 1

# View logs and keep watching
Receive-Job -Id 1 -Keep
```

### Option 3: Check Job Output Files
If jobs are writing to files, check:
- The terminal output where the job was started
- Any log files in the `n8n-ops-backend/` directory

## What to Look For

When testing deployments, look for these log messages:

### Deployment Start
```
INFO: [Job {job_id}] Background task added for promotion {promotion_id}, deployment {deployment_id}
INFO: [Job {job_id}] Creating N8N clients - Source: {url}, Target: {url}
INFO: [Job {job_id}] Testing source environment connection...
INFO: [Job {job_id}] Source environment connection successful
```

### Workflow Processing
```
INFO: [Job {job_id}] Fetching workflow {workflow_id} ({workflow_name}) from source environment
INFO: [Job {job_id}] Prepared workflow data for {workflow_name}: {node_count} nodes
INFO: [Job {job_id}] Checking for existing workflow '{workflow_name}' in target environment
INFO: [Job {job_id}] Creating new workflow '{workflow_name}' in target environment
INFO: [Job {job_id}] Successfully created workflow '{workflow_name}' (ID: {id}) in target environment
```

### Errors
```
ERROR: [Job {job_id}] Failed to transfer workflow {workflow_name}: {error_message}
ERROR: [Job {job_id}] Error type: {error_type}
ERROR: Windows errno 22 (Invalid argument) - check for invalid characters in workflow data
ERROR: Workflow name: {name}
ERROR: Number of nodes: {count}
```

## Enabling More Verbose Logging

To see more detailed logs, you can:

### 1. Set Log Level via Environment Variable
```bash
# Windows PowerShell
$env:LOG_LEVEL="DEBUG"
python -m uvicorn app.main:app --reload --port 4000

# Windows CMD
set LOG_LEVEL=DEBUG
python -m uvicorn app.main:app --reload --port 4000
```

### 2. Add Logging Configuration
Create a file `n8n-ops-backend/logging_config.py`:

```python
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
```

Then import it in `app/main.py`:
```python
import logging_config  # Add this at the top
```

## Common Log Locations

- **Terminal Output**: The console where `uvicorn` is running
- **Print Statements**: Also appear in the terminal (like `ERROR:` messages)
- **Uvicorn Access Logs**: HTTP request/response logs (enabled by default)

## Tips

1. **Keep the terminal visible** - Don't minimize the window running uvicorn
2. **Scroll up** - Errors might have scrolled past, use scroll to see earlier messages
3. **Look for `[Job`** - All deployment-related logs include `[Job {job_id}]` prefix
4. **Check for `ERROR:`** - Our enhanced error handling prints detailed `ERROR:` messages
5. **Watch in real-time** - Logs appear as requests are processed, so watch while testing

## Example: Testing a Deployment

1. Start the backend (logs appear in that terminal)
2. Open the frontend and create a deployment
3. Watch the backend terminal for:
   ```
   INFO: [Job abc123] Background task added...
   INFO: [Job abc123] Creating N8N clients...
   INFO: [Job abc123] Fetching workflow...
   ```
4. If there's an error, you'll see:
   ```
   ERROR: [Job abc123] Failed to transfer workflow...
   ERROR: Windows errno 22 (Invalid argument)...
   ```

## Troubleshooting

**If you don't see any logs:**
- Make sure the backend is actually running
- Check if you're looking at the correct terminal window
- Verify the backend started successfully (you should see "Uvicorn running on...")

**If logs are too verbose:**
- The default level is INFO, which should be fine
- You can filter by searching for "ERROR" or "[Job" in your terminal

**If you need to save logs:**
- Use terminal output redirection:
  ```bash
  python -m uvicorn app.main:app --reload --port 4000 > backend.log 2>&1
  ```
- Then view with: `cat backend.log` or `Get-Content backend.log`

