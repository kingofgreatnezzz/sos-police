"""
db.py
=================================================================
Database helper module for the
Emergency Response and SOS Location Tracking System
Nigeria Police Force - Enugu State Command
=================================================================

This module is the ONLY place in the application that talks directly
to SQLite.  Every other module (and the Streamlit app) uses the four
public helpers:

    get_connection()                     -> raw sqlite3 connection
    execute_query(query, params)         -> write  (INSERT/UPDATE/DELETE)
    fetch_all(query, params)             -> list[dict]
    fetch_one(query, params)             -> dict | None

Design notes
------------
* Connections are cached **per thread** because Streamlit runs each
  browser session in its own ScriptRunner thread.  A single shared
  sqlite3 connection would raise "SQLite objects created in a thread
  can only be used in that same thread".

  This matters a great deal for the TWO-MODE architecture: the Citizen SOS
  app (phone) and the Police Command dashboard (control-room PC) are two
  independent Streamlit sessions, so they hold two independent SQLite
  connections to the SAME database file.

* **Concurrent write safety.**  SQLite runs in WAL (write-ahead logging)
  journal mode, which allows readers to continue while a writer is active
  instead of blocking them.  On top of that:
      - ``PRAGMA busy_timeout`` makes SQLite *wait* rather than fail
        immediately when another connection holds the write lock, and
      - every statement is retried a few times on "database is locked",
        which covers the brief overlap when the citizen app is INSERTing
        an SOS alert at the very instant the police dashboard is polling.

* ``PRAGMA foreign_keys = ON`` is issued on every new connection so the
  relational integrity between ``sos_alerts`` and ``patrol_units``
  (the dispatch relationship) is genuinely enforced by SQLite.
* ``row_factory = sqlite3.Row`` lets rows be read by column name, and we
  convert them to plain dicts so Pandas / Streamlit can consume them
  directly.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"

#: The single SQLite database shared by BOTH application modes
#: (Citizen SOS app + Police Command dashboard).
DB_FILENAME: str = "sos_emergency.db"
DB_PATH: Path = DATA_DIR / DB_FILENAME

#: Name used by an earlier prototype - migrated automatically on first use.
LEGACY_DB_PATH: Path = DATA_DIR / "sos_database.db"

# Concurrency tuning
BUSY_TIMEOUT_MS: int = 8000      # wait up to 8 s for a competing writer
MAX_RETRIES: int = 5             # retries when the database is briefly locked
RETRY_DELAY_SECONDS: float = 0.15

# ---------------------------------------------------------------------
# Thread-local connection cache
# ---------------------------------------------------------------------
_local = threading.local()


class DatabaseError(Exception):
    """Raised when a database operation fails, with a friendly message."""


def _migrate_legacy_database() -> None:
    """
    Rename an older ``sos_database.db`` to ``sos_emergency.db`` so that any
    existing data and accounts are preserved rather than starting afresh.
    """
    try:
        if not DB_PATH.exists() and LEGACY_DB_PATH.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            LEGACY_DB_PATH.rename(DB_PATH)
            for suffix in ("-wal", "-shm"):
                old_side = Path(str(LEGACY_DB_PATH) + suffix)
                if old_side.exists():
                    old_side.rename(Path(str(DB_PATH) + suffix))
    except OSError:
        # If the rename fails we simply start a fresh database.
        pass


def _is_locked_error(exc: Exception) -> bool:
    """True when the failure is a transient 'database is locked' condition."""
    text = str(exc).lower()
    return "locked" in text or "busy" in text


def _run_with_retry(operation: Callable[[], Any]) -> Any:
    """
    Execute a database operation, retrying briefly if the file is locked.

    This is what makes simultaneous writes from the citizen app and the
    police dashboard safe: instead of raising "database is locked" at the
    operator, the statement waits a fraction of a second and retries.
    """
    last_error: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not _is_locked_error(exc):
                raise
            last_error = exc
            time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    raise DatabaseError(
        "The database is busy (another session is writing at the same moment). "
        "Please try that action again."
    ) from last_error


# ---------------------------------------------------------------------
# Connection handling
# ---------------------------------------------------------------------
def get_connection() -> sqlite3.Connection:
    """
    Return a thread-local SQLite connection to the SOS database.

    The connection is created on first use in each thread and reused
    afterwards.  Foreign key enforcement is switched on explicitly
    (SQLite disables it by default).
    """
    conn: Optional[sqlite3.Connection] = getattr(_local, "conn", None)

    if conn is not None:
        try:
            # Cheap liveness probe - the connection may have been closed
            # by a previous Streamlit rerun.
            conn.execute("SELECT 1")
            return conn
        except sqlite3.Error:
            _local.conn = None

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_database()
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=15.0,
        check_same_thread=False,
        isolation_level=None,  # autocommit; we manage transactions ourselves
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL lets the citizen app write while the police dashboard is reading.
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    # Wait (rather than fail) when the other session holds the write lock.
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS};")
    _local.conn = conn
    return conn


def close_connection() -> None:
    """Close the connection held by the current thread (used by tests)."""
    conn: Optional[sqlite3.Connection] = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass
        _local.conn = None


def database_exists() -> bool:
    """True when the database file is present and has the expected tables."""
    if not DB_PATH.exists():
        return False
    try:
        row = fetch_one(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'sos_alerts'"
        )
        return row is not None
    except DatabaseError:
        return False


# ---------------------------------------------------------------------
# Public query helpers
# ---------------------------------------------------------------------
def execute_query(query: str, params: Sequence[Any] = ()) -> int:
    """
    Run an INSERT / UPDATE / DELETE statement.

    Retries automatically if another session (for example the citizen app)
    is writing to the database at the same instant.

    Returns
    -------
    int
        For INSERT statements -> the new ``lastrowid``.
        For UPDATE / DELETE   -> the number of affected rows.
    """
    def operation() -> int:
        conn = get_connection()
        cur = conn.execute(query, tuple(params))
        try:
            stripped = query.lstrip().upper()
            if stripped.startswith("INSERT"):
                return int(cur.lastrowid or 0)
            return int(cur.rowcount)
        finally:
            try:
                cur.close()
            except Exception:  # pragma: no cover - defensive
                pass

    try:
        return _run_with_retry(operation)
    except DatabaseError:
        raise
    except sqlite3.IntegrityError as exc:
        raise DatabaseError(_friendly_integrity_error(exc)) from exc
    except sqlite3.Error as exc:
        raise DatabaseError(f"Database error: {exc}") from exc


def execute_many(query: str, param_list: Iterable[Sequence[Any]]) -> int:
    """Run the same statement for many parameter sets. Returns row count."""
    params = [tuple(p) for p in param_list]

    def operation() -> int:
        conn = get_connection()
        cur = conn.executemany(query, params)
        try:
            return int(cur.rowcount)
        finally:
            try:
                cur.close()
            except Exception:  # pragma: no cover
                pass

    try:
        return _run_with_retry(operation)
    except DatabaseError:
        raise
    except sqlite3.IntegrityError as exc:
        raise DatabaseError(_friendly_integrity_error(exc)) from exc
    except sqlite3.Error as exc:
        raise DatabaseError(f"Database error: {exc}") from exc


def fetch_all(query: str, params: Sequence[Any] = ()) -> list[dict]:
    """Run a SELECT and return every row as a plain dictionary."""
    def operation() -> list[dict]:
        conn = get_connection()
        cur = conn.execute(query, tuple(params))
        try:
            return [dict(row) for row in cur.fetchall()]
        finally:
            try:
                cur.close()
            except Exception:  # pragma: no cover
                pass

    try:
        return _run_with_retry(operation)
    except DatabaseError:
        raise
    except sqlite3.Error as exc:
        raise DatabaseError(f"Database error: {exc}") from exc


def fetch_one(query: str, params: Sequence[Any] = ()) -> Optional[dict]:
    """Run a SELECT and return the first row as a dictionary (or None)."""
    def operation() -> Optional[dict]:
        conn = get_connection()
        cur = conn.execute(query, tuple(params))
        try:
            row = cur.fetchone()
            return dict(row) if row is not None else None
        finally:
            try:
                cur.close()
            except Exception:  # pragma: no cover
                pass

    try:
        return _run_with_retry(operation)
    except DatabaseError:
        raise
    except sqlite3.Error as exc:
        raise DatabaseError(f"Database error: {exc}") from exc


def fetch_scalar(query: str, params: Sequence[Any] = (), default: Any = None) -> Any:
    """Run a SELECT and return the first column of the first row."""
    row = fetch_one(query, params)
    if row is None:
        return default
    value = next(iter(row.values()))
    return default if value is None else value


def execute_script(script: str) -> None:
    """Execute a multi-statement SQL script (used by setup_db.py)."""
    conn = get_connection()
    try:
        conn.executescript(script)
    except sqlite3.Error as exc:
        raise DatabaseError(f"Database error: {exc}") from exc


# ---------------------------------------------------------------------
# Activity log helper (powers the dashboard "Recent Activity" feed)
# ---------------------------------------------------------------------
def log_activity(
    action: str,
    details: str = "",
    actor: str = "system",
    alert_id: Optional[int] = None,
) -> None:
    """
    Append an entry to the audit/activity trail.

    Failures here are swallowed on purpose - logging must never break the
    primary operation being performed by an officer.
    """
    try:
        execute_query(
            """
            INSERT INTO activity_log (action, details, actor, alert_id)
            VALUES (?, ?, ?, ?)
            """,
            (action, details, actor, alert_id),
        )
    except Exception:  # pragma: no cover - logging is best effort
        pass


def recent_activity(limit: int = 6) -> list[dict]:
    """Return the most recent activity log entries."""
    try:
        return fetch_all(
            "SELECT * FROM activity_log ORDER BY log_id DESC LIMIT ?", (limit,)
        )
    except DatabaseError:
        return []


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------
def _friendly_integrity_error(exc: sqlite3.IntegrityError) -> str:
    """Translate raw SQLite constraint errors into officer-friendly text."""
    text = str(exc)
    lowered = text.lower()

    if "foreign key" in lowered:
        return (
            "Operation rejected: the selected patrol unit no longer exists "
            "in the register (foreign key constraint)."
        )
    if "unique" in lowered and "unit_callsign" in lowered:
        return "That patrol unit callsign already exists. Callsigns must be unique."
    if "unique" in lowered and "username" in lowered:
        return "That username is already taken. Please choose another one."
    if "check" in lowered and "emergency_type" in lowered:
        return (
            "Invalid emergency type. Allowed values are: Armed Robbery, "
            "Kidnapping, Accident, Medical, Other."
        )
    if "check" in lowered and "status" in lowered:
        return "Invalid status value supplied for this record."
    if "check" in lowered and "role" in lowered:
        return "Invalid role. Allowed roles are 'Admin' and 'Viewer'."
    if "not null" in lowered:
        return "A required field was left empty. Please complete all mandatory fields."
    return f"Data integrity error: {text}"


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    print(f"Database file : {DB_PATH}")
    print(f"Exists        : {database_exists()}")
    if database_exists():
        for table in ("users", "sos_alerts", "patrol_units", "police_stations"):
            count = fetch_scalar(f"SELECT COUNT(*) FROM {table}", default=0)
            print(f"  {table:<16}: {count} row(s)")
