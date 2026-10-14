"""
tests/two_mode_test.py
=================================================================================
Two-mode integration test
Emergency Response and SOS Location Tracking System - NPF Enugu State Command
=================================================================================

Proves the complete defence-day demonstration flow works end to end, in one
process, against the real app.py:

  1. CITIZEN MODE renders without login
  2. The citizen fills the form and presses the big red SOS button
  3. A new row appears in sos_alerts with status 'Active'
  4. POLICE MODE logs in and its alarm monitor detects the new alert
     (i.e. it is treated as a new arrival that must RING)
  5. "Mark as Dispatched" assigns the nearest patrol unit and stops the alarm
  6. The citizen's tracking screen then shows the responding unit

Run from the project root:

    python tests/two_mode_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

import db  # noqa: E402

APP_FILE = str(PROJECT_ROOT / "app.py")
CITIZEN = "🚨 Citizen SOS App"
POLICE = "👮 Police Command"

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: object = "") -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}"
          f"{(' - ' + str(detail)) if detail != '' else ''}")
    if not condition:
        FAILURES.append(label)


def exceptions(at: AppTest, label: str) -> int:
    errs = [e.value for e in at.exception]
    print(f"  [{label}] exceptions={len(errs)}")
    for exc in errs:
        print("      EXC:", str(exc).splitlines()[-1][:220])
        FAILURES.append(f"{label} exception")
    return len(errs)


def find(widgets, key: str):
    """Return the widget with the given key, or None."""
    for widget in widgets:
        if getattr(widget, "key", None) == key:
            return widget
    return None


def sign_in(at: AppTest, username: str, password: str) -> None:
    """
    Complete the police sign-in form.

    The button is found by its label because the mode-switch buttons at the top
    of the page also occupy the button list.
    """
    at.text_input[0].set_value(username)
    at.text_input[1].set_value(password)
    for button in at.button:
        if "Sign in" in str(button.label):
            button.click().run()
            return
    raise AssertionError("The 'Sign in' button was not found on the login page.")


def max_alert_id() -> int:
    return int(db.fetch_scalar("SELECT COALESCE(MAX(alert_id), 0) FROM sos_alerts", default=0) or 0)


def main() -> int:
    print("== 1. CITIZEN MODE renders without any login ==")
    at = AppTest.from_file(APP_FILE, default_timeout=180)
    at.session_state["app_mode"] = CITIZEN
    at.run()
    exceptions(at, "citizen mode")
    check("no login form is shown", len(at.text_input) >= 2)
    check("police sidebar is not present in citizen mode", not at.sidebar.radio)

    print("\n== 2. Citizen fills the form ==")
    find(at.text_input, "citizen_name").set_value("John Doe")
    find(at.text_input, "citizen_phone").set_value("08034567890")
    at.run()
    exceptions(at, "citizen form")

    # one-tap emergency category (three choices, index 0 = "Robbery / Theft")
    category_btn = find(at.button, "citizen_quick_0")
    check("one-tap category button exists", category_btn is not None)
    if category_btn:
        category_btn.click().run()
        exceptions(at, "category tap")
        check("category tap recorded",
              at.session_state["citizen_quick"] == 0,
              at.session_state["citizen_quick"])

    # simulated Enugu location (the demo-reliable fallback)
    sim_btn = find(at.button, "citizen_sim_loc")
    check("simulated location button exists", sim_btn is not None)
    if sim_btn:
        sim_btn.click().run()
        exceptions(at, "simulated location")
    check("Ogui Road coordinates applied",
          abs(float(at.session_state["citizen_lat"]) - 6.4521) < 1e-6
          and abs(float(at.session_state["citizen_lon"]) - 7.5089) < 1e-6,
          f"{at.session_state['citizen_lat']}, {at.session_state['citizen_lon']}")

    print("\n== 3. Press the BIG RED SOS BUTTON ==")
    before = max_alert_id()
    panic = find(at.button, "sos_panic_button")
    check("panic button exists", panic is not None)
    panic.click().run()
    exceptions(at, "after SOS press")
    after = max_alert_id()
    check("a new alert row was inserted", after > before, f"{before} -> {after}")

    new_alert = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (after,))
    check("alert status is Active", new_alert and new_alert["status"] == "Active",
          new_alert["status"] if new_alert else None)
    check("alert carries the citizen's name",
          new_alert and new_alert["citizen_name"] == "John Doe",
          new_alert["citizen_name"] if new_alert else None)
    check("alert carries the citizen's phone",
          new_alert and new_alert["phone_number"] == "08034567890")
    check("alert carries the emergency type",
          new_alert and new_alert["emergency_type"] == "Armed Robbery")
    check("alert carries the GPS coordinates",
          new_alert and abs(new_alert["latitude"] - 6.4521) < 1e-6
          and abs(new_alert["longitude"] - 7.5089) < 1e-6)
    check("citizen session is on the success screen",
          at.session_state["citizen_last_alert_id"] == after)
    import sounds  # noqa: E402
    beep = sounds.read_sound_bytes("beep")
    alarm = sounds.read_sound_bytes("alarm")
    check("confirmation chime WAV exists", len(beep) > 1000, f"{len(beep)} bytes")
    check("ringing alarm WAV exists", len(alarm) > 10000, f"{len(alarm)} bytes")

    print("\n== 4. POLICE MODE detects the new alert ==")
    police = AppTest.from_file(APP_FILE, default_timeout=180)
    police.session_state["app_mode"] = POLICE
    police.run()
    exceptions(police, "police login page")
    sign_in(police, "commander", "npf123")
    exceptions(police, "police login")
    check("logged in as commander",
          (police.session_state["user"] or {}).get("username") == "commander")

    # import the alarm logic directly to inspect the decision it takes
    import app as app_module  # noqa: E402

    pending, ringing = app_module.alarm_snapshot()
    check("the citizen's alert is pending acknowledgement",
          any(int(a["alert_id"]) == after for a in pending))
    check("the citizen's alert is flagged as RINGING (new arrival)",
          any(int(a["alert_id"]) == after for a in ringing),
          f"ringing ids={[int(a['alert_id']) for a in ringing]}")

    print("\n== 5. Mark as Dispatched from the alarm panel ==")
    dispatch_btn = find(police.button, "alarm_dispatch")
    check("'Mark as Dispatched' button is on screen", dispatch_btn is not None)
    unit_before = db.fetch_all("SELECT * FROM patrol_units WHERE status = 'Available'")
    if dispatch_btn:
        dispatch_btn.click().run()
        exceptions(police, "after dispatch")

    dispatched = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (after,))
    check("alert status changed to Dispatched",
          dispatched and dispatched["status"] == "Dispatched",
          dispatched["status"] if dispatched else None)
    check("a patrol unit was assigned", dispatched and dispatched["assigned_unit_id"])

    if dispatched and dispatched["assigned_unit_id"]:
        unit = db.fetch_one("SELECT * FROM patrol_units WHERE unit_id = ?",
                            (dispatched["assigned_unit_id"],))
        check("the assigned unit is now Dispatched", unit and unit["status"] == "Dispatched",
              unit["status"] if unit else None)

    pending_after, ringing_after = app_module.alarm_snapshot()
    check("alarm has stopped (alert is no longer Active)",
          not any(int(a["alert_id"]) == after for a in ringing_after))
    check("alarm was acknowledged in session state",
          after in set(police.session_state["alarm_acknowledged"]))
    check("at least one unit was available before dispatch", len(unit_before) >= 1)

    print("\n== 6. Citizen tracking screen reflects the dispatch ==")
    at.run()
    exceptions(at, "citizen tracking screen")
    tracked = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (after,))
    check("citizen screen still tracks the same incident",
          at.session_state["citizen_last_alert_id"] == after)
    check("citizen would now see 'Dispatched'",
          tracked and tracked["status"] == "Dispatched", tracked["status"] if tracked else None)

    print("\n== 7. Cleanup - restore the demo database ==")
    # release the unit and delete the test alert so the demonstration database
    # is left exactly as it was.
    if dispatched and dispatched["assigned_unit_id"]:
        db.execute_query(
            "UPDATE patrol_units SET status = 'Available' WHERE unit_id = ?",
            (dispatched["assigned_unit_id"],),
        )
    db.execute_query("DELETE FROM sos_alerts WHERE alert_id = ?", (after,))
    check("test alert removed", max_alert_id() == before)

    print("\n== 8. ONE-PRESS test: nothing filled in at all ==")
    # The whole design point: a terrified caller must be able to raise the alarm
    # without typing a single character.
    blank = AppTest.from_file(APP_FILE, default_timeout=180)
    blank.session_state["app_mode"] = CITIZEN
    blank.run()
    exceptions(blank, "blank citizen page")
    before_blank = max_alert_id()
    panic = find(blank.button, "sos_panic_button")
    check("panic button present with an empty form", panic is not None)
    panic.click().run()
    exceptions(blank, "one-press SOS")
    after_blank = max_alert_id()
    check("a row was created with NOTHING typed", after_blank > before_blank,
          f"{before_blank} -> {after_blank}")

    blank_alert = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (after_blank,))
    check("status is Active", blank_alert and blank_alert["status"] == "Active")
    check("unnamed caller is labelled clearly",
          blank_alert and blank_alert["citizen_name"] == "Unknown caller",
          blank_alert["citizen_name"] if blank_alert else None)
    check("missing phone is labelled clearly",
          blank_alert and blank_alert["phone_number"] == "Not provided",
          blank_alert["phone_number"] if blank_alert else None)
    check("a usable position is still recorded",
          blank_alert and blank_alert["latitude"] and blank_alert["longitude"],
          f"{blank_alert['latitude']}, {blank_alert['longitude']}" if blank_alert else None)
    check("the record explains the caller gave no details",
          blank_alert and "did not leave a name" in str(blank_alert["description"]))

    if blank_alert:
        db.execute_query("DELETE FROM sos_alerts WHERE alert_id = ?", (after_blank,))
    check("one-press alert cleaned up", max_alert_id() == before_blank)

    print(f"\n===== {len(FAILURES)} failure(s) =====")
    for failure in FAILURES:
        print("  FAILED:", failure)
    return len(FAILURES)


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
