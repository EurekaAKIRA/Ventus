"""Standalone launcher for the FastAPI task-center service."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import uvicorn


def _is_disabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"0", "false", "no", "off"}


def _configure_default_database() -> None:
    if os.getenv("TASK_CENTER_DATABASE_URL"):
        os.environ.setdefault("TASK_CENTER_PERSISTENCE_BACKEND", "db")
        return

    os.environ.setdefault("TASK_CENTER_PERSISTENCE_BACKEND", "db")
    if _is_disabled(os.getenv("TASK_CENTER_LOCAL_MYSQL_ENABLED")):
        return

    host = os.getenv("TASK_CENTER_LOCAL_MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("TASK_CENTER_LOCAL_MYSQL_PORT", "3306"))
    user = os.getenv("TASK_CENTER_LOCAL_MYSQL_USER", "root")
    password = os.getenv("TASK_CENTER_LOCAL_MYSQL_PASSWORD", "000000")
    database = os.getenv("TASK_CENTER_LOCAL_MYSQL_DATABASE", "task_center")
    quoted_identifier = database.replace("`", "``")

    try:
        import pymysql

        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset="utf8mb4",
            connect_timeout=2,
            read_timeout=2,
            write_timeout=2,
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{quoted_identifier}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            connection.commit()
        finally:
            connection.close()
    except Exception as exc:
        print(f"[task-center] Local MySQL unavailable ({exc}); using default SQLite database.")
        return

    quoted_user = quote_plus(user)
    quoted_password = quote_plus(password)
    quoted_database = quote_plus(database)
    os.environ["TASK_CENTER_DATABASE_URL"] = (
        f"mysql+pymysql://{quoted_user}:{quoted_password}@{host}:{port}/{quoted_database}?charset=utf8mb4"
    )
    print(f"[task-center] Using local MySQL database: {host}:{port}/{database}")


def _extend_path() -> None:
    root = Path(__file__).resolve().parents[2]
    legacy = root / "legacy"
    additions = [
        root / "platform" / "shared" / "src",
        root / "platform" / "requirement-analysis" / "src",
        root / "platform" / "case-generation" / "src",
        root / "platform" / "result-analysis" / "src",
        root / "platform" / "execution-engine" / "api-runner" / "src",
        root / "platform" / "execution-engine" / "core" / "src",
        root / "platform" / "task-center" / "src",
        legacy / "lavague-core",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-selenium",
        legacy / "lavague-integrations" / "drivers" / "lavague-drivers-playwright",
    ]
    for item in additions:
        path = str(item)
        if path not in sys.path:
            sys.path.insert(0, path)


def main() -> int:
    _extend_path()
    _configure_default_database()
    uvicorn.run("task_center.api:app", host="127.0.0.1", port=8001, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
