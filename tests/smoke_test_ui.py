"""
tests/smoke_test_ui.py
=================================================================================
User-interface smoke test - Emergency Response and SOS Tracking System
Nigeria Police Force - Enugu State Command
=================================================================================

Uses Streamlit's official ``AppTest`` harness to execute the real ``app.py``
script and assert that **no page raises an exception**, for both the
Admin/Commander and the Viewer/Dispatcher roles.

Run from the project root:

    python tests/smoke_test_ui.py

A total of 0 exceptions means every page renders cleanly.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

APP_FILE = str(PROJECT_ROOT / "app.py")

PAGES = [
    "📊 Command Dashboard",
    "🗺️ Live SOS Map",
    "🚨 SOS Alert Management",
    "🧭 Nearest Unit Calculator",
    "🚔 Patrol Units",
    "🏛️ Police Stations",
    "📄 Incident Report",
    "🔍 Search & Retrieve",
    "👤 User Management",
]
ADMIN_ONLY = {"👤 User Management"}

ADMIN_USER = {"user_id": 1, "username": "commander", "role": "Admin"}
VIEWER_USER = {"user_id": 2, "username": "dispatcher", "role": "Viewer"}


def report(at: AppTest, label: str) -> int:
    """Print the status of one page run and return the number of exceptions."""
    exceptions = [e.value for e in at.exception]
    print(f"  [{label}] exceptions={len(exceptions)}")
    for exc in exceptions:
        print("      EXCEPTION:", str(exc).splitlines()[-1][:250])
    return len(exceptions)


def goto(at: AppTest, page: str) -> None:
    """Switch the sidebar navigation to ``page`` and re-run the script."""
    at.session_state["page"] = page
    at.session_state["nav_radio"] = page
    at.run()


def sign_in(at: AppTest, username: str, password: str) -> None:
    """
    Complete the police sign-in form.

    The submit button is located by its label because the two mode-switch
    buttons at the very top of the page also appear in the button list.
    """
    at.text_input[0].set_value(username)
    at.text_input[1].set_value(password)
    for button in at.button:
        if "Sign in" in str(button.label):
            button.click().run()
            return
    raise AssertionError("The 'Sign in' button was not found on the login page.")


def main() -> int:
    total = 0

    print("== 1. police login page ==")
    at = AppTest.from_file(APP_FILE, default_timeout=120)
    at.session_state["app_mode"] = "👮 Police Command"
    at.run()
    total += report(at, "login page")

    print("\n== 2. rejected login ==")
    at.text_input[0].set_value("commander")
    at.text_input[1].set_value("wrong-password")
    for button in at.button:
        if "Sign in" in str(button.label):
            button.click().run()
            break
    errors = [str(e.value) for e in at.error]
    print(f"  [rejected] errors={len(errors)} -> {errors[:1]}")
    if not errors or "Invalid username or password" not in errors[0]:
        total += 1
        print("      FAIL: an invalid password was not rejected")

    print("\n== 3. successful admin login ==")
    sign_in(at, "commander", "npf123")
    total += report(at, "admin login")

    print("\n== 4. every page as Admin / Commander ==")
    for page in PAGES:
        goto(at, page)
        total += report(at, page)

    print("\n== 5. every permitted page as Viewer / Dispatcher ==")
    at.session_state["user"] = VIEWER_USER
    for page in [p for p in PAGES if p not in ADMIN_ONLY]:
        goto(at, page)
        total += report(at, f"viewer:{page}")

    options = at.sidebar.radio[0].options if at.sidebar.radio else []
    leaked = [o for o in options if o in ADMIN_ONLY]
    print(f"  [role check] admin-only pages visible to the viewer: {leaked or 'none'}")
    if leaked:
        total += 1

    print("\n== 6. search functionality ==")
    at.session_state["user"] = ADMIN_USER
    goto(at, "🔍 Search & Retrieve")
    for needle in ("Nwankwo", "SOS-00001", "PATROL-01-OGUI", "Kidnapping", "zzz-no-match"):
        at.text_input[0].set_value(needle).run()
        total += report(at, f"search:'{needle}'")

    print(f"\n===== TOTAL EXCEPTIONS: {total} =====")
    return total


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
