"""
Start script that runs database migrations before starting the application.

This ensures the database schema is up-to-date before the FastAPI app starts.
If migrations fail, the application will not start.

Also enforces deterministic port ownership per reqs/ports.md:
- Checks if port is available
- Force-kills any process using the port
- Fails fast if port remains occupied

Usage:
    python scripts/start_with_migrations.py
    python scripts/start_with_migrations.py --port 4000
    python scripts/start_with_migrations.py --host 0.0.0.0 --port 4000 --reload
"""
import subprocess
import sys
import os
import argparse
from pathlib import Path
import platform


def run_migrations():
    """Run Alembic migrations before starting the app."""
    backend_dir = Path(__file__).parent.parent
    original_dir = os.getcwd()
    
    try:
        os.chdir(backend_dir)
        
        print("=" * 60)
        print("Running database migrations...")
        print("=" * 60)
        
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("[ERROR] Migration failed!")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            return False

        print("[OK] Migrations completed successfully")
        print("=" * 60)
        return True
        
    except FileNotFoundError:
        print("[ERROR] 'alembic' command not found.")
        print("   Make sure Alembic is installed: pip install alembic")
        return False
    except Exception as e:
        print(f"[ERROR] Error running migrations: {str(e)}")
        return False
    finally:
        os.chdir(original_dir)


def enforce_port_ownership(port):
    """
    Enforce port ownership per reqs/ports.md.
    Checks if port is available, kills blocking processes, and fails if port remains occupied.
    """
    if platform.system() != "Windows":
        print(f"[WARN] Port enforcement skipped (not Windows). Port {port} may be in use.")
        return

    repo_root = Path(__file__).parent.parent.parent
    enforce_script = repo_root / "scripts" / "enforce-ports.ps1"

    if not enforce_script.exists():
        print(f"[WARN] Port enforcement script not found at {enforce_script}")
        print(f"   Skipping port check. Port {port} may be in use.")
        return
    
    print("=" * 60)
    print(f"Enforcing port ownership for port {port}...")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(enforce_script), "-Port", str(port)],
            capture_output=True,
            text=True,
            cwd=str(repo_root)
        )
        
        if result.returncode != 0:
            print("[ERROR] Port enforcement failed!")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            sys.exit(1)

        print(result.stdout)
        print("[OK] Port ownership enforced")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Error running port enforcement: {str(e)}")
        print(f"   Port {port} may be in use. Continuing anyway...")
        sys.exit(1)


def start_application(host="0.0.0.0", port=4000, reload=True):
    """Start the FastAPI application using uvicorn."""
    backend_dir = Path(__file__).parent.parent
    os.chdir(backend_dir)
    
    print("\n" + "=" * 60)
    print("Starting application...")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Reload: {reload}")
    print("=" * 60 + "\n")
    
    # Build uvicorn command
    cmd = [
        "uvicorn",
        "app.main:app",
        "--host", host,
        "--port", str(port)
    ]
    
    if reload:
        cmd.append("--reload")
    
    # Replace current process with uvicorn
    os.execvp("uvicorn", cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Run database migrations and start the application"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4000,
        help="Port to bind to (default: 4000)"
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (useful for production)"
    )
    parser.add_argument(
        "--skip-migrations",
        action="store_true",
        help="Skip running migrations (not recommended)"
    )
    
    args = parser.parse_args()
    
    # Enforce port ownership before starting (per reqs/ports.md)
    enforce_port_ownership(args.port)
    
    # Run migrations unless skipped
    if not args.skip_migrations:
        if not run_migrations():
            print("\n[ERROR] Failed to run migrations. Application will not start.")
            print("   To skip migrations (not recommended), use --skip-migrations")
            sys.exit(1)
    else:
        print("[WARN] Skipping migrations (--skip-migrations flag used)")
    
    # Start the application
    start_application(
        host=args.host,
        port=args.port,
        reload=not args.no_reload
    )


if __name__ == "__main__":
    main()

