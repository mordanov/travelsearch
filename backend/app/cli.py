"""CLI commands for user and system management."""
import asyncio

import structlog

log = structlog.get_logger(__name__)


async def _create_user(email: str, password: str) -> None:
    from app.core.database import get_session_factory
    from app.core.logging import configure_logging
    from app.core.security import hash_password
    from app.repositories.user_repository import create_user, get_by_email

    configure_logging()
    factory = get_session_factory()
    async with factory() as db:
        existing = await get_by_email(db, email)
        if existing:
            print(f"User {email} already exists.")
            return
        hashed = hash_password(password)
        user = await create_user(db, email, hashed)
        await db.commit()
        print(f"User created: {user.email} (id={user.id})")


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.cli <command> [args]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create-user":
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", required=True)
        args = parser.parse_args(sys.argv[2:])
        asyncio.run(_create_user(args.email, args.password))
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
