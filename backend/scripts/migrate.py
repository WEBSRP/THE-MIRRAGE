"""Explicit database migration CLI. Run from the repository root as a module."""
import argparse
import asyncio
import json

from alembic import command
from alembic.migration import MigrationContext
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core.config import settings
from backend.app.core.migrations import adopt_schema, expected_heads, migration_config


async def inspect_or_adopt(action):
    engine = create_async_engine(settings.DATABASE_URL, echo=False, hide_parameters=True)
    try:
        async with engine.begin() as connection:
            if action == "adopt":
                revision = await connection.run_sync(adopt_schema)
                return {"adopted_revision": revision}
            current = await connection.run_sync(lambda conn: MigrationContext.configure(conn).get_current_heads())
            expected = expected_heads()
            return {"state": "current" if set(current) == expected else "behind" if current else "unversioned",
                    "revisions": sorted(current), "expected": sorted(expected)}
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "adopt", "upgrade", "downgrade"))
    parser.add_argument("revision", nargs="?", help="Optional upgrade target; required downgrade target")
    args = parser.parse_args()
    if args.action in ("status", "adopt"):
        if args.revision:
            parser.error("status/adopt do not accept a revision")
        print(json.dumps(asyncio.run(inspect_or_adopt(args.action))))
    elif args.action == "downgrade":
        if not args.revision:
            parser.error("downgrade requires an explicit revision")
        command.downgrade(migration_config(), args.revision)
        print("Database downgrade completed")
    else:
        command.upgrade(migration_config(), args.revision or "head")
        print("Database upgrade completed")


if __name__ == "__main__":
    main()
