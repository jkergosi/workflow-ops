#!/usr/bin/env python3
"""
Helper script to create Alembic migration files with raw SQL.
Usage:
    python scripts/create_migration.py "migration_name" --sql "YOUR_SQL_HERE"
    python scripts/create_migration.py "migration_name" --file path/to/sql/file.sql
"""
import argparse
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory
    HAS_ALEMBIC = True
except ImportError:
    HAS_ALEMBIC = False


def create_migration(name: str, sql: str = None, sql_file: str = None):
    """Create a new Alembic migration file with raw SQL"""
    
    if sql_file:
        sql_path = Path(sql_file)
        if not sql_path.exists():
            print(f"Error: SQL file not found: {sql_file}")
            sys.exit(1)
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql = f.read()
    
    if not sql:
        print("Error: Either --sql or --file must be provided")
        sys.exit(1)
    
    backend_dir = Path(__file__).resolve().parent.parent
    
    if not HAS_ALEMBIC:
        print("Warning: Alembic not available as Python module, using subprocess...")
        result = subprocess.run(
            ["alembic", "revision", "-m", name],
            cwd=backend_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error running alembic: {result.stderr}")
            sys.exit(1)
        
        versions_dir = backend_dir / "alembic" / "versions"
        migration_files = sorted(versions_dir.glob("*.py"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not migration_files:
            print("Error: Could not find generated migration file")
            sys.exit(1)
        migration_path = migration_files[0]
        
        with open(migration_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        revision_match = re.search(r"revision = ['\"]([^'\"]+)['\"]", content)
        down_revision_match = re.search(r"down_revision = (.+)", content)
        
        if not revision_match:
            print("Error: Could not parse revision ID from migration file")
            sys.exit(1)
        
        head = revision_match.group(1)
        down_revision_str = down_revision_match.group(1).strip() if down_revision_match else "None"
    else:
        alembic_cfg = Config("alembic.ini")
        
        try:
            command.revision(
                alembic_cfg,
                message=name,
                autogenerate=False
            )
            
            script_dir = ScriptDirectory.from_config(alembic_cfg)
            head = script_dir.get_current_head()
            
            if not head:
                print("Error: Could not get revision ID")
                sys.exit(1)
            
            revision_file = script_dir.get_revision(head)
            migration_path = Path(revision_file.path)
            down_revision_str = repr(revision_file.down_revision) if revision_file.down_revision else "None"
        except Exception as e:
            print(f"Error creating migration: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    sql_escaped = sql.replace("'''", "\\'\\'\\'")
    sql_lines = sql_escaped.strip().split('\n')
    sql_indented = '\n'.join(f"    {line}" for line in sql_lines)
    
    upgrade_code = f"""def upgrade() -> None:
    op.execute('''
{sql_indented}
    ''')
"""

    downgrade_code = """def downgrade() -> None:
    pass
"""
    
    migration_content = f'''"""{name}

Revision ID: {head}
Revises: {down_revision_str if isinstance(down_revision_str, str) and down_revision_str != "None" else "None"}
Create Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '{head}'
down_revision = {down_revision_str}
branch_labels = None
depends_on = None


{upgrade_code}

{downgrade_code}
'''
    
    with open(migration_path, 'w', encoding='utf-8') as f:
        f.write(migration_content)
    
    print(f"\nCreated migration: {migration_path.name}")
    print(f"  Revision: {head}")
    print(f"  Path: {migration_path}")
    print(f"\nTo apply this migration, run:")
    print(f"  alembic upgrade head")


def main():
    parser = argparse.ArgumentParser(
        description="Create an Alembic migration file with raw SQL"
    )
    parser.add_argument(
        "name",
        help="Descriptive name for the migration (e.g., 'add_provider_to_environments')"
    )
    parser.add_argument(
        "--sql",
        help="Raw SQL to execute in the upgrade() function"
    )
    parser.add_argument(
        "--file",
        help="Path to SQL file to use for the migration"
    )
    
    args = parser.parse_args()
    
    create_migration(args.name, sql=args.sql, sql_file=args.file)


if __name__ == "__main__":
    main()
