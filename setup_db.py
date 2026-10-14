"""
setup_db.py
=================================================================
Database creation and seeding script
Emergency Response and SOS Location Tracking System
Nigeria Police Force - Enugu State Command
=================================================================

Run this once before starting the application:

    python setup_db.py            # create tables, seed if empty
    python setup_db.py --reset    # DROP everything and rebuild + reseed
    python setup_db.py --no-seed  # create empty tables only

It is completely safe to re-run: seeding only happens when a table is
empty, so an officer's live data is never overwritten by the demo data.

Tables created
--------------
    users             - Admin/Commander and Viewer/Dispatcher accounts
    police_stations   - divisions of Enugu State Command (real GPS coords)
    patrol_units      - patrol vehicles on the ground
    sos_alerts        - distress calls received from citizens
    activity_log      - audit trail used by the dashboard activity feed
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

# Local modules
import auth
import db

# ---------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------
SCHEMA_SQL = """
-- ==================================================================
-- 1. USERS  (authentication + role based access control)
-- ==================================================================
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('Admin', 'Viewer')),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================================================================
-- 2. POLICE STATIONS  (divisions of Enugu State Command)
-- ==================================================================
CREATE TABLE IF NOT EXISTS police_stations (
    station_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    station_name TEXT NOT NULL,
    latitude     REAL NOT NULL,
    longitude    REAL NOT NULL,
    address      TEXT
);

