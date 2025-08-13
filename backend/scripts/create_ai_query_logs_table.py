#!/usr/bin/env python3
"""
Create the AI Query Logs table (idempotent) by invoking SQLAlchemy metadata.
Intended for local/dev. Safe to run multiple times.
"""

import asyncio
from app.core.database import init_db


async def main() -> None:
  await init_db()


if __name__ == "__main__":
  asyncio.run(main())


