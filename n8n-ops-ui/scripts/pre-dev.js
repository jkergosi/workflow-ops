/**
 * pre-dev.js
 * 
 * Pre-flight check for frontend dev server.
 * Enforces port 3000 ownership per reqs/ports.md.
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const FRONTEND_PORT = 3000;
const repoRoot = path.resolve(__dirname, '../..');
const enforceScript = path.join(repoRoot, 'scripts', 'enforce-ports.ps1');

if (process.platform !== 'win32') {
  console.log(`⚠️  Port enforcement skipped (not Windows). Port ${FRONTEND_PORT} may be in use.`);
  process.exit(0);
}

if (!fs.existsSync(enforceScript)) {
  console.log(`⚠️  Port enforcement script not found at ${enforceScript}`);
  console.log(`   Skipping port check. Port ${FRONTEND_PORT} may be in use.`);
  process.exit(0);
}

console.log(`Enforcing port ownership for frontend (port ${FRONTEND_PORT})...`);

try {
  execSync(
    `powershell.exe -ExecutionPolicy Bypass -File "${enforceScript}" -Port ${FRONTEND_PORT}`,
    { stdio: 'inherit', cwd: repoRoot }
  );
  console.log(`✓ Port ${FRONTEND_PORT} is free and ready`);
} catch (error) {
  console.error('❌ Port enforcement failed. Cannot start dev server.');
  process.exit(1);
}

