"""
tests/functional_test.py
=================================================================================
Functional test suite - Emergency Response and SOS Location Tracking System
Nigeria Police Force - Enugu State Command
=================================================================================

Exercises the database layer, the CRUD/dispatch business logic, the Haversine
calculations and the incident report generator (including PDF structure).

Run from the project root:

    python tests/functional_test.py

Exit code 0 means every check passed.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Make the project root importable when this file is run directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app          # noqa: E402
import db           # noqa: E402
import haversine    # noqa: E402
import reports      # noqa: E402

FAILURES: list[str] = []
EARTH_MEAN_RADIUS_KM = 6371.0088


def check(label: str, condition: bool, detail: object = "") -> None:
    status = "PASS" if condition else "FAIL"
    if not condition:
        FAILURES.append(label)
    print(f"  [{status}] {label}{(' - ' + str(detail)) if detail != '' else ''}")


def main() -> int:
    print("== A. database integrity ==")
    check("database exists", db.database_exists(), db.DB_PATH)
    for table, minimum in (("users", 2), ("police_stations", 6), ("patrol_units", 5),
                           ("sos_alerts", 4), ("activity_log", 1)):
        count = db.fetch_scalar(f"SELECT COUNT(*) FROM {table}", default=0)
        check(f"{table} has >= {minimum} rows", count >= minimum, f"{count} rows")

    fk = db.fetch_scalar("PRAGMA foreign_keys", default=0)
    check("foreign keys enforced", int(fk) == 1, f"PRAGMA foreign_keys={fk}")

    print("\n== B. CRUD and dispatch lifecycle ==")
    ok, message, alert_id = app.create_alert(
        {
            "citizen_name": "Test Citizen", "phone_number": "08011112222",
            "latitude": 6.4500, "longitude": 7.5050,
            "emergency_type": "Medical", "description": "Functional test alert.",
            "status": "Active",
        },
        actor="test_suite",
    )
    check("create_alert", bool(ok and alert_id), message)

    alert = app.get_alert(alert_id)
    check("new alert is Active", bool(alert) and alert["status"] == "Active",
          alert["status"] if alert else None)

    units = app.load_units()
    available = [u for u in units if u["status"] == "Available"]
    target_unit = available[0] if available else units[0]

    ok, message = app.dispatch_unit(alert_id, target_unit["unit_id"], actor="test_suite")
    check("dispatch_unit", ok, message)

    alert = app.get_alert(alert_id)
    unit = db.fetch_one("SELECT * FROM patrol_units WHERE unit_id = ?", (target_unit["unit_id"],))
    check("alert -> Dispatched", alert["status"] == "Dispatched", alert["status"])
    check("alert stores assigned_unit_id", alert["assigned_unit_id"] == target_unit["unit_id"])
    check("unit -> Dispatched", unit["status"] == "Dispatched", unit["status"])

    ok, message = app.close_alert(alert_id, "Resolved", actor="test_suite")
    check("close_alert(Resolved)", ok, message)
    alert = app.get_alert(alert_id)
    unit = db.fetch_one("SELECT * FROM patrol_units WHERE unit_id = ?", (target_unit["unit_id"],))
    check("alert -> Resolved with resolved_at",
          alert["status"] == "Resolved" and bool(alert["resolved_at"]),
          f"{alert['status']} / {alert['resolved_at']}")
    check("unit released back to Available", unit["status"] == "Available", unit["status"])

    print("\n== C. foreign key behaviour (ON DELETE SET NULL) ==")
    db.execute_query("UPDATE sos_alerts SET assigned_unit_id = ? WHERE alert_id = ?",
                     (target_unit["unit_id"], alert_id))
    db.execute_query("DELETE FROM patrol_units WHERE unit_id = ?", (target_unit["unit_id"],))
    alert = app.get_alert(alert_id)
    check("deleting a unit nulls sos_alerts.assigned_unit_id",
          alert["assigned_unit_id"] is None, alert["assigned_unit_id"])
    # Restore the unit so the demonstration database is left intact.
    db.execute_query(
        """INSERT INTO patrol_units
               (unit_callsign, officer_name, current_lat, current_long, status)
           VALUES (?, ?, ?, ?, 'Available')""",
        (target_unit["unit_callsign"], target_unit["officer_name"],
         target_unit["current_lat"], target_unit["current_long"]),
    )

    print("\n== D. CHECK / UNIQUE constraints ==")
    duplicate = db.fetch_one("SELECT unit_callsign FROM patrol_units LIMIT 1")
    try:
        db.execute_query(
            "INSERT INTO patrol_units (unit_callsign, officer_name, current_lat,"
            " current_long, status) VALUES (?, 'X', 6.4, 7.5, 'Available')",
            (duplicate["unit_callsign"],),
        )
        check("duplicate callsign rejected", False, "insert unexpectedly succeeded")
    except db.DatabaseError as exc:
        check("duplicate callsign rejected", True, exc)

    try:
        db.execute_query(
            "INSERT INTO sos_alerts (citizen_name, phone_number, latitude, longitude,"
            " emergency_type, status) VALUES ('X', '080', 6.4, 7.5, 'Arson', 'Active')"
        )
        check("invalid emergency_type rejected", False, "insert unexpectedly succeeded")
    except db.DatabaseError as exc:
        check("invalid emergency_type rejected", True, exc)

    print("\n== E. Haversine accuracy ==")
    quarter_equator = 3.14159265358979 / 2.0 * EARTH_MEAN_RADIUS_KM
    cases = [
        ((6.4483, 7.5023, 6.4521, 7.5089), 0.843),      # State HQ -> Ogui Road Division
        ((6.4483, 7.5023, 6.4712, 7.5134), 2.826),      # State HQ -> Abakpa Nike
        ((6.4483, 7.5023, 6.8523, 7.3934), 46.505),     # Enugu city -> Nsukka
        ((0.0, 0.0, 0.0, 90.0), quarter_equator),       # quarter of the equator
    ]
    for args, expected in cases:
        actual = haversine.calculate_distance(*args)
        check(f"distance {args} = {expected:.3f} km", abs(actual - expected) < 0.05,
              f"got {actual} km")

    check("distance to the same point is zero",
          haversine.calculate_distance(6.5, 7.5, 6.5, 7.5) == 0.0)
    check("symmetry", haversine.calculate_distance(6.4, 7.4, 6.9, 7.9)
          == haversine.calculate_distance(6.9, 7.9, 6.4, 7.4))
    check("ETA: 40 km at 40 km/h = 69 min (15% traffic allowance)",
          abs(haversine.estimate_arrival_time(40, 40) - 69.0) < 0.1,
          haversine.estimate_arrival_time(40, 40))
    check("format_eta(90) = '1 hr 30 min'", haversine.format_eta(90) == "1 hr 30 min",
          haversine.format_eta(90))

    alert = app.get_alert(alert_id)
    ranked = haversine.find_nearest_units(alert["latitude"], alert["longitude"],
                                          app.load_units(), top_n=3, available_only=True)
    check("find_nearest_units returns at most 3", 0 < len(ranked) <= 3, f"{len(ranked)}")
    check("results sorted nearest first",
          all(ranked[i]["distance_km"] <= ranked[i + 1]["distance_km"]
              for i in range(len(ranked) - 1)),
          [r["distance_km"] for r in ranked])
    check("only Available units considered",
          all(r["status"] == "Available" for r in ranked), [r["status"] for r in ranked])
    print("      ranking:", [(r["unit_callsign"], r["distance_km"], r["eta_text"]) for r in ranked])

    print("\n== F. incident report and PDF ==")
    report = reports.generate_incident_report(alert_id)
    check("report reference present", bool(report["reference"]), report["reference"])
    check("resolved incident has a response time", report["response_minutes"] is not None,
          report["response_minutes_text"])
    check("response block populated", bool(report["response"]["unit_callsign"]),
          report["response"]["unit_callsign"])
    html_report = reports.format_report_as_html(report)
    check("HTML report contains the command name", "NIGERIA POLICE FORCE" in html_report)
    check("HTML report contains the incident id", f"SOS-{alert_id:05d}" in html_report)
    check("text report contains the dispatch block",
          "RESPONSE DISPATCH" in reports.format_report_as_text(report))

    pdf = reports.generate_pdf_bytes(report)
    check("PDF header is %PDF-1.4", pdf.startswith(b"%PDF-1.4"), pdf[:8])
    check("PDF ends with %%EOF", pdf.rstrip().endswith(b"%%EOF"))
    check("PDF size is plausible", len(pdf) > 2000, f"{len(pdf)} bytes")

    text = pdf.decode("latin-1")
    xref_pos = int(re.search(r"startxref\s+(\d+)", text).group(1))
    check("startxref points at the xref table", text[xref_pos:xref_pos + 4] == "xref")
    lines = text[xref_pos:].split("\n")
    entries = int(lines[1].split()[1])
    offsets_ok = all(
        text[int(line.split()[0]):int(line.split()[0]) + 20].startswith(f"{i + 1} 0 obj")
        for i, line in enumerate(lines[3:3 + entries - 1])
    )
    check("every PDF xref offset resolves to its object", offsets_ok)
    (PROJECT_ROOT / "data").mkdir(exist_ok=True)
    (PROJECT_ROOT / "data" / "_test_report.pdf").write_bytes(pdf)

    print("\n== G. search queries ==")
    for needle, table, column in (("Nwankwo", "sos_alerts", "citizen_name"),
                                  ("Kidnapping", "sos_alerts", "emergency_type"),
                                  ("PATROL-01", "patrol_units", "unit_callsign"),
                                  ("Ogui", "police_stations", "station_name")):
        rows = db.fetch_all(f"SELECT * FROM {table} WHERE {column} LIKE ?", (f"%{needle}%",))
        check(f"search '{needle}' in {table}.{column}", len(rows) >= 1, f"{len(rows)} hit(s)")

    rows = db.fetch_all(
        "SELECT * FROM sos_alerts WHERE ('SOS-' || printf('%05d', alert_id)) LIKE ?",
        (f"%SOS-{alert_id:05d}%",),
    )
    check("search by SOS-xxxxx incident id", len(rows) == 1, f"{len(rows)} hit(s)")

    print("\n== H. cleanup ==")
    ok, message = app.delete_alert(alert_id, actor="test_suite")
    check("delete_alert", ok, message)
    check("alert removed from the register", app.get_alert(alert_id) is None)

    print("\n== I. concurrent writes (citizen app + police dashboard) ==")
    # Two independent Streamlit sessions mean two independent SQLite
    # connections to the same database file.  Simulate that with threads.
    import threading
    import time as _time

    WRITERS = 5
    PER_WRITER = 8
    errors: list[str] = []
    written: list[int] = []
    reader_stop = threading.Event()
    reader_counts: list[int] = []
    lock = threading.Lock()

    def writer(worker: int) -> None:
        for index in range(PER_WRITER):
            try:
                new_id = db.execute_query(
                    """INSERT INTO sos_alerts
                       (citizen_name, phone_number, latitude, longitude,
                        emergency_type, description, status)
                       VALUES (?, ?, ?, ?, 'Other', 'concurrency test', 'Active')""",
                    (f"Concurrent Writer {worker}", f"0800000{worker:02d}{index:02d}",
                     6.44 + worker * 0.001, 7.50 + index * 0.001),
                )
                with lock:
                    written.append(int(new_id))
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"writer {worker}: {exc}")

    def reader() -> None:
        while not reader_stop.is_set():
            try:
                count = int(db.fetch_scalar("SELECT COUNT(*) FROM sos_alerts", default=0) or 0)
                with lock:
                    reader_counts.append(count)
            except Exception as exc:  # noqa: BLE001
                with lock:
                    errors.append(f"reader: {exc}")
            _time.sleep(0.01)

    writer_threads = [threading.Thread(target=writer, args=(w,)) for w in range(WRITERS)]
    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()
    for thread in writer_threads:
        thread.start()
    for thread in writer_threads:
        thread.join()
    reader_stop.set()
    reader_thread.join(timeout=2)

    expected = WRITERS * PER_WRITER
    check(f"{expected} simultaneous INSERTs all succeeded", len(written) == expected,
          f"{len(written)} written")
    check("no 'database is locked' failure", not errors, errors[:3])
    # WAL mode lets the reader keep working while the writers hold the lock.
    check("reads succeeded while writes were in progress", len(reader_counts) >= 1,
          f"{len(reader_counts)} successful reads during the write burst")

    if written:
        placeholders = ",".join("?" for _ in written)
        db.execute_query(f"DELETE FROM sos_alerts WHERE alert_id IN ({placeholders})",
                         tuple(written))
        leftover = db.fetch_scalar(
            "SELECT COUNT(*) FROM sos_alerts WHERE description = 'concurrency test'",
            default=0,
        )
        check("concurrency test rows cleaned up", int(leftover) == 0, f"{leftover} left")

    print(f"\n===== {len(FAILURES)} failure(s) =====")
    for failure in FAILURES:
        print("  FAILED:", failure)
    return len(FAILURES)


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
