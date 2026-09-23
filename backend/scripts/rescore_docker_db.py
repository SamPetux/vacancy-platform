"""Apply location rescore against Docker-published Postgres (non-loopback host)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv


def _rewrite_host(url: str, host: str) -> str:
    parsed = urlparse(url)
    auth = parsed.netloc.rsplit("@", 1)[0] if "@" in parsed.netloc else ""
    port = parsed.port or 5432
    netloc = f"{auth}@{host}:{port}" if auth else f"{host}:{port}"
    return urlunparse(parsed._replace(netloc=netloc))


async def _print_feed_state() -> None:
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.session import dispose_db, get_session_factory, init_db

    get_settings.cache_clear()
    init_db(get_settings())
    async with get_session_factory()() as session:
        statuses = (
            await session.execute(
                text(
                    "select moderation_status, count(*) "
                    "from vacancies group by 1 order by 2 desc"
                )
            )
        ).all()
        print("statuses", statuses)
        arzamas = (
            await session.execute(
                text(
                    "select count(*) from vacancies "
                    "where moderation_status='ready_for_publication' "
                    "and coalesce(address,'') ilike '%Арзамас%'"
                )
            )
        ).scalar()
        tazov = (
            await session.execute(
                text(
                    "select count(*) from vacancies "
                    "where moderation_status='ready_for_publication' "
                    "and ("
                    "coalesce(address,'') ilike '%Тазов%' "
                    "or title ilike '%Педагог дополнительного%'"
                    ")"
                )
            )
        ).scalar()
        print("arzamas_ready", arzamas, "tazov_ready", tazov)
        rows = (
            await session.execute(
                text(
                    "select ranked_position, left(title,50), left(coalesce(address,''),50) "
                    "from vacancies where moderation_status='ready_for_publication' "
                    "order by ranked_position"
                )
            )
        ).all()
        for row in rows:
            print(row)
    await dispose_db()


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.75"
    base = os.environ.get("DATABASE_URL")
    if not base:
        raise SystemExit("DATABASE_URL missing")
    os.environ["DATABASE_URL"] = _rewrite_host(base, host)

    from app.core.config import get_settings

    get_settings.cache_clear()
    from app.cli.main import rescore

    asyncio.run(rescore("nizhny-novgorod"))
    asyncio.run(_print_feed_state())


if __name__ == "__main__":
    main()
