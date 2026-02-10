"""Run retention purge: python -m app.tasks.retention"""
import asyncio
import sys

from app.database import async_session_maker
from app.services.retention_service import purge_expired_data


async def main() -> int:
    async with async_session_maker() as db:
        stats = await purge_expired_data(db)
        print("Purged:", stats)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
