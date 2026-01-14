#!/usr/bin/env python3
"""Run database migrations manually."""

import asyncio
from app.db.database import init_db, run_migrations


async def main():
    """Initialize database and run migrations."""
    print("Initializing database...")
    await init_db()
    print("\nRunning migrations...")
    await run_migrations()
    print("\n✓ Migration complete!")


if __name__ == "__main__":
    asyncio.run(main())