-- ==================================================================
-- 3. PATROL UNITS  (vehicles on the ground)
-- ==================================================================
CREATE TABLE IF NOT EXISTS patrol_units (
    unit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_callsign TEXT UNIQUE NOT NULL,
    officer_name TEXT NOT NULL,
    current_lat  REAL NOT NULL,
    current_long REAL NOT NULL,
    status       TEXT NOT NULL CHECK (status IN ('Available', 'Dispatched', 'Offline')),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================================================================
-- 4. SOS ALERTS  (distress calls from citizens)
--    assigned_unit_id is a FOREIGN KEY to patrol_units: deleting a
--    patrol unit automatically releases any alert it was attending
--    (ON DELETE SET NULL) instead of leaving a dangling reference.
-- ==================================================================
CREATE TABLE IF NOT EXISTS sos_alerts (
    alert_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    citizen_name    TEXT NOT NULL,
    phone_number    TEXT NOT NULL,
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    emergency_type  TEXT NOT NULL CHECK (emergency_type IN
                        ('Armed Robbery', 'Kidnapping', 'Accident', 'Medical', 'Other')),
    description     TEXT,
    status          TEXT NOT NULL CHECK (status IN
                        ('Active', 'Dispatched', 'Resolved', 'False Alarm')),
    assigned_unit_id INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at     TIMESTAMP,
    FOREIGN KEY (assigned_unit_id) REFERENCES patrol_units (unit_id)
        ON DELETE SET NULL ON UPDATE CASCADE
);

-- ==================================================================
-- 5. ACTIVITY LOG  (audit trail / dashboard activity feed)
-- ==================================================================
CREATE TABLE IF NOT EXISTS activity_log (
    log_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    action    TEXT NOT NULL,
    details   TEXT,
    actor     TEXT,
    alert_id  INTEGER,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================================================================
-- Indexes for the searches performed most often by the dashboard
-- ==================================================================
CREATE INDEX IF NOT EXISTS idx_alerts_status      ON sos_alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_type        ON sos_alerts (emergency_type);
CREATE INDEX IF NOT EXISTS idx_alerts_created     ON sos_alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_citizen     ON sos_alerts (citizen_name);
CREATE INDEX IF NOT EXISTS idx_units_status       ON patrol_units (status);
CREATE INDEX IF NOT EXISTS idx_activity_logged    ON activity_log (logged_at DESC);
"""

# ---------------------------------------------------------------------
# Seed data - real Enugu State locations
# ---------------------------------------------------------------------
SEED_POLICE_STATIONS = [
    ("Enugu State Police Command Headquarters", 6.4483, 7.5023,
     "State Police Headquarters, Abakaliki Road, GRA, Enugu"),
    ("Ogui Road Division", 6.4521, 7.5089,
     "Ogui Road, by Ogui Urban, Enugu North LGA, Enugu State"),
    ("Abakpa Nike Division", 6.4712, 7.5134,
     "Abakpa Nike Road, Enugu East LGA, Enugu State"),
    ("Trans-Ekulu Division", 6.4356, 7.4892,
     "Trans-Ekulu, along Enugu-Onitsha Expressway, Enugu State"),
    ("Independence Layout Division", 6.4398, 7.4956,
     "Independence Layout, Enugu South LGA, Enugu State"),
    ("Nsukka Division", 6.8523, 7.3934,
     "Nsukka Urban, Nsukka LGA, Enugu State"),
]

SEED_PATROL_UNITS = [
    ("PATROL-01-OGUI", "Sgt. Emeka Okonkwo", 6.4538, 7.5061, "Available", 4),
    ("PATROL-02-ABAKPA", "Cpl. Ngozi Umeh", 6.4698, 7.5152, "Available", 9),
    ("PATROL-03-TRANS-EKULU", "Insp. Chidi Okafor", 6.4361, 7.4901, "Dispatched", 27),
    ("PATROL-04-INDEPENDENCE", "Sgt. Aisha Bello", 6.4412, 7.4987, "Available", 12),
    ("PATROL-05-NSUKKA", "Insp. Musa Danjuma", 6.8507, 7.3962, "Offline", 96),
]

# (citizen, phone, lat, lon, type, description, status, assigned_callsign,
#  created_minutes_ago, resolved_minutes_after_creation)
#
# NOTE ON TIMINGS: every seeded alert is deliberately made OLDER than
# ALARM_FRESH_MINUTES (5 minutes, defined in app.py).  The police dashboard
# rings only for a genuinely new arrival, so an officer signing in must NOT
# trigger the alarm - otherwise the control room would start ringing the
# moment the application is opened.
SEED_SOS_ALERTS = [
    (
        "Chief Anthony Nwankwo", "08034567890", 6.4471, 7.5098, "Armed Robbery",
        "Four armed men on two motorcycles are robbing a provision store at "
        "Ogui Road. They are shooting sporadically. Traders are running for safety.",
        "Active", None, 26, None,
    ),
    (
        "Mrs. Blessing Eze", "08127784512", 6.4623, 7.4721, "Accident",
        "A commercial bus has somersaulted along the Enugu-Onitsha Expressway "
        "by Ogbaku Junction. Two passengers are trapped inside the vehicle.",
        "Dispatched", "PATROL-03-TRANS-EKULU", 41, None,
    ),
    (
        "Mr. Ifeanyi Obi", "07061239876", 6.4389, 7.4967, "Medical",
        "My neighbour collapsed at No. 14 Nza Street, Independence Layout. "
        "He is diabetic and unconscious. We need an ambulance urgently.",
        "Resolved", None, 52, 12,
    ),
    (
        "Miss Chiamaka Agu", "08099887766", 6.8551, 7.3908, "Kidnapping",
        "Unknown persons in a tinted Sienna bus forcefully pushed my younger "
        "brother into the vehicle around Odenigbo Junction, Nsukka.",
        "Resolved", "PATROL-05-NSUKKA", 58, 26,
    ),
    (
        "Mr. Peter Nnamdi", "08156674321", 6.4275, 7.4869, "Other",
        "Some youths are fighting at the motor park. It may just be a dispute "
        "over park levy. Please confirm before sending a team.",
        "False Alarm", None, 47, 9,
    ),
]


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(minutes_delta: float = 0.0) -> str:
    """UTC timestamp string ``YYYY-MM-DD HH:MM:SS`` offset by minutes."""
    return (_utc_now() + timedelta(minutes=minutes_delta)).strftime("%Y-%m-%d %H:%M:%S")


def _table_count(table: str) -> int:
    try:
        return int(db.fetch_scalar(f"SELECT COUNT(*) FROM {table}", default=0) or 0)
    except db.DatabaseError:
        return 0


# ---------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------
def create_tables() -> None:
    """Create every table, index and constraint (idempotent)."""
    db.execute_script(SCHEMA_SQL)
    print("  [OK] Tables and indexes created / verified.")
    _apply_migrations()


def _apply_migrations() -> None:
    """
    Bring an older database up to the current schema.

    ``CREATE TABLE IF NOT EXISTS`` does not add new columns to a table
    that already exists, so we check explicitly and ALTER when needed.
    This keeps previous demo databases usable without a reset.
    """
    try:
        columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(sos_alerts)")}
    except db.DatabaseError:
        return

    if columns and "assigned_unit_id" not in columns:
        db.execute_query("ALTER TABLE sos_alerts ADD COLUMN assigned_unit_id INTEGER")
        print("  [OK] Migration applied: sos_alerts.assigned_unit_id added.")


def drop_tables() -> None:
    """Drop every application table (used by --reset)."""
    db.execute_script(
        """
        PRAGMA foreign_keys = OFF;
        DROP TABLE IF EXISTS activity_log;
        DROP TABLE IF EXISTS sos_alerts;
        DROP TABLE IF EXISTS patrol_units;
        DROP TABLE IF EXISTS police_stations;
        DROP TABLE IF EXISTS users;
        PRAGMA foreign_keys = ON;
        """
    )
    print("  [OK] Existing tables dropped.")


def seed_users(force: bool = False) -> None:
    """Create the two default accounts with properly hashed passwords."""
    if _table_count("users") > 0 and not force:
        print("  [--] users already populated - skipped.")
        return

    accounts = [
        ("commander", "npf123", "Admin"),
        ("dispatcher", "npf123", "Viewer"),
    ]
    for username, password, role in accounts:
        db.execute_query(
            "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, auth.hash_password(password), role),
        )
    print(f"  [OK] Seeded {len(accounts)} user accounts "
          f"(commander/Admin, dispatcher/Viewer - password: npf123).")


def seed_stations(force: bool = False) -> None:
    """Insert the six divisions of Enugu State Command."""
    if _table_count("police_stations") > 0 and not force:
        print("  [--] police_stations already populated - skipped.")
        return

    for name, lat, lon, address in SEED_POLICE_STATIONS:
        db.execute_query(
            """
            INSERT INTO police_stations (station_name, latitude, longitude, address)
            VALUES (?, ?, ?, ?)
            """,
            (name, lat, lon, address),
        )
    print(f"  [OK] Seeded {len(SEED_POLICE_STATIONS)} police stations.")


def seed_patrol_units(force: bool = False) -> None:
    """Insert the five patrol units currently on the ground."""
    if _table_count("patrol_units") > 0 and not force:
        print("  [--] patrol_units already populated - skipped.")
        return

    for callsign, officer, lat, lon, status, updated_minutes_ago in SEED_PATROL_UNITS:
        db.execute_query(
            """
            INSERT INTO patrol_units
                (unit_callsign, officer_name, current_lat, current_long, status, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (callsign, officer, lat, lon, status, _ts(-updated_minutes_ago)),
        )
    print(f"  [OK] Seeded {len(SEED_PATROL_UNITS)} patrol units.")


def seed_alerts(force: bool = False) -> None:
    """Insert the demo distress calls with a realistic status mix."""
    if _table_count("sos_alerts") > 0 and not force:
        print("  [--] sos_alerts already populated - skipped.")
        return

    unit_lookup = {
        unit["unit_callsign"]: unit["unit_id"]
        for unit in db.fetch_all("SELECT unit_id, unit_callsign FROM patrol_units")
    }

    inserted = 0
    for (
        citizen, phone, lat, lon, emergency_type, description,
        status, callsign, minutes_ago, resolve_after,
    ) in SEED_SOS_ALERTS:
        created_at = _ts(-minutes_ago)
        resolved_at = _ts(-minutes_ago + resolve_after) if resolve_after is not None else None
        assigned_unit_id = (
            unit_lookup.get(callsign) if callsign and callsign in unit_lookup else None
        )

        db.execute_query(
            """
            INSERT INTO sos_alerts
                (citizen_name, phone_number, latitude, longitude, emergency_type,
                 description, status, assigned_unit_id, created_at, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                citizen, phone, lat, lon, emergency_type, description, status,
                assigned_unit_id, created_at, resolved_at,
            ),
        )
        inserted += 1

    print(f"  [OK] Seeded {inserted} SOS alerts "
          f"(Active, Dispatched, Resolved and False Alarm).")


def seed_activity_log(force: bool = False) -> None:
    """Seed a short audit trail so the dashboard feed is never empty."""
    if _table_count("activity_log") > 0 and not force:
        print("  [--] activity_log already populated - skipped.")
        return

    entries = [
        ("SYSTEM_INIT", "Database created and demo data seeded", "system", 0),
        ("ALERT_RECEIVED", "SOS-00001 Armed Robbery at Ogui Road - Active", "commander", 1),
        ("UNIT_DISPATCHED", "PATROL-03-TRANS-EKULU dispatched to SOS-00002", "commander", 2),
        ("ALERT_RESOLVED", "SOS-00003 Medical emergency resolved in 12 minutes", "dispatcher", 3),
        ("ALERT_RESOLVED", "SOS-00004 Kidnapping report resolved, victim recovered", "commander", 4),
        ("ALERT_CLOSED", "SOS-00005 verified as False Alarm", "dispatcher", 5),
    ]
    for action, details, actor, alert_id in entries:
        db.execute_query(
            """
            INSERT INTO activity_log (action, details, actor, alert_id, logged_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (action, details, actor, alert_id, _ts(-(6 - alert_id) * 3)),
        )
    print(f"  [OK] Seeded {len(entries)} activity log entries.")


def print_summary() -> None:
    """Print a short verification report after setup."""
    print("\n  Database summary")
    print("  " + "-" * 44)
    for table, label in (
        ("users", "Users"),
        ("police_stations", "Police stations"),
        ("patrol_units", "Patrol units"),
        ("sos_alerts", "SOS alerts"),
        ("activity_log", "Activity log entries"),
    ):
        print(f"  {label:<24}: {_table_count(table):>4}")
    active = _table_count("sos_alerts")
    if active:
        by_status = db.fetch_all(
            "SELECT status, COUNT(*) AS total FROM sos_alerts GROUP BY status ORDER BY status"
        )
        breakdown = ", ".join(f"{row['status']}={row['total']}" for row in by_status)
        print(f"  {'Alert status mix':<24}: {breakdown}")
    print(f"  {'Database file':<24}: {db.DB_PATH}")


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and seed the NPF Enugu SOS tracking database."
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop all tables and rebuild the database from scratch.",
    )
    parser.add_argument(
        "--no-seed", action="store_true",
        help="Create empty tables without inserting demo data.",
    )
    args = parser.parse_args(argv)

    print("=" * 62)
    print(" NPF ENUGU - EMERGENCY RESPONSE & SOS TRACKING SYSTEM")
    print(" Database setup utility")
    print("=" * 62)
    print(f" Target: {db.DB_PATH}\n")

    try:
        if args.reset:
            print(" Resetting database ...")
            drop_tables()

        print(" Creating schema ...")
        create_tables()

        if args.no_seed:
            print("\n  [--] Seeding skipped (--no-seed).")
        else:
            print("\n Seeding demo data ...")
            seed_users()
            seed_stations()
            seed_patrol_units()
            seed_alerts()
            seed_activity_log()

        print_summary()
        print("\n Setup completed successfully.")
        print(" Next step:  streamlit run app.py")
        print("=" * 62)
        return 0

    except db.DatabaseError as exc:
        print(f"\n[ERROR] Database failure: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - top level guard
        print(f"\n[ERROR] Unexpected failure: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close_connection()


if __name__ == "__main__":
    raise SystemExit(main())
