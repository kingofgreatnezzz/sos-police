"""
app.py
=================================================================================
EMERGENCY RESPONSE AND SOS LOCATION TRACKING SYSTEM
Nigeria Police Force - Enugu State Command
---------------------------------------------------------------------------------
A Case Study implementation of a real-time distress-call management and
location-tracking platform for the Enugu State Police Command.

TECH STACK
    Python 3.10+ | Streamlit | SQLite | Pandas | Folium + streamlit-folium
    Haversine formula (nearest-unit calculation)

RUN
    python setup_db.py        (once, to build and seed the database)
    streamlit run app.py

DEFAULT ACCOUNTS
    commander  / npf123   -> Admin / Commander    (full access)
    dispatcher / npf123   -> Viewer / Dispatcher  (read-only)
=================================================================================
"""

from __future__ import annotations

import html as html_lib
import json
import random
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

import auth
import db
import haversine
import reports
import sounds

# =================================================================================
# 1. PAGE CONFIGURATION  (must be the first Streamlit call in the script)
# =================================================================================
st.set_page_config(
    page_title="NPF Enugu | Emergency Response & SOS Tracking",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =================================================================================
# 2. CONSTANTS
# =================================================================================
APP_NAME = "Emergency Response & SOS Location Tracking System"
COMMAND_NAME = "Nigeria Police Force — Enugu State Command"
APP_VERSION = "1.0.0"


# ---------------------------------------------------------------------------------
# Streamlit API compatibility shim
# ---------------------------------------------------------------------------------
# Streamlit 1.49 renamed the `use_container_width` argument to `width`, and the old
# name is scheduled for removal.  These dictionaries let the application run
# unchanged on both the older and the current API.  (streamlit-folium's own `width`
# argument means a pixel width, so st_folium deliberately keeps using
# `use_container_width`.)
def _supports_stretch_width() -> bool:
    """True when this Streamlit build accepts width='stretch'."""
    try:
        major, minor = str(st.__version__).split(".")[:2]
        return (int(major), int(minor)) >= (1, 49)
    except (ValueError, AttributeError, TypeError):
        return False


if _supports_stretch_width():
    FULL_WIDTH: dict = {"width": "stretch"}
    CONTENT_WIDTH: dict = {"width": "content"}
else:  # pragma: no cover - older Streamlit builds
    FULL_WIDTH = {"use_container_width": True}
    CONTENT_WIDTH = {"use_container_width": False}


EMERGENCY_TYPES = ["Armed Robbery", "Kidnapping", "Accident", "Medical", "Other"]
ALERT_STATUSES = ["Active", "Dispatched", "Resolved", "False Alarm"]
UNIT_STATUSES = ["Available", "Dispatched", "Offline"]

# Colour / iconography used consistently across the map and the UI
STATUS_META = {
    "Active":      {"colour": "#c62828", "bg": "#ffebee", "icon": "🔴"},
    "Dispatched":  {"colour": "#ef6c00", "bg": "#fff3e0", "icon": "🟠"},
    "Resolved":    {"colour": "#2e7d32", "bg": "#e8f5e9", "icon": "🟢"},
    "False Alarm": {"colour": "#616161", "bg": "#f5f5f5", "icon": "⚪"},
}

UNIT_STATUS_META = {
    "Available":  {"colour": "#2e7d32", "icon": "🟢"},
    "Dispatched": {"colour": "#ef6c00", "icon": "🟠"},
    "Offline":    {"colour": "#9e9e9e", "icon": "⚫"},
}

TYPE_ICON = {
    "Armed Robbery": "🔫",
    "Kidnapping": "🚷",
    "Accident": "🚗",
    "Medical": "🚑",
    "Other": "📞",
}

MAP_REFRESH_SECONDS = 3
ENUGU_CENTER = [haversine.ENUGU_CENTER_LAT, haversine.ENUGU_CENTER_LON]
DEFAULT_SPEED_KMH = 40.0

# Locations used by the SOS simulator so demo alerts land on real Enugu spots.
SIMULATION_SPOTS = [
    ("Ogui Road, by Ogui Urban", 6.4521, 7.5089),
    ("Abakpa Nike Market", 6.4712, 7.5134),
    ("Ogbete Main Market", 6.4448, 7.4988),
    ("Trans-Ekulu Expressway", 6.4356, 7.4892),
    ("Independence Layout, Nza Street", 6.4398, 7.4956),
    ("Nsukka, Odenigbo Junction", 6.8523, 7.3934),
    ("GRA, Enugu (Abakaliki Road)", 6.4483, 7.5023),
    ("Emene Industrial Layout", 6.4602, 7.5498),
    ("Uwani, Enugu", 6.4312, 7.5002),
    ("New Haven, Enugu", 6.4567, 7.4812),
]

SIMULATION_NAMES = [
    "Mr. Chinedu Alumona", "Mrs. Adaobi Nnaji", "Miss Peace Okoro",
    "Mr. Samuel Ugwu", "Chief Bernard Onah", "Mrs. Grace Ogbonna",
    "Mr. Kingsley Ede", "Miss Amarachi Nwali", "Mr. Tobenna Ani",
    "Mrs. Rita Chukwu",
]

SIMULATION_NARRATIVES = {
    "Armed Robbery": "Armed men are robbing {place}. Shots are being fired and members of the public are scampering for safety.",
    "Kidnapping": "Suspicious persons in a vehicle have abducted a victim near {place}. The vehicle is heading towards the expressway.",
    "Accident": "A road traffic crash has just occurred at {place}. Casualties are trapped and traffic is building up.",
    "Medical": "A person has collapsed at {place} and requires urgent medical evacuation.",
    "Other": "Disturbance of public peace reported at {place}. Please assess before deploying a team.",
}


# =================================================================================
# 3. STYLING  (professional navy / gold police theme)
# =================================================================================
CUSTOM_CSS = """
<style>
    /* ---------- global ---------- */
    .block-container { padding-top: 1.3rem; padding-bottom: 2.5rem; max-width: 1550px; }
    html, body, [class*="css"] { font-family: "Segoe UI", "Inter", Arial, sans-serif; }

    /* ---------- command header ---------- */
    .npf-header {
        background: linear-gradient(120deg, #0b2545 0%, #13315c 55%, #1b4079 100%);
        border-radius: 12px; padding: 18px 26px; margin-bottom: 18px;
        box-shadow: 0 6px 18px rgba(11,37,69,.28);
        border-left: 6px solid #ffd54f;
    }
    .npf-header h1 {
        color: #ffffff; font-size: 24px; font-weight: 700; margin: 0;
        letter-spacing: .3px;
    }
    .npf-header p { color: #b8c7dc; margin: 4px 0 0 0; font-size: 13px; letter-spacing: .4px; }
    .npf-header .badge {
        display: inline-block; background: #ffd54f; color: #0b2545;
        font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 10px;
        margin-left: 10px; vertical-align: middle; letter-spacing: .6px;
    }

    /* ---------- metric cards ---------- */
    div[data-testid="stMetric"] {
        background: #ffffff; border: 1px solid #dde3ea; border-radius: 12px;
        padding: 14px 16px 12px 16px; box-shadow: 0 2px 8px rgba(16,39,57,.07);
        border-top: 4px solid #0b2545;
    }
    div[data-testid="stMetricLabel"] > div { font-size: 13px !important; color: #546e7a !important; font-weight: 600; }
    div[data-testid="stMetricValue"] { font-size: 28px !important; color: #102027; font-weight: 700; }

    /* ---------- section titles ---------- */
    .section-title {
        font-size: 15px; font-weight: 700; color: #0b2545; margin: 6px 0 10px 0;
        padding-left: 10px; border-left: 4px solid #ffd54f; letter-spacing: .3px;
    }

    /* ---------- status pills ---------- */
    .pill {
        display: inline-block; padding: 3px 11px; border-radius: 11px;
        font-size: 11.5px; font-weight: 700; letter-spacing: .4px;
    }

    /* ---------- info cards ---------- */
    .info-card {
        background: #ffffff; border: 1px solid #dde3ea; border-left: 5px solid #0b2545;
        border-radius: 10px; padding: 13px 16px; margin-bottom: 10px;
        box-shadow: 0 2px 6px rgba(16,39,57,.06);
    }
    .info-card.rank1 { border-left-color: #2e7d32; background: #f4fbf5; }
    .info-card.rank2 { border-left-color: #ef6c00; background: #fffaf3; }
    .info-card.rank3 { border-left-color: #1b4079; background: #f5f8fd; }
    .info-card .callsign { font-size: 16px; font-weight: 700; color: #102027; }
    .info-card .officer { font-size: 13px; color: #455a64; margin-top: 2px; }
    .info-card .stats { font-size: 13px; color: #102027; margin-top: 7px; }
    .info-card .stats b { color: #0b2545; }

    /* ---------- alert banner ---------- */
    .alert-banner {
        background: linear-gradient(90deg, #b71c1c 0%, #e53935 100%);
        color: #ffffff; padding: 14px 20px; border-radius: 10px;
        font-size: 14.5px; font-weight: 600; margin-bottom: 14px;
        box-shadow: 0 4px 14px rgba(183,28,28,.35);
        animation: pulse 1.8s infinite;
    }
    @keyframes pulse {
        0%   { box-shadow: 0 4px 14px rgba(183,28,28,.35); }
        50%  { box-shadow: 0 4px 22px rgba(183,28,28,.75); }
        100% { box-shadow: 0 4px 14px rgba(183,28,28,.35); }
    }

    /* ---------- activity feed ---------- */
    .feed-item {
        border-left: 3px solid #cfd8dc; padding: 7px 0 7px 13px; margin-bottom: 4px;
        font-size: 13px; color: #263238;
    }
    .feed-item .meta { font-size: 11.5px; color: #78909c; margin-top: 2px; }

    /* ---------- legend ---------- */
    .legend { font-size: 12.5px; color: #37474f; padding: 8px 12px;
              background: #f7f9fc; border-radius: 8px; border: 1px solid #e2e8f0; }
    .legend span.dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; }

    /* ---------- login ---------- */
    .login-hero {
        background: linear-gradient(150deg, #0b2545 0%, #13315c 60%, #1b4079 100%);
        border-radius: 14px; padding: 34px 30px; color: #ffffff; height: 100%;
        box-shadow: 0 8px 26px rgba(11,37,69,.3);
    }
    .login-hero h2 { color: #ffffff; font-size: 22px; margin: 0 0 6px 0; }
    .login-hero .sub { color: #b8c7dc; font-size: 13px; letter-spacing: .5px; }
    .login-hero ul { margin-top: 18px; padding-left: 18px; color: #dbe6f3; font-size: 13.5px; line-height: 1.85; }
    .login-hero .creds {
        margin-top: 22px; background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.22);
        border-radius: 10px; padding: 12px 15px; font-size: 12.5px; color: #e8f0fa;
    }
    .login-hero .creds code { background: #ffd54f; color: #0b2545; padding: 1px 6px; border-radius: 4px; font-weight: 700; }

    /* ---------- misc ---------- */
    .small-note { font-size: 12px; color: #78909c; }
    div[data-testid="stDataFrame"] { border-radius: 8px; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] {
        background: #f1f5f9; border-radius: 8px 8px 0 0; padding: 7px 15px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background: #0b2545 !important; color: #ffffff !important; }
    footer, #MainMenu { visibility: hidden; }
</style>
"""


# =================================================================================
# 4. GENERAL HELPERS
# =================================================================================
def format_timestamp(value) -> str:
    """Render a stored UTC timestamp as West Africa Time (UTC+1)."""
    if value in (None, "", "None"):
        return "—"
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            stamp = datetime.strptime(text, fmt)
            return (stamp + timedelta(hours=1)).strftime("%d %b %Y, %H:%M WAT")
        except ValueError:
            continue
    return text


def rel_time(value) -> str:
    """Relative time such as '6 minutes ago', used in the activity feed."""
    if not value:
        return ""
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            stamp = datetime.strptime(text, fmt)
            delta = datetime.utcnow() - stamp
            seconds = int(delta.total_seconds())
            if seconds < 60:
                return "just now"
            if seconds < 3600:
                return f"{seconds // 60} min ago"
            if seconds < 86400:
                return f"{seconds // 3600} hr ago"
            return f"{seconds // 86400} day(s) ago"
        except ValueError:
            continue
    return ""


def status_pill(status: str) -> str:
    """Return an HTML pill for an alert status."""
    meta = STATUS_META.get(status, {"colour": "#424242", "bg": "#eeeeee"})
    return (
        f'<span class="pill" style="background:{meta["bg"]};color:{meta["colour"]};'
        f'border:1px solid {meta["colour"]}44;">{html_lib.escape(str(status)).upper()}</span>'
    )


def unit_status_pill(status: str) -> str:
    meta = UNIT_STATUS_META.get(status, {"colour": "#424242"})
    return (
        f'<span class="pill" style="background:{meta["colour"]}1a;color:{meta["colour"]};'
        f'border:1px solid {meta["colour"]}44;">{html_lib.escape(str(status)).upper()}</span>'
    )


def command_header(title: str, subtitle: str, badge: str = "") -> None:
    """Render the navy command header used at the top of every page."""
    badge_html = f'<span class="badge">{html_lib.escape(badge)}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="npf-header">
            <h1>{html_lib.escape(title)}{badge_html}</h1>
            <p>{html_lib.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(text: str) -> None:
    st.markdown(f'<div class="section-title">{html_lib.escape(text)}</div>', unsafe_allow_html=True)


def nav_callback(page_label: str, updates: dict | None = None) -> None:
    """
    ``on_click`` callback that moves the user to another page.

    Callbacks run *before* the script body of the rerun, which is the only
    moment at which Streamlit allows the sidebar radio's widget key
    (``nav_radio``) to be written to.  Any extra session state (for example
    the incident to focus on) is applied at the same time.
    """
    if updates:
        for key, value in updates.items():
            st.session_state[key] = value
    st.session_state["page"] = page_label
    st.session_state["nav_radio"] = page_label


def goto(page_label: str) -> None:
    """
    Navigate to another page from inside a page body (fallback route).

    Used where an ``on_click`` callback cannot be attached.  The request is
    recorded and applied at the *start* of the next run by ``render_sidebar``,
    which avoids Streamlit's "cannot modify a widget key after the widget was
    instantiated" restriction.
    """
    st.session_state["page"] = page_label
    st.session_state["_nav_request"] = page_label
    st.rerun()


def notify(kind: str, message: str) -> None:
    """Queue a toast so it survives the st.rerun() that follows a write."""
    st.session_state.setdefault("pending_toasts", []).append((kind, message))


def flush_toasts() -> None:
    """Display and clear any queued toast messages."""
    for kind, message in st.session_state.get("pending_toasts", []):
        try:
            if kind == "success":
                st.toast(message, icon="✅")
            elif kind == "error":
                st.toast(message, icon="⛔")
            elif kind == "warning":
                st.toast(message, icon="⚠️")
            else:
                st.toast(message, icon="ℹ️")
        except Exception:
            # Older Streamlit versions may not support st.toast.
            st.success(message)
    st.session_state["pending_toasts"] = []


# ---------------------------------------------------------------------------------
# Data access wrappers with graceful error handling
# ---------------------------------------------------------------------------------
def safe_fetch_all(query: str, params=(), context: str = "records") -> list[dict]:
    try:
        return db.fetch_all(query, params)
    except db.DatabaseError as exc:
        st.error(f"Unable to load {context} from the database. {exc}")
        return []


def safe_fetch_one(query: str, params=(), context: str = "record"):
    try:
        return db.fetch_one(query, params)
    except db.DatabaseError as exc:
        st.error(f"Unable to load {context}. {exc}")
        return None


def load_alerts() -> list[dict]:
    return safe_fetch_all(
        """
        SELECT a.*, u.unit_callsign AS assigned_callsign, u.officer_name AS assigned_officer
        FROM sos_alerts a
        LEFT JOIN patrol_units u ON u.unit_id = a.assigned_unit_id
        ORDER BY a.alert_id DESC
        """,
        context="SOS alerts",
    )


def load_units() -> list[dict]:
    return safe_fetch_all(
        "SELECT * FROM patrol_units ORDER BY unit_callsign", context="patrol units"
    )


def load_stations() -> list[dict]:
    return safe_fetch_all(
        "SELECT * FROM police_stations ORDER BY station_name", context="police stations"
    )


def get_alert(alert_id: int) -> dict | None:
    return safe_fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (alert_id,), "the alert")


# =================================================================================
# 5. BUSINESS LOGIC  (dispatch, resolve, delete, simulate)
# =================================================================================
def dispatch_unit(alert_id: int, unit_id: int, actor: str) -> tuple[bool, str]:
    """
    Assign a patrol unit to an SOS alert.

    Effects (all or nothing):
      * alert  -> status 'Dispatched', assigned_unit_id set
      * unit   -> status 'Dispatched', last_updated refreshed
      * audit trail entry written
    """
    try:
        alert = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (alert_id,))
        unit = db.fetch_one("SELECT * FROM patrol_units WHERE unit_id = ?", (unit_id,))

        if not alert:
            return False, "The selected SOS alert no longer exists."
        if not unit:
            return False, "The selected patrol unit no longer exists."
        if alert["status"] in ("Resolved", "False Alarm"):
            return False, "A closed incident cannot receive a dispatch. Re-open it first."

        distance = haversine.calculate_distance(
            alert["latitude"], alert["longitude"],
            unit["current_lat"], unit["current_long"],
        )
        eta = haversine.estimate_arrival_time(distance)

        db.execute_query(
            "UPDATE sos_alerts SET status = 'Dispatched', assigned_unit_id = ? WHERE alert_id = ?",
            (unit_id, alert_id),
        )
        db.execute_query(
            "UPDATE patrol_units SET status = 'Dispatched', last_updated = CURRENT_TIMESTAMP "
            "WHERE unit_id = ?",
            (unit_id,),
        )
        db.log_activity(
            "UNIT_DISPATCHED",
            f"{unit['unit_callsign']} dispatched to SOS-{alert_id:05d} "
            f"({distance:.2f} km away, ETA {haversine.format_eta(eta)})",
            actor=actor,
            alert_id=alert_id,
        )
        return True, (
            f"{unit['unit_callsign']} dispatched to SOS-{alert_id:05d}. "
            f"Distance {distance:.2f} km — ETA {haversine.format_eta(eta)}."
        )
    except db.DatabaseError as exc:
        return False, str(exc)


def close_alert(alert_id: int, status: str, actor: str) -> tuple[bool, str]:
    """Mark an alert Resolved or False Alarm and release its patrol unit."""
    if status not in ("Resolved", "False Alarm"):
        return False, "Invalid closing status."

    try:
        alert = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (alert_id,))
        if not alert:
            return False, "The selected SOS alert no longer exists."

        db.execute_query(
            "UPDATE sos_alerts SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE alert_id = ?",
            (status, alert_id),
        )

        if alert.get("assigned_unit_id"):
            db.execute_query(
                "UPDATE patrol_units SET status = 'Available', last_updated = CURRENT_TIMESTAMP "
                "WHERE unit_id = ? AND status = 'Dispatched'",
                (alert["assigned_unit_id"],),
            )

        db.log_activity(
            "ALERT_CLOSED",
            f"SOS-{alert_id:05d} marked as {status}",
            actor=actor,
            alert_id=alert_id,
        )
        return True, f"SOS-{alert_id:05d} has been marked as {status}."
    except db.DatabaseError as exc:
        return False, str(exc)


def reopen_alert(alert_id: int, actor: str) -> tuple[bool, str]:
    """Return a closed alert to the Active queue."""
    try:
        affected = db.execute_query(
            "UPDATE sos_alerts SET status = 'Active', resolved_at = NULL WHERE alert_id = ?",
            (alert_id,),
        )
        if affected == 0:
            return False, "The selected SOS alert no longer exists."
        db.log_activity("ALERT_REOPENED", f"SOS-{alert_id:05d} re-opened as Active",
                        actor=actor, alert_id=alert_id)
        return True, f"SOS-{alert_id:05d} re-opened and returned to the active queue."
    except db.DatabaseError as exc:
        return False, str(exc)


def delete_alert(alert_id: int, actor: str) -> tuple[bool, str]:
    """Permanently delete an alert and free any unit that was attached."""
    try:
        alert = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (alert_id,))
        if not alert:
            return False, "The selected SOS alert no longer exists."

        if alert.get("assigned_unit_id"):
            db.execute_query(
                "UPDATE patrol_units SET status = 'Available', last_updated = CURRENT_TIMESTAMP "
                "WHERE unit_id = ? AND status = 'Dispatched'",
                (alert["assigned_unit_id"],),
            )

        db.execute_query("DELETE FROM sos_alerts WHERE alert_id = ?", (alert_id,))
        db.log_activity(
            "ALERT_DELETED",
            f"SOS-{alert_id:05d} ({alert['emergency_type']}, {alert['citizen_name']}) deleted",
            actor=actor,
        )
        return True, f"SOS-{alert_id:05d} deleted from the register."
    except db.DatabaseError as exc:
        return False, str(exc)


def create_alert(payload: dict, actor: str) -> tuple[bool, str, int | None]:
    """Insert a new SOS alert (used by both the form and the simulator)."""
    try:
        alert_id = db.execute_query(
            """
            INSERT INTO sos_alerts
                (citizen_name, phone_number, latitude, longitude,
                 emergency_type, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["citizen_name"], payload["phone_number"],
                payload["latitude"], payload["longitude"],
                payload["emergency_type"], payload.get("description", ""),
                payload.get("status", "Active"),
            ),
        )
        db.log_activity(
            "ALERT_RECEIVED",
            f"SOS-{alert_id:05d} — {payload['emergency_type']} reported by "
            f"{payload['citizen_name']} ({payload['latitude']:.4f}, {payload['longitude']:.4f})",
            actor=actor,
            alert_id=alert_id,
        )
        return True, f"SOS-{alert_id:05d} logged successfully.", alert_id
    except db.DatabaseError as exc:
        return False, str(exc), None


def simulate_incoming_alert(actor: str) -> tuple[bool, str, int | None]:
    """Generate a realistic random distress call for demonstration."""
    place, lat, lon = random.choice(SIMULATION_SPOTS)
    emergency_type = random.choice(EMERGENCY_TYPES)
    payload = {
        "citizen_name": random.choice(SIMULATION_NAMES),
        "phone_number": "0" + random.choice(["703", "803", "806", "810", "813", "816", "909"])
                        + f"{random.randint(0, 9999999):07d}",
        "latitude": round(lat + random.uniform(-0.004, 0.004), 6),
        "longitude": round(lon + random.uniform(-0.004, 0.004), 6),
        "emergency_type": emergency_type,
        "description": SIMULATION_NARRATIVES[emergency_type].format(place=place)
                       + " Caller is requesting immediate police intervention.",
        "status": "Active",
    }
    return create_alert(payload, actor)


def build_folium_map(
    alerts: list[dict],
    units: list[dict],
    stations: list[dict],
    highlight_alert_id: int | None = None,
    nearest_matches: list[dict] | None = None,
    map_key: str = "map",
) -> folium.Map:
    """
    Build the interactive Enugu State command map.

    Layers
        red    marker -> SOS alert (colour follows the alert status)
        green  marker -> available patrol unit (orange dispatched, grey offline)
        blue   marker -> police station
    """
    fmap = folium.Map(
        location=ENUGU_CENTER,
        zoom_start=11,
        tiles="CartoDB positron",
        control_scale=True,
        prefer_canvas=True,
    )

    # ---- alternate base layers -------------------------------------------
    folium.TileLayer("OpenStreetMap", name="Street map").add_to(fmap)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
              "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite imagery", overlay=False,
    ).add_to(fmap)

    alert_layer = folium.FeatureGroup(name="🚨 SOS alerts", show=True)
    unit_layer = folium.FeatureGroup(name="🚔 Patrol units", show=True)
    station_layer = folium.FeatureGroup(name="🏛️ Police stations", show=True)

    bounds: list[list[float]] = []

    # ---- SOS alerts -------------------------------------------------------
    for alert in alerts:
        try:
            lat, lon = float(alert["latitude"]), float(alert["longitude"])
        except (TypeError, ValueError, KeyError):
            continue
        bounds.append([lat, lon])

        status = alert.get("status", "Active")
        is_active = status == "Active"
        is_highlight = highlight_alert_id is not None and alert.get("alert_id") == highlight_alert_id
        colour = "red" if is_active else {
            "Dispatched": "orange", "Resolved": "green", "False Alarm": "gray"
        }.get(status, "red")

        popup_html = f"""
        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:12.5px;width:270px">
            <div style="background:#0b2545;color:#fff;padding:7px 10px;margin:-10px -10px 8px -10px;
                        font-weight:700;letter-spacing:.4px">
                SOS-{int(alert.get('alert_id', 0)):05d} &nbsp;|&nbsp; {html_lib.escape(str(alert.get('emergency_type','')))}
            </div>
            <table style="width:100%;border-collapse:collapse">
                <tr><td style="color:#607d8b;padding:2px 0">Citizen</td>
                    <td style="font-weight:600">{html_lib.escape(str(alert.get('citizen_name','')))}</td></tr>
                <tr><td style="color:#607d8b;padding:2px 0">Phone</td>
                    <td>{html_lib.escape(str(alert.get('phone_number','')))}</td></tr>
                <tr><td style="color:#607d8b;padding:2px 0">Status</td>
                    <td style="font-weight:700;color:{STATUS_META.get(status,{}).get('colour','#000')}">{html_lib.escape(status)}</td></tr>
                <tr><td style="color:#607d8b;padding:2px 0">Received</td>
                    <td>{html_lib.escape(format_timestamp(alert.get('created_at')))}</td></tr>
                <tr><td style="color:#607d8b;padding:2px 0">Coords</td>
                    <td style="font-family:Consolas,monospace">{lat:.5f}, {lon:.5f}</td></tr>
            </table>
            <div style="margin-top:7px;padding-top:6px;border-top:1px solid #eceff1;color:#37474f">
                {html_lib.escape(str(alert.get('description') or 'No description provided.')[:190])}
            </div>
        </div>
        """

        icon = folium.Icon(
            color=colour, icon="bell" if is_active else "info-sign",
            prefix="fa" if is_active else "glyphicon",
        )
        marker = folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=(f"SOS-{int(alert.get('alert_id', 0)):05d} • "
                     f"{alert.get('emergency_type','')} • {status}"),
            icon=icon,
        )
        marker.add_to(alert_layer)

        if is_active:
            # Pulsing-style emphasis ring around open incidents
            folium.Circle(
                location=[lat, lon], radius=220, color="#c62828", weight=1.6,
                fill=True, fill_opacity=0.12,
            ).add_to(alert_layer)

        if is_highlight:
            folium.Circle(
                location=[lat, lon], radius=420, color="#ffd54f", weight=4,
                fill=False, dash_array="8",
            ).add_to(alert_layer)
            folium.Marker(
                location=[lat + 0.0022, lon],
                icon=folium.DivIcon(
                    html='<div style="font-size:11px;font-weight:700;color:#b71c1c;'
                         'background:#fff3cd;border:1px solid #ffd54f;border-radius:4px;'
                         'padding:2px 6px;white-space:nowrap;">SELECTED INCIDENT</div>'
                ),
            ).add_to(alert_layer)

    # ---- patrol units -----------------------------------------------------
    for unit in units:
        try:
            lat, lon = float(unit["current_lat"]), float(unit["current_long"])
        except (TypeError, ValueError, KeyError):
            continue
        bounds.append([lat, lon])

        status = unit.get("status", "Offline")
        colour = {"Available": "green", "Dispatched": "orange", "Offline": "gray"}.get(status, "gray")

        popup_html = f"""
        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:12.5px;width:255px">
            <div style="background:#1b5e20;color:#fff;padding:7px 10px;margin:-10px -10px 8px -10px;
                        font-weight:700;letter-spacing:.4px">
                🚔 {html_lib.escape(str(unit.get('unit_callsign','')))}
            </div>
            <table style="width:100%;border-collapse:collapse">
                <tr><td style="color:#607d8b;padding:2px 0">Officer</td>
                    <td style="font-weight:600">{html_lib.escape(str(unit.get('officer_name','')))}</td></tr>
                <tr><td style="color:#607d8b;padding:2px 0">Status</td>
                    <td style="font-weight:700;color:{UNIT_STATUS_META.get(status,{}).get('colour','#000')}">{html_lib.escape(status)}</td></tr>
                <tr><td style="color:#607d8b;padding:2px 0">Position</td>
                    <td style="font-family:Consolas,monospace">{lat:.5f}, {lon:.5f}</td></tr>
                <tr><td style="color:#607d8b;padding:2px 0">Updated</td>
                    <td>{html_lib.escape(format_timestamp(unit.get('last_updated')))}</td></tr>
            </table>
        </div>
        """

        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=285),
            tooltip=f"{unit.get('unit_callsign','')} • {status}",
            icon=folium.Icon(color=colour, icon="car", prefix="fa"),
        ).add_to(unit_layer)

    # ---- police stations --------------------------------------------------
    for station in stations:
        try:
            lat, lon = float(station["latitude"]), float(station["longitude"])
        except (TypeError, ValueError, KeyError):
            continue
        bounds.append([lat, lon])

        popup_html = f"""
        <div style="font-family:Segoe UI,Arial,sans-serif;font-size:12.5px;width:250px">
            <div style="background:#0d47a1;color:#fff;padding:7px 10px;margin:-10px -10px 8px -10px;
                        font-weight:700">
                🏛️ {html_lib.escape(str(station.get('station_name','')))}
            </div>
            <div style="color:#37474f">{html_lib.escape(str(station.get('address') or 'Address not recorded'))}</div>
            <div style="margin-top:6px;font-family:Consolas,monospace;color:#546e7a">
                {lat:.5f}, {lon:.5f}
            </div>
        </div>
        """
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"🏛️ {station.get('station_name','')}",
            icon=folium.Icon(color="blue", icon="home", prefix="fa"),
        ).add_to(station_layer)

    # ---- dispatch route lines for the nearest-unit calculator -------------
    if nearest_matches:
        target = next(
            (a for a in alerts if highlight_alert_id and a.get("alert_id") == highlight_alert_id),
            None,
        )
        if target:
            route_layer = folium.FeatureGroup(name="📏 Nearest-unit routes", show=True)
            for index, match in enumerate(nearest_matches):
                folium.PolyLine(
                    locations=[[float(target["latitude"]), float(target["longitude"])],
                               [match["lat"], match["lon"]]],
                    color="#2e7d32" if index == 0 else "#1b4079",
                    weight=4 if index == 0 else 2,
                    opacity=0.85 if index == 0 else 0.6,
                    dash_array=None if index == 0 else "7",
                    tooltip=(f"{match['unit_callsign']} — {match['distance_km']:.2f} km "
                             f"(ETA {match['eta_text']})"),
                ).add_to(route_layer)
            route_layer.add_to(fmap)

    alert_layer.add_to(fmap)
    unit_layer.add_to(fmap)
    station_layer.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)

    # Fit the view to whatever data we actually have.
    if bounds:
        fmap.fit_bounds(haversine.bounding_box(bounds, padding=0.012))

    return fmap


# =================================================================================
# 6. LOGIN PAGE
# =================================================================================
def render_login() -> None:
    """Full-page login screen with role explanation and demo credentials."""
    left, right = st.columns([1.25, 1], gap="large")

    with left:
        st.markdown(
            f"""
            <div class="login-hero">
                <div style="font-size:42px;line-height:1">🚨</div>
                <h2>{html_lib.escape(APP_NAME)}</h2>
                <div class="sub">{html_lib.escape(COMMAND_NAME)}</div>
                <ul>
                    <li>Real-time SOS distress call intake and tracking</li>
                    <li>Live command map of incidents, patrol units and divisions</li>
                    <li>Automatic nearest-unit calculation (Haversine formula)</li>
                    <li>Dispatch management, incident reports and audit trail</li>
                </ul>
                <div class="creds">
                    <div style="font-weight:700;margin-bottom:6px">Demonstration accounts</div>
                    <div>Commander (full access): <code>commander</code> / <code>npf123</code></div>
                    <div style="margin-top:4px">Dispatcher (read-only): <code>dispatcher</code> / <code>npf123</code></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        st.markdown("### 🔐 Officer Sign-in")
        st.caption("Authorised personnel of the Enugu State Command only.")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="commander", autocomplete="username")
            password = st.text_input("Password", type="password", placeholder="••••••",
                                     autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", **FULL_WIDTH, type="primary")

        if submitted:
            success, message, user = auth.authenticate(username, password)
            if success:
                st.session_state["user"] = user
                st.session_state["login_time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["last_seen_alert_id"] = db.fetch_scalar(
                    "SELECT COALESCE(MAX(alert_id), 0) FROM sos_alerts", default=0
                )
                db.log_activity("LOGIN", f"{user['username']} signed in as {user['role']}",
                                actor=user["username"])
                st.rerun()
            else:
                st.error(f"⛔ {message}")

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        with st.expander("ℹ️ About this system"):
            st.markdown(
                f"""
                **{APP_NAME}**

                Version {APP_VERSION} · Built with Python, Streamlit, SQLite, Pandas and Folium.

                This prototype demonstrates how the Enugu State Police Command can receive
                citizen distress calls, plot them instantly on a command map, and dispatch the
                nearest patrol unit using the Haversine great-circle distance formula.

                *All data in this demonstration database is sample data.*
                """
            )

    st.markdown(
        "<div class='small-note' style='text-align:center;margin-top:26px'>"
        f"{html_lib.escape(COMMAND_NAME)} · Control Room Portal · v{APP_VERSION}"
        "</div>",
        unsafe_allow_html=True,
    )


# =================================================================================
# 7. PAGE: COMMAND DASHBOARD
# =================================================================================
def page_dashboard() -> None:
    command_header(
        "Command Dashboard",
        f"{COMMAND_NAME} · Real-time operational overview",
        badge="LIVE",
    )

    alerts = load_alerts()
    units = load_units()
    stations = load_stations()

    active_alerts = [a for a in alerts if a["status"] == "Active"]
    dispatched_alerts = [a for a in alerts if a["status"] == "Dispatched"]
    available_units = [u for u in units if u["status"] == "Available"]
    dispatched_units = [u for u in units if u["status"] == "Dispatched"]

    incidents_today = db.fetch_scalar(
        """
        SELECT COUNT(*) FROM sos_alerts
        WHERE date(created_at, '+1 hour') = date('now', '+1 hour')
        """,
        default=0,
    )
    avg_response = db.fetch_scalar(
        """
        SELECT ROUND(AVG((julianday(resolved_at) - julianday(created_at)) * 1440.0), 1)
        FROM sos_alerts
        WHERE resolved_at IS NOT NULL
        """,
        default=None,
    )

    # ---------------- KPI cards -------------------------------------------
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    with c1:
        st.metric(
            "🚨 Active SOS Alerts", len(active_alerts),
            delta=f"{len(dispatched_alerts)} dispatched" if dispatched_alerts else None,
            delta_color="off",
            help="Distress calls currently awaiting resolution.",
        )
    with c2:
        st.metric(
            "📞 Total Incidents Today", int(incidents_today or 0),
            help="All SOS alerts logged since midnight (West Africa Time).",
        )
    with c3:
        st.metric(
            "🚔 Available Patrol Units", len(available_units),
            delta=f"of {len(units)} on strength", delta_color="off",
            help="Units ready for immediate dispatch.",
        )
    with c4:
        st.metric(
            "⏱️ Average Response Time",
            f"{float(avg_response):.1f} min" if avg_response is not None else "—",
            help="Mean time between receiving a call and closing the incident.",
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # ---------------- active incident banner ------------------------------
    if active_alerts:
        newest = max(active_alerts, key=lambda a: a["alert_id"])
        st.markdown(
            f"""
            <div class="alert-banner">
                🚨 ACTIVE EMERGENCY — SOS-{int(newest['alert_id']):05d} ·
                {html_lib.escape(str(newest['emergency_type']))} ·
                {html_lib.escape(str(newest['citizen_name']))} ·
                received {html_lib.escape(rel_time(newest['created_at']))}.
                &nbsp;{len(active_alerts)} open call(s) require attention.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.success("✅ No active SOS alerts at this time. All incidents have been attended to.")

    # ---------------- map + side panels -----------------------------------
    left, right = st.columns([2.05, 1], gap="medium")

    with left:
        section_title("🗺️ Command Overview Map")
        focus_id = st.session_state.get("focus_alert_id")
        fmap = build_folium_map(
            alerts=alerts, units=units, stations=stations,
            highlight_alert_id=focus_id, map_key="dash_map",
        )
        st_folium(fmap, height=430, use_container_width=True,
                  returned_objects=[], key="dashboard_map")
        st.markdown(
            "<div class='legend'>"
            "<span class='dot' style='background:#c62828'></span> Active SOS &nbsp;&nbsp;"
            "<span class='dot' style='background:#ef6c00'></span> Dispatched &nbsp;&nbsp;"
            "<span class='dot' style='background:#2e7d32'></span> Available unit / resolved &nbsp;&nbsp;"
            "<span class='dot' style='background:#0d47a1'></span> Police station &nbsp;&nbsp;"
            "<span class='dot' style='background:#9e9e9e'></span> Offline unit"
            "</div>",
            unsafe_allow_html=True,
        )

    with right:
        section_title("📋 Recent SOS Alerts")
        if alerts:
            for alert in alerts[:5]:
                st.markdown(
                    f"""
                    <div class="feed-item">
                        {TYPE_ICON.get(alert['emergency_type'], '📞')}
                        <b>SOS-{int(alert['alert_id']):05d}</b> — {html_lib.escape(str(alert['emergency_type']))}<br>
                        {html_lib.escape(str(alert['citizen_name']))} {status_pill(alert['status'])}
                        <div class="meta">{html_lib.escape(format_timestamp(alert['created_at']))}
                        · {html_lib.escape(rel_time(alert['created_at']))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No SOS alerts recorded yet. Use the SOS Alert Management page to log one.")

        section_title("🕒 Control Room Activity")
        activity = db.recent_activity(limit=6)
        if activity:
            for entry in activity:
                st.markdown(
                    f"""
                    <div class="feed-item">
                        <b>{html_lib.escape(str(entry['action']))}</b><br>
                        <span style="color:#455a64">{html_lib.escape(str(entry['details'] or ''))}</span>
                        <div class="meta">{html_lib.escape(str(entry['actor'] or 'system'))}
                        · {html_lib.escape(rel_time(entry['logged_at']))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No activity recorded yet.")

    # ---------------- analytics row ---------------------------------------
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    a1, a2, a3 = st.columns([1.2, 1, 1], gap="medium")

    with a1:
        section_title("📊 Incidents by Emergency Type")
        if alerts:
            type_counts = pd.Series(
                [a["emergency_type"] for a in alerts], name="Incidents"
            ).value_counts().rename_axis("Emergency type").to_frame()
            st.bar_chart(type_counts, height=230, color="#0b2545")
        else:
            st.caption("No data available.")

    with a2:
        section_title("📌 Alert Status Breakdown")
        if alerts:
            status_counts = pd.Series(
                [a["status"] for a in alerts], name="Alerts"
            ).value_counts().rename_axis("Status").to_frame()
            st.dataframe(status_counts, **FULL_WIDTH, height=230)
        else:
            st.caption("No data available.")

    with a3:
        section_title("🚔 Fleet Readiness")
        if units:
            unit_counts = pd.Series(
                [u["status"] for u in units], name="Units"
            ).value_counts().rename_axis("Unit status").to_frame()
            st.dataframe(unit_counts, **FULL_WIDTH, height=230)
            st.caption(f"Registered divisions: {len(stations)}")
        else:
            st.caption("No patrol units registered.")


# =================================================================================
# 8. PAGE: LIVE SOS MAP  (the flagship feature)
# =================================================================================
def _live_map_body() -> None:
    """Body of the live map; re-executed every few seconds by st.fragment."""
    alerts = load_alerts()
    units = load_units()
    stations = load_stations()

    active_alerts = [a for a in alerts if a["status"] == "Active"]
    available_units = [u for u in units if u["status"] == "Available"]

    # ---- detect a brand new alert since the last automatic refresh --------
    newest_id = max([int(a["alert_id"]) for a in alerts], default=0)
    previous_id = int(st.session_state.get("last_seen_alert_id") or 0)

    if newest_id > previous_id and previous_id:
        fresh = next((a for a in alerts if int(a["alert_id"]) == newest_id), None)
        if fresh:
            st.markdown(
                f"""
                <div class="alert-banner">
                    🆕 NEW SOS ALERT RECEIVED — SOS-{newest_id:05d} ·
                    {html_lib.escape(str(fresh['emergency_type']))} ·
                    {html_lib.escape(str(fresh['citizen_name']))} ·
                    {html_lib.escape(str(fresh['phone_number']))} ·
                    received {html_lib.escape(rel_time(fresh['created_at']))}.
                    Nearest available unit is being computed.
                </div>
                """,
                unsafe_allow_html=True,
            )
    if newest_id > previous_id:
        st.session_state["last_seen_alert_id"] = newest_id

    # ---- live status strip ------------------------------------------------
    m1, m2, m3, m4 = st.columns(4, gap="medium")
    m1.metric("🚨 Active SOS", len(active_alerts))
    m2.metric("🚔 Available units", len(available_units))
    m3.metric("🟠 Units dispatched", len([u for u in units if u["status"] == "Dispatched"]))
    m4.metric("🏛️ Divisions", len(stations))

    left, right = st.columns([2.6, 1], gap="medium")

    with left:
        fmap = build_folium_map(
            alerts=alerts, units=units, stations=stations,
            highlight_alert_id=st.session_state.get("focus_alert_id"),
            map_key="live_map",
        )
        st_folium(
            fmap, height=560, use_container_width=True,
            returned_objects=[], key="live_sos_map",
        )

    with right:
        section_title("🔴 Live Incident Queue")
        if active_alerts:
            for alert in sorted(active_alerts, key=lambda a: a["alert_id"], reverse=True):
                nearest = haversine.find_nearest_units(
                    alert["latitude"], alert["longitude"], units, top_n=1,
                    available_only=True,
                )
                eta_text = nearest[0]["eta_text"] if nearest else "no unit available"
                callsign = nearest[0]["unit_callsign"] if nearest else "—"

                st.markdown(
                    f"""
                    <div class="info-card">
                        <div class="callsign">{TYPE_ICON.get(alert['emergency_type'],'📞')}
                            SOS-{int(alert['alert_id']):05d}</div>
                        <div class="officer">{html_lib.escape(str(alert['emergency_type']))} ·
                            {html_lib.escape(str(alert['citizen_name']))}</div>
                        <div class="stats">📍 {float(alert['latitude']):.4f}, {float(alert['longitude']):.4f}<br>
                            🚔 Nearest: <b>{html_lib.escape(callsign)}</b> · ETA <b>{html_lib.escape(eta_text)}</b><br>
                            🕒 {html_lib.escape(rel_time(alert['created_at']))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.success("No active alerts. The Command area is calm.")

        st.markdown(
            "<div class='legend'>"
            "<span class='dot' style='background:#c62828'></span> Active SOS (pulsing ring)<br>"
            "<span class='dot' style='background:#ef6c00'></span> Dispatched incident / unit<br>"
            "<span class='dot' style='background:#2e7d32'></span> Available patrol unit<br>"
            "<span class='dot' style='background:#0d47a1'></span> Police division<br>"
            "<span class='dot' style='background:#9e9e9e'></span> Offline unit"
            "</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Map refreshes automatically every {MAP_REFRESH_SECONDS} seconds. "
            "Switch to the satellite layer from the layer control at the top-right of the map."
        )


# Wrap the body so it auto-refreshes every MAP_REFRESH_SECONDS.
if hasattr(st, "fragment"):
    _live_map_body_autorefresh = st.fragment(run_every=MAP_REFRESH_SECONDS)(_live_map_body)
else:  # pragma: no cover - very old Streamlit
    _live_map_body_autorefresh = _live_map_body


def page_live_map() -> None:
    command_header(
        "Live SOS Tracking Map",
        f"{COMMAND_NAME} · Real-time incident and patrol unit positions",
        badge="AUTO-REFRESH",
    )

    control_left, control_right = st.columns([1, 1])
    with control_left:
        auto = st.toggle(
            f"🔄 Auto-refresh every {MAP_REFRESH_SECONDS} seconds", value=True,
            help="Turn off to pan and zoom the map freely without it resetting.",
        )
    with control_right:
        if st.button("♻️ Refresh now"):
            st.rerun()

    if auth.is_admin():
        if st.button("🎲 Simulate an incoming SOS call", type="primary"):
            ok, message, alert_id = simulate_incoming_alert(auth.current_username())
            if ok:
                st.session_state["focus_alert_id"] = alert_id
                st.session_state["last_seen_alert_id"] = int(alert_id) - 1
                notify("error", f"🚨 {message}")
            else:
                notify("error", message)
            st.rerun()

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if auto:
        _live_map_body_autorefresh()
    else:
        _live_map_body()


# =================================================================================
# 9. PAGE: SOS ALERT MANAGEMENT (CRUD)
# =================================================================================
def page_sos_alerts() -> None:
    command_header(
        "SOS Alert Management",
        f"{COMMAND_NAME} · Intake, dispatch and closure of distress calls",
        badge="ADMIN" if auth.is_admin() else "READ-ONLY",
    )

    is_admin = auth.is_admin()
    alerts = load_alerts()
    units = load_units()

    # ---------------- filters ---------------------------------------------
    section_title("🔎 Filter the alert register")
    f1, f2, f3, f4 = st.columns([1, 1, 1, 1.4])
    with f1:
        status_filter = st.multiselect("Status", ALERT_STATUSES, default=[])
    with f2:
        type_filter = st.multiselect("Emergency type", EMERGENCY_TYPES, default=[])
    with f3:
        only_today = st.checkbox("Today only", value=False)
    with f4:
        text_filter = st.text_input("Search within alerts", placeholder="name, phone or description")

    filtered = alerts
    if status_filter:
        filtered = [a for a in filtered if a["status"] in status_filter]
    if type_filter:
        filtered = [a for a in filtered if a["emergency_type"] in type_filter]
    if only_today:
        today = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d")
        filtered = [
            a for a in filtered
            if (datetime.strptime(str(a["created_at"])[:10], "%Y-%m-%d") + timedelta(hours=1)
                ).strftime("%Y-%m-%d") == today
        ]
    if text_filter.strip():
        needle = text_filter.strip().lower()
        filtered = [
            a for a in filtered
            if needle in str(a["citizen_name"]).lower()
            or needle in str(a["phone_number"]).lower()
            or needle in str(a["emergency_type"]).lower()
            or needle in str(a["description"] or "").lower()
            or needle in f"sos-{int(a['alert_id']):05d}"
        ]

    # ---------------- register table --------------------------------------
    section_title(f"📋 Alert Register — {len(filtered)} record(s)")
    if filtered:
        frame = pd.DataFrame(
            [
                {
                    "Incident ID": f"SOS-{int(a['alert_id']):05d}",
                    "Citizen": a["citizen_name"],
                    "Phone": a["phone_number"],
                    "Emergency Type": a["emergency_type"],
                    "Status": a["status"],
                    "Latitude": round(float(a["latitude"]), 5),
                    "Longitude": round(float(a["longitude"]), 5),
                    "Assigned Unit": a.get("assigned_callsign") or "—",
                    "Reported (WAT)": format_timestamp(a["created_at"]),
                    "Closed (WAT)": format_timestamp(a["resolved_at"]),
                }
                for a in filtered
            ]
        )
        st.dataframe(
            frame, **FULL_WIDTH, hide_index=True, height=310,
            column_config={
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Emergency Type": st.column_config.TextColumn("Emergency Type", width="medium"),
            },
        )
        csv = frame.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Export register as CSV", data=csv,
            file_name="npf_enugu_sos_alerts.csv", mime="text/csv",
        )
    else:
        st.info("No alerts match the selected filters.")

    # ---------------- drill-down ------------------------------------------
    if filtered:
        section_title("🔍 Alert drill-down")
        options = {
            f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']} "
            f"[{a['status']}]": a["alert_id"]
            for a in filtered
        }
        picked = st.selectbox("Select an alert to inspect", list(options.keys()))
        alert = get_alert(options[picked])
        if alert:
            d1, d2 = st.columns([1.3, 1], gap="medium")
            with d1:
                st.markdown(
                    f"""
                    <div class="info-card">
                        <div class="callsign">SOS-{int(alert['alert_id']):05d}
                            {status_pill(alert['status'])}</div>
                        <div class="stats">
                            <b>Citizen:</b> {html_lib.escape(str(alert['citizen_name']))}<br>
                            <b>Telephone:</b> {html_lib.escape(str(alert['phone_number']))}<br>
                            <b>Emergency type:</b> {html_lib.escape(str(alert['emergency_type']))}<br>
                            <b>Coordinates:</b> {float(alert['latitude']):.6f}, {float(alert['longitude']):.6f}<br>
                            <b>Reported:</b> {html_lib.escape(format_timestamp(alert['created_at']))}<br>
                            <b>Closed:</b> {html_lib.escape(format_timestamp(alert['resolved_at']))}
                        </div>
                        <div style="margin-top:8px;padding-top:8px;border-top:1px solid #eceff1;color:#37474f">
                            {html_lib.escape(str(alert.get('description') or 'No description supplied.'))}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with d2:
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                st.button(
                    "📍 Show this incident on the live map", **FULL_WIDTH,
                    on_click=nav_callback, args=("🗺️ Live SOS Map",),
                    kwargs={"updates": {"focus_alert_id": alert["alert_id"]}},
                )
                st.button(
                    "🧭 Calculate nearest units", **FULL_WIDTH,
                    on_click=nav_callback, args=("🧭 Nearest Unit Calculator",),
                    kwargs={"updates": {"calc_alert_id": alert["alert_id"]}},
                )
                st.button(
                    "📄 Generate incident report", **FULL_WIDTH,
                    on_click=nav_callback, args=("📄 Incident Report",),
                    kwargs={"updates": {"report_alert_id": alert["alert_id"]}},
                )

    if not is_admin:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.info(
            "🔒 You are signed in as a **Viewer / Dispatcher**. "
            "Creating, updating, dispatching and deleting alerts is restricted to the "
            "Admin / Commander role."
        )
        return

    # ================= ADMIN OPERATIONS ==================================
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    section_title("🛠️ Alert Operations (Admin / Commander)")

    tab_new, tab_update, tab_dispatch, tab_delete, tab_sim = st.tabs(
        ["➕ Log new alert", "✏️ Update status", "📲 Dispatch unit", "🗑️ Delete alert", "🎲 Simulator"]
    )

    # ---------------- create ---------------------------------------------
    with tab_new:
        with st.form("new_alert_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                citizen = st.text_input("Citizen name *", placeholder="e.g. Mrs. Blessing Eze")
                phone = st.text_input("Phone number *", placeholder="e.g. 08034567890")
                emergency_type = st.selectbox("Emergency type *", EMERGENCY_TYPES)
            with c2:
                latitude = st.number_input("Latitude *", value=6.4483, format="%.6f",
                                           min_value=-90.0, max_value=90.0)
                longitude = st.number_input("Longitude *", value=7.5023, format="%.6f",
                                            min_value=-180.0, max_value=180.0)
                status = st.selectbox("Initial status", ALERT_STATUSES, index=0)

            description = st.text_area(
                "Description of the distress call",
                placeholder="Describe what the caller reported...", height=90,
            )
            submitted = st.form_submit_button("📥 Log SOS alert", type="primary")

        if submitted:
            errors = []
            if not citizen.strip():
                errors.append("Citizen name is required.")
            if not phone.strip():
                errors.append("Phone number is required.")
            elif not phone.strip().replace("+", "").replace("-", "").replace(" ", "").isdigit():
                errors.append("Phone number must contain digits only.")
            elif not (7 <= len(phone.strip()) <= 15):
                errors.append("Phone number should be between 7 and 15 digits.")
            if not haversine.is_within_command_area(latitude, longitude):
                st.warning(
                    "⚠️ The coordinates supplied fall outside the usual Enugu State Command "
                    "bounding box. Please confirm before saving."
                )

            if errors:
                for error in errors:
                    st.error(f"⛔ {error}")
            else:
                ok, message, alert_id = create_alert(
                    {
                        "citizen_name": citizen.strip(),
                        "phone_number": phone.strip(),
                        "latitude": float(latitude),
                        "longitude": float(longitude),
                        "emergency_type": emergency_type,
                        "description": description.strip(),
                        "status": status,
                    },
                    actor=auth.current_username(),
                )
                if ok:
                    st.session_state["focus_alert_id"] = alert_id
                    notify("success", message)
                    st.rerun()
                else:
                    st.error(f"⛔ {message}")

    # ---------------- update ---------------------------------------------
    with tab_update:
        if not alerts:
            st.info("There are no alerts in the register yet.")
        else:
            options = {
                f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']} "
                f"[{a['status']}]": a["alert_id"]
                for a in alerts
            }
            choice = st.selectbox("Select alert to update", list(options.keys()), key="upd_alert")
            target = get_alert(options[choice])

            if target:
                u1, u2 = st.columns(2)
                with u1:
                    new_status = st.selectbox(
                        "New status", ALERT_STATUSES,
                        index=ALERT_STATUSES.index(target["status"]), key="upd_status",
                    )
                with u2:
                    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                    st.caption(
                        "Marking an alert **Resolved** or **False Alarm** automatically "
                        "records the closure time and releases any patrol unit that was "
                        "attending the incident."
                    )

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("💾 Apply status change", type="primary", **FULL_WIDTH):
                        if new_status in ("Resolved", "False Alarm"):
                            ok, message = close_alert(target["alert_id"], new_status,
                                                      auth.current_username())
                        elif target["status"] in ("Resolved", "False Alarm") and new_status in (
                            "Active", "Dispatched"
                        ):
                            ok, message = reopen_alert(target["alert_id"], auth.current_username())
                        else:
                            try:
                                db.execute_query(
                                    "UPDATE sos_alerts SET status = ? WHERE alert_id = ?",
                                    (new_status, target["alert_id"]),
                                )
                                db.log_activity(
                                    "ALERT_UPDATED",
                                    f"SOS-{target['alert_id']:05d} status changed from "
                                    f"{target['status']} to {new_status}",
                                    actor=auth.current_username(), alert_id=target["alert_id"],
                                )
                                ok, message = True, f"SOS-{target['alert_id']:05d} updated to {new_status}."
                            except db.DatabaseError as exc:
                                ok, message = False, str(exc)
                        notify("success" if ok else "error", message)
                        st.rerun()
                with c2:
                    if st.button("✅ Mark resolved", **FULL_WIDTH):
                        ok, message = close_alert(target["alert_id"], "Resolved",
                                                  auth.current_username())
                        notify("success" if ok else "error", message)
                        st.rerun()
                with c3:
                    if st.button("⚠️ Mark false alarm", **FULL_WIDTH):
                        ok, message = close_alert(target["alert_id"], "False Alarm",
                                                  auth.current_username())
                        notify("success" if ok else "error", message)
                        st.rerun()

                with st.expander("✏️ Edit incident particulars"):
                    with st.form("edit_alert_form"):
                        e1, e2 = st.columns(2)
                        with e1:
                            e_citizen = st.text_input("Citizen name", value=target["citizen_name"])
                            e_phone = st.text_input("Phone number", value=target["phone_number"])
                            e_type = st.selectbox(
                                "Emergency type", EMERGENCY_TYPES,
                                index=EMERGENCY_TYPES.index(target["emergency_type"]),
                            )
                        with e2:
                            e_lat = st.number_input("Latitude", value=float(target["latitude"]),
                                                    format="%.6f")
                            e_lon = st.number_input("Longitude", value=float(target["longitude"]),
                                                    format="%.6f")
                        e_desc = st.text_area("Description",
                                              value=str(target.get("description") or ""))
                        if st.form_submit_button("💾 Save changes", type="primary"):
                            try:
                                db.execute_query(
                                    """
                                    UPDATE sos_alerts
                                    SET citizen_name = ?, phone_number = ?, emergency_type = ?,
                                        latitude = ?, longitude = ?, description = ?
                                    WHERE alert_id = ?
                                    """,
                                    (e_citizen.strip(), e_phone.strip(), e_type,
                                     float(e_lat), float(e_lon), e_desc.strip(),
                                     target["alert_id"]),
                                )
                                db.log_activity(
                                    "ALERT_EDITED",
                                    f"SOS-{target['alert_id']:05d} particulars updated",
                                    actor=auth.current_username(), alert_id=target["alert_id"],
                                )
                                notify("success", f"SOS-{target['alert_id']:05d} updated successfully.")
                                st.rerun()
                            except db.DatabaseError as exc:
                                st.error(f"⛔ {exc}")

    # ---------------- dispatch -------------------------------------------
    with tab_dispatch:
        open_alerts = [a for a in alerts if a["status"] in ("Active", "Dispatched")]
        if not open_alerts:
            st.info("There are no open alerts requiring dispatch.")
        else:
            options = {
                f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']} "
                f"[{a['status']}]": a["alert_id"]
                for a in open_alerts
            }
            choice = st.selectbox("Select the alert requiring a patrol unit",
                                  list(options.keys()), key="dispatch_alert")
            alert = get_alert(options[choice])

            if alert:
                available = [u for u in units if u["status"] == "Available"]
                ranked = haversine.find_nearest_units(
                    alert["latitude"], alert["longitude"], units,
                    top_n=len(units) or 1, available_only=False,
                )

                if not ranked:
                    st.warning("No patrol units are registered in the system.")
                else:
                    st.markdown(
                        f"**Incident location:** {float(alert['latitude']):.5f}, "
                        f"{float(alert['longitude']):.5f} — "
                        f"{len(available)} unit(s) currently available."
                    )
                    st.markdown("<div class='section-title'>Ranked by distance (Haversine)</div>",
                                unsafe_allow_html=True)

                    rank_cols = st.columns(min(3, len(ranked)))
                    for index, match in enumerate(ranked[:3]):
                        with rank_cols[index]:
                            badge_class = f"rank{index + 1}"
                            st.markdown(
                                f"""
                                <div class="info-card {badge_class}">
                                    <div class="callsign">{'🥇' if index == 0 else ('🥈' if index == 1 else '🥉')}
                                        {html_lib.escape(str(match['unit_callsign']))}</div>
                                    <div class="officer">{html_lib.escape(str(match['officer_name']))}</div>
                                    <div class="stats">
                                        📏 <b>{match['distance_km']:.2f} km</b> away<br>
                                        ⏱️ ETA <b>{html_lib.escape(match['eta_text'])}</b><br>
                                        {unit_status_pill(match['status'])}
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    selectable = {
                        f"{m['unit_callsign']} — {m['distance_km']:.2f} km, ETA {m['eta_text']} "
                        f"({m['status']})": m["unit_id"]
                        for m in ranked
                    }
                    pick = st.selectbox("Assign a specific unit", list(selectable.keys()))
                    if st.button("📲 Dispatch selected unit", type="primary", **FULL_WIDTH):
                        ok, message = dispatch_unit(alert["alert_id"], selectable[pick],
                                                    auth.current_username())
                        notify("success" if ok else "error", message)
                        st.rerun()

    # ---------------- delete ---------------------------------------------
    with tab_delete:
        if not alerts:
            st.info("There are no alerts to delete.")
        else:
            options = {
                f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']} "
                f"[{a['status']}]": a["alert_id"]
                for a in alerts
            }
            choice = st.selectbox("Select the alert to delete", list(options.keys()), key="del_alert")
            target = get_alert(options[choice])

            if target:
                st.error(
                    f"⚠️ You are about to permanently delete **SOS-{target['alert_id']:05d}** "
                    f"({target['emergency_type']} reported by {target['citizen_name']}). "
                    "This action cannot be undone."
                )
                confirm = st.checkbox(
                    f"I confirm that SOS-{target['alert_id']:05d} should be deleted permanently"
                )
                if st.button("🗑️ Delete alert", type="primary", disabled=not confirm):
                    ok, message = delete_alert(target["alert_id"], auth.current_username())
                    notify("success" if ok else "error", message)
                    st.rerun()

    # ---------------- simulator -------------------------------------------
    with tab_sim:
        st.markdown(
            "For the purpose of this demonstration there is no mobile SOS application "
            "connected to the Command. Use the simulator below to inject a realistic "
            "incoming distress call and watch the live map react within "
            f"{MAP_REFRESH_SECONDS} seconds."
        )
        s1, s2 = st.columns([1, 2])
        with s1:
            if st.button("🎲 Generate one incoming SOS", type="primary", **FULL_WIDTH):
                ok, message, alert_id = simulate_incoming_alert(auth.current_username())
                if ok:
                    st.session_state["focus_alert_id"] = alert_id
                    notify("error", f"🚨 {message}")
                else:
                    notify("error", message)
                st.rerun()
        with s2:
            if st.button("🎬 Simulate a burst of 3 incoming calls", **FULL_WIDTH):
                created = 0
                last_id = None
                for _ in range(3):
                    ok, _message, alert_id = simulate_incoming_alert(auth.current_username())
                    if ok:
                        created += 1
                        last_id = alert_id
                if last_id:
                    st.session_state["focus_alert_id"] = last_id
                notify("error", f"🚨 {created} new SOS alert(s) received from the field.")
                st.rerun()

        st.caption(
            "Simulated calls use real Enugu landmarks (Ogui Road, Abakpa Nike, Ogbete Market, "
            "Nsukka, Emene, Uwani, New Haven and others) so that the nearest-unit calculation "
            "produces sensible distances."
        )


# =================================================================================
# 10. PAGE: PATROL UNIT MANAGEMENT
# =================================================================================
def page_patrol_units() -> None:
    command_header(
        "Patrol Unit Management",
        f"{COMMAND_NAME} · Fleet register, positions and availability",
        badge="ADMIN" if auth.is_admin() else "READ-ONLY",
    )

    is_admin = auth.is_admin()
    units = load_units()
    alerts = load_alerts()
    stations = load_stations()

    total = len(units)
    available = len([u for u in units if u["status"] == "Available"])
    dispatched = len([u for u in units if u["status"] == "Dispatched"])
    offline = len([u for u in units if u["status"] == "Offline"])

    c1, c2, c3, c4 = st.columns(4, gap="medium")
    c1.metric("🚔 Units on strength", total)
    c2.metric("🟢 Available", available)
    c3.metric("🟠 Dispatched", dispatched)
    c4.metric("⚫ Offline", offline)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.35, 1], gap="medium")

    with left:
        section_title(f"📋 Fleet Register — {total} unit(s)")
        if units:
            frame = pd.DataFrame(
                [
                    {
                        "Callsign": u["unit_callsign"],
                        "Officer": u["officer_name"],
                        "Status": u["status"],
                        "Latitude": round(float(u["current_lat"]), 5),
                        "Longitude": round(float(u["current_long"]), 5),
                        "Last Updated (WAT)": format_timestamp(u["last_updated"]),
                    }
                    for u in units
                ]
            )
            st.dataframe(frame, **FULL_WIDTH, hide_index=True, height=300)
        else:
            st.info("No patrol units have been registered.")

    with right:
        section_title("🗺️ Unit Positions")
        fmap = build_folium_map(alerts, units, stations, map_key="units_map")
        st_folium(fmap, height=300, use_container_width=True,
                  returned_objects=[], key="units_map_render")

    if not is_admin:
        st.info(
            "🔒 Viewer / Dispatcher accounts have read-only access. "
            "Adding, editing and deleting patrol units requires the Admin / Commander role."
        )
        return

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    section_title("🛠️ Fleet Operations (Admin / Commander)")

    tab_add, tab_edit, tab_delete = st.tabs(
        ["➕ Add patrol unit", "✏️ Update unit", "🗑️ Delete unit"]
    )

    # ---------------- add -------------------------------------------------
    with tab_add:
        with st.form("add_unit_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                callsign = st.text_input("Unit callsign *", placeholder="e.g. PATROL-06-EMENE")
                officer = st.text_input("Officer name *", placeholder="e.g. Sgt. Daniel Ibe")
            with c2:
                lat = st.number_input("Current latitude *", value=6.4483, format="%.6f")
                lon = st.number_input("Current longitude *", value=7.5023, format="%.6f")
                status = st.selectbox("Status", UNIT_STATUSES, index=0)
            submitted = st.form_submit_button("🚔 Register patrol unit", type="primary")

        if submitted:
            errors = []
            if not callsign.strip():
                errors.append("Unit callsign is required.")
            elif len(callsign.strip()) < 5:
                errors.append("Callsign looks too short — use a format such as PATROL-06-EMENE.")
            if not officer.strip():
                errors.append("Officer name is required.")
            if not haversine.is_within_command_area(lat, lon):
                st.warning("⚠️ These coordinates are outside the usual Enugu State Command area.")

            if errors:
                for error in errors:
                    st.error(f"⛔ {error}")
            else:
                try:
                    db.execute_query(
                        """
                        INSERT INTO patrol_units
                            (unit_callsign, officer_name, current_lat, current_long,
                             status, last_updated)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (callsign.strip().upper(), officer.strip(), float(lat), float(lon), status),
                    )
                    db.log_activity("UNIT_ADDED",
                                    f"Patrol unit {callsign.strip().upper()} registered under "
                                    f"{officer.strip()}",
                                    actor=auth.current_username())
                    notify("success", f"Patrol unit {callsign.strip().upper()} registered.")
                    st.rerun()
                except db.DatabaseError as exc:
                    st.error(f"⛔ {exc}")

    # ---------------- edit -------------------------------------------------
    with tab_edit:
        if not units:
            st.info("No patrol units to update.")
        else:
            options = {
                f"{u['unit_callsign']} — {u['officer_name']} [{u['status']}]": u["unit_id"]
                for u in units
            }
            choice = st.selectbox("Select a patrol unit", list(options.keys()), key="edit_unit")
            unit = safe_fetch_one("SELECT * FROM patrol_units WHERE unit_id = ?",
                                  (options[choice],), "the patrol unit")

            if unit:
                with st.form("edit_unit_form"):
                    c1, c2 = st.columns(2)
                    with c1:
                        e_callsign = st.text_input("Unit callsign", value=unit["unit_callsign"])
                        e_officer = st.text_input("Officer name", value=unit["officer_name"])
                    with c2:
                        e_lat = st.number_input("Current latitude",
                                                value=float(unit["current_lat"]), format="%.6f")
                        e_lon = st.number_input("Current longitude",
                                                value=float(unit["current_long"]), format="%.6f")
                        e_status = st.selectbox("Status", UNIT_STATUSES,
                                                index=UNIT_STATUSES.index(unit["status"]))
                    if st.form_submit_button("💾 Save unit changes", type="primary"):
                        try:
                            db.execute_query(
                                """
                                UPDATE patrol_units
                                SET unit_callsign = ?, officer_name = ?, current_lat = ?,
                                    current_long = ?, status = ?, last_updated = CURRENT_TIMESTAMP
                                WHERE unit_id = ?
                                """,
                                (e_callsign.strip().upper(), e_officer.strip(), float(e_lat),
                                 float(e_lon), e_status, unit["unit_id"]),
                            )
                            db.log_activity(
                                "UNIT_UPDATED",
                                f"{e_callsign.strip().upper()} updated (status: {e_status}, "
                                f"position {e_lat:.5f}, {e_lon:.5f})",
                                actor=auth.current_username(),
                            )
                            notify("success", f"{e_callsign.strip().upper()} updated successfully.")
                            st.rerun()
                        except db.DatabaseError as exc:
                            st.error(f"⛔ {exc}")

                if unit["status"] == "Dispatched":
                    st.caption(
                        "ℹ️ This unit is currently attached to an incident. "
                        "Update the incident status on the SOS Alert Management page to "
                        "release it automatically."
                    )

    # ---------------- delete ----------------------------------------------
    with tab_delete:
        if not units:
            st.info("No patrol units to delete.")
        else:
            options = {
                f"{u['unit_callsign']} — {u['officer_name']} [{u['status']}]": u["unit_id"]
                for u in units
            }
            choice = st.selectbox("Select the patrol unit to delete",
                                  list(options.keys()), key="del_unit")
            unit_id = options[choice]
            unit = safe_fetch_one("SELECT * FROM patrol_units WHERE unit_id = ?", (unit_id,))

            if unit:
                st.error(
                    f"⚠️ Deleting **{unit['unit_callsign']}** will remove it from the fleet "
                    "register. Any incident it was attending will be released automatically "
                    "(ON DELETE SET NULL on the sos_alerts.assigned_unit_id foreign key)."
                )
                confirm = st.checkbox(
                    f"I confirm that {unit['unit_callsign']} should be removed from the fleet"
                )
                if st.button("🗑️ Delete patrol unit", type="primary", disabled=not confirm):
                    try:
                        db.execute_query("DELETE FROM patrol_units WHERE unit_id = ?", (unit_id,))
                        db.log_activity("UNIT_DELETED",
                                        f"Patrol unit {unit['unit_callsign']} removed from the fleet",
                                        actor=auth.current_username())
                        notify("success", f"{unit['unit_callsign']} deleted from the fleet register.")
                        st.rerun()
                    except db.DatabaseError as exc:
                        st.error(f"⛔ {exc}")


# =================================================================================
# 11. PAGE: POLICE STATIONS
# =================================================================================
def page_stations() -> None:
    command_header(
        "Police Stations & Divisions",
        f"{COMMAND_NAME} · Divisional headquarters and areas of responsibility",
        badge="DATABASE",
    )

    stations = load_stations()
    alerts = load_alerts()
    units = load_units()

    c1, c2, c3 = st.columns(3, gap="medium")
    c1.metric("🏛️ Divisions registered", len(stations))
    c2.metric("🚔 Patrol units assigned", len(units))
    c3.metric("📞 Incidents in register", len(alerts))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    left, right = st.columns([1.15, 1], gap="medium")

    with left:
        section_title("🏛️ Divisional Register")
        if stations:
            frame = pd.DataFrame(
                [
                    {
                        "Station": s["station_name"],
                        "Latitude": round(float(s["latitude"]), 5),
                        "Longitude": round(float(s["longitude"]), 5),
                        "Address": s.get("address") or "—",
                    }
                    for s in stations
                ]
            )
            st.dataframe(frame, **FULL_WIDTH, hide_index=True, height=280)
        else:
            st.info("No police stations recorded.")

        section_title("📏 Distance from a selected incident to each division")
        if alerts and stations:
            options = {
                f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']}": a
                for a in alerts
            }
            pick = st.selectbox("Select an incident", list(options.keys()), key="station_dist")
            alert = options[pick]
            ranked = haversine.nearest_station(
                alert["latitude"], alert["longitude"], stations, top_n=len(stations)
            )
            dist_frame = pd.DataFrame(
                [
                    {
                        "Division": item["station_name"],
                        "Distance (km)": round(item["distance_km"], 2),
                        "ETA at 40 km/h": item["eta_text"],
                        "Address": item["address"],
                    }
                    for item in ranked
                ]
            )
            st.dataframe(dist_frame, **FULL_WIDTH, hide_index=True, height=230)

    with right:
        section_title("🗺️ Divisional Coverage Map")
        fmap = build_folium_map(alerts, units, stations,
                                highlight_alert_id=st.session_state.get("focus_alert_id"),
                                map_key="stations_map")
        st_folium(fmap, height=330, use_container_width=True,
                  returned_objects=[], key="stations_map_render")
        st.caption(
            "Blue markers show the six divisions of the Enugu State Command with their real "
            "GPS coordinates. Zoom in and click a marker to see the address and coordinates."
        )

    if auth.is_admin():
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        with st.expander("➕ Register a new division"):
            with st.form("add_station_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Station name *", placeholder="e.g. Uwani Division")
                    address = st.text_input("Address", placeholder="e.g. Uwani, Enugu South LGA")
                with c2:
                    lat = st.number_input("Latitude *", value=6.4312, format="%.6f")
                    lon = st.number_input("Longitude *", value=7.5002, format="%.6f")
                if st.form_submit_button("🏛️ Register division", type="primary"):
                    if not name.strip():
                        st.error("⛔ Station name is required.")
                    else:
                        try:
                            db.execute_query(
                                """
                                INSERT INTO police_stations
                                    (station_name, latitude, longitude, address)
                                VALUES (?, ?, ?, ?)
                                """,
                                (name.strip(), float(lat), float(lon), address.strip()),
                            )
                            db.log_activity("STATION_ADDED",
                                            f"Division '{name.strip()}' registered",
                                            actor=auth.current_username())
                            notify("success", f"Division '{name.strip()}' registered.")
                            st.rerun()
                        except db.DatabaseError as exc:
                            st.error(f"⛔ {exc}")
    else:
        st.info("🔒 Registering new divisions requires the Admin / Commander role.")


# =================================================================================
# 12. PAGE: NEAREST UNIT CALCULATOR  (the "wow" feature)
# =================================================================================
def page_nearest_units() -> None:
    command_header(
        "Nearest Unit Calculator",
        f"{COMMAND_NAME} · Haversine great-circle dispatch recommendation",
        badge="DECISION SUPPORT",
    )

    alerts = load_alerts()
    units = load_units()
    stations = load_stations()

    if not alerts:
        st.warning("There are no SOS alerts in the register. Log an alert first.")
        return
    if not units:
        st.warning("There are no patrol units registered. Add a unit first.")
        return

    # ---------------- selection panel -------------------------------------
    section_title("🎯 Select the incident and dispatch parameters")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])

    alert_options = {
        f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']} "
        f"[{a['status']}]": a["alert_id"]
        for a in alerts
    }
    default_key = None
    preset = st.session_state.get("calc_alert_id")
    if preset:
        default_key = next(
            (k for k, v in alert_options.items() if v == preset), None
        )

    with c1:
        picked = st.selectbox(
            "SOS alert", list(alert_options.keys()),
            index=list(alert_options.keys()).index(default_key) if default_key else 0,
        )
    with c2:
        top_n = st.slider("Units to rank", 1, min(5, len(units)), min(3, len(units)))
    with c3:
        speed = st.number_input("Average speed (km/h)", min_value=10, max_value=120,
                                value=int(DEFAULT_SPEED_KMH), step=5)
    with c4:
        available_only = st.checkbox("Available units only", value=True,
                                     help="Uncheck to also consider dispatched and offline units.")

    alert_id = alert_options[picked]
    alert = get_alert(alert_id)
    if not alert:
        st.error("The selected alert could not be loaded.")
        return

    st.session_state["focus_alert_id"] = alert_id

    # ---------------- run the Haversine calculation -----------------------
    ranked = haversine.find_nearest_units(
        alert["latitude"], alert["longitude"], units,
        top_n=top_n, available_only=available_only, speed_kmh=float(speed),
    )
    all_ranked = haversine.find_nearest_units(
        alert["latitude"], alert["longitude"], units,
        top_n=len(units), available_only=False, speed_kmh=float(speed),
    )

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="info-card">
            <div class="callsign">{TYPE_ICON.get(alert['emergency_type'],'📞')}
                SOS-{int(alert['alert_id']):05d} — {html_lib.escape(str(alert['emergency_type']))}
                {status_pill(alert['status'])}</div>
            <div class="stats">
                <b>Citizen:</b> {html_lib.escape(str(alert['citizen_name']))} ·
                <b>Phone:</b> {html_lib.escape(str(alert['phone_number']))}<br>
                <b>Incident location:</b> {float(alert['latitude']):.6f}, {float(alert['longitude']):.6f}<br>
                <b>Reported:</b> {html_lib.escape(format_timestamp(alert['created_at']))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not ranked:
        st.warning(
            "No patrol unit matches the current filter. "
            "Untick **Available units only** to see units that are dispatched or offline."
        )
    else:
        section_title(f"🏆 Top {len(ranked)} nearest patrol unit(s) — ranked by Haversine distance")

        columns = st.columns(len(ranked))
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for index, match in enumerate(ranked):
            with columns[index]:
                eta_plan = match["eta_minutes"]
                st.markdown(
                    f"""
                    <div class="info-card rank{min(index + 1, 3)}">
                        <div class="callsign">{medals[index]} {html_lib.escape(str(match['unit_callsign']))}</div>
                        <div class="officer">👮 {html_lib.escape(str(match['officer_name']))}</div>
                        <div class="stats">
                            📏 <b>{match['distance_km']:.2f} km</b> from the incident<br>
                            ⏱️ ETA <b>{html_lib.escape(match['eta_text'])}</b>
                            <span class="small-note">({eta_plan:.1f} min at {int(speed)} km/h + 15% traffic delay)</span><br>
                            📍 {match['lat']:.5f}, {match['lon']:.5f}<br>
                            {unit_status_pill(match['status'])}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ---- full ranking table -----------------------------------------
        with st.expander("📊 Full ranking of every patrol unit (distance & ETA)"):
            frame = pd.DataFrame(
                [
                    {
                        "Rank": index + 1,
                        "Callsign": m["unit_callsign"],
                        "Officer": m["officer_name"],
                        "Status": m["status"],
                        "Distance (km)": round(m["distance_km"], 3),
                        "ETA (minutes)": round(m["eta_minutes"], 1),
                        "ETA": m["eta_text"],
                    }
                    for index, m in enumerate(all_ranked)
                ]
            )
            st.dataframe(frame, **FULL_WIDTH, hide_index=True)
            st.caption(
                "Distance is computed with the Haversine formula: "
                "a = sin²(Δφ/2) + cos φ₁·cos φ₂·sin²(Δλ/2),  c = 2·atan2(√a, √(1−a)),  "
                "d = 6371.0088 · c kilometres."
            )

        # ---- dispatch action ---------------------------------------------
        if auth.is_admin():
            section_title("📲 Dispatch")
            d1, d2 = st.columns([2, 1])
            with d1:
                dispatch_options = {
                    f"{m['unit_callsign']} — {m['distance_km']:.2f} km, ETA {m['eta_text']}"
                    f" ({m['status']})": m["unit_id"]
                    for m in all_ranked
                }
                chosen = st.selectbox("Select the unit to dispatch", list(dispatch_options.keys()))
            with d2:
                st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
                if st.button("📲 Dispatch now", type="primary", **FULL_WIDTH):
                    ok, message = dispatch_unit(alert["alert_id"], dispatch_options[chosen],
                                                auth.current_username())
                    notify("success" if ok else "error", message)
                    st.rerun()
        else:
            st.info("🔒 Dispatch actions are restricted to the Admin / Commander role.")

    # ---------------- map with route lines --------------------------------
    section_title("🗺️ Distance visualisation")
    fmap = build_folium_map(
        alerts=alerts, units=units, stations=stations,
        highlight_alert_id=alert_id,
        nearest_matches=ranked if ranked else None,
        map_key="nearest_map",
    )
    st_folium(fmap, height=520, use_container_width=True,
              returned_objects=[], key="nearest_map_render")

    # ---------------- nearest division ------------------------------------
    nearest_div = haversine.nearest_station(alert["latitude"], alert["longitude"], stations, top_n=1)
    if nearest_div:
        item = nearest_div[0]
        st.markdown(
            f"""
            <div class="info-card">
                <div class="callsign">🏛️ Division with jurisdiction</div>
                <div class="stats">
                    <b>{html_lib.escape(str(item['station_name']))}</b> —
                    {item['distance_km']:.2f} km from the incident ·
                    ETA {html_lib.escape(item['eta_text'])}<br>
                    <span class="small-note">{html_lib.escape(str(item['address']))}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =================================================================================
# 13. PAGE: INCIDENT REPORT GENERATOR
# =================================================================================
def page_incident_report() -> None:
    command_header(
        "Emergency Incident Report",
        f"{COMMAND_NAME} · Printable incident record for the Command diary",
        badge="PRINTABLE",
    )

    alerts = load_alerts()
    if not alerts:
        st.warning("There are no alerts in the register. Log an SOS alert first, then generate a report.")
        return

    alert_options = {
        f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']} "
        f"[{a['status']}] · {format_timestamp(a['created_at'])}": a["alert_id"]
        for a in alerts
    }
    preset = st.session_state.get("report_alert_id")
    default_index = 0
    if preset:
        for index, (key, value) in enumerate(alert_options.items()):
            if value == preset:
                default_index = index
                break

    c1, c2 = st.columns([3, 1])
    with c1:
        picked = st.selectbox("Select the incident to report on",
                              list(alert_options.keys()), index=default_index)
    with c2:
        st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
        include_preview = st.checkbox("Show printable preview", value=True)

    alert_id = alert_options[picked]

    # ---------------- build the report ------------------------------------
    try:
        report_data = reports.generate_incident_report(alert_id)
    except ValueError as exc:
        st.error(f"⛔ {exc}")
        return
    except db.DatabaseError as exc:
        st.error(f"⛔ Database error while building the report: {exc}")
        return
    except Exception as exc:  # noqa: BLE001 - defensive
        st.error(f"⛔ Unexpected error while building the report: {exc}")
        return

    response = report_data["response"]

    # ---------------- headline metrics ------------------------------------
    m1, m2, m3, m4 = st.columns(4, gap="medium")
    m1.metric("🆔 Incident ID", f"SOS-{int(report_data['alert_id']):05d}")
    m2.metric("📏 Distance to unit", f"{response['distance_km']:.2f} km")
    m3.metric("⏱️ Estimated arrival", response["eta_text"])
    m4.metric(
        "✅ Response time",
        report_data["response_minutes_text"].replace(" minutes", " min")
        if report_data["response_minutes"] is not None else "Pending",
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ---------------- download buttons ------------------------------------
    section_title("⬇️ Download the report")
    d1, d2, d3 = st.columns([1, 1, 1])
    with d1:
        try:
            pdf_bytes, filename = reports.generate_incident_pdf(alert_id)
            st.download_button(
                "📄 Download as PDF", data=pdf_bytes, file_name=filename,
                mime="application/pdf", type="primary", **FULL_WIDTH,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"PDF generation failed: {exc}")
    with d2:
        html_report = reports.format_report_as_html(report_data)
        st.download_button(
            "🌐 Download as HTML", data=html_report.encode("utf-8"),
            file_name=f"NPF_Enugu_Incident_Report_SOS-{int(alert_id):05d}.html",
            mime="text/html", **FULL_WIDTH,
        )
    with d3:
        st.download_button(
            "📝 Download as text", data=reports.format_report_as_text(report_data).encode("utf-8"),
            file_name=f"NPF_Enugu_Incident_Report_SOS-{int(alert_id):05d}.txt",
            mime="text/plain", **FULL_WIDTH,
        )

    st.caption(
        "The PDF is generated internally with a built-in PDF writer — no external service or "
        "paid library is required. The HTML version can be opened in any browser and printed "
        "to paper with Ctrl + P."
    )

    # ---------------- printable preview -----------------------------------
    if include_preview:
        section_title("🖨️ Printable report preview")
        components.html(html_report, height=880, scrolling=True)

    # ---------------- plain-text version ----------------------------------
    with st.expander("📃 Plain-text version (for the incident register book)"):
        st.code(reports.format_report_as_text(report_data), language="text")


# =================================================================================
# 14. PAGE: SEARCH & RETRIEVE
# =================================================================================
def page_search() -> None:
    command_header(
        "Search & Retrieve",
        f"{COMMAND_NAME} · Search incidents, citizens, callsigns and divisions",
        badge="SEARCH",
    )

    query = st.text_input(
        "🔍 Enter your search term",
        placeholder="e.g. Nwankwo · SOS-00001 · Kidnapping · PATROL-01-OGUI · 08034567890",
        help="Searches citizen names, phone numbers, incident IDs, emergency types, "
             "descriptions, patrol unit callsigns, officer names and division names.",
    )

    if not query or len(query.strip()) < 2:
        st.info(
            "Type at least two characters to search. You may search by **citizen name**, "
            "**incident ID** (SOS-00001), **phone number**, **emergency type**, "
            "**patrol unit callsign** or **division name**."
        )

        # Show something useful while waiting for input.
        alerts = load_alerts()
        if alerts:
            section_title("🕒 Most recent incidents")
            for alert in alerts[:5]:
                st.markdown(
                    f"""
                    <div class="feed-item">
                        {TYPE_ICON.get(alert['emergency_type'],'📞')}
                        <b>SOS-{int(alert['alert_id']):05d}</b> ·
                        {html_lib.escape(str(alert['emergency_type']))} ·
                        {html_lib.escape(str(alert['citizen_name']))}
                        {status_pill(alert['status'])}
                        <div class="meta">{html_lib.escape(format_timestamp(alert['created_at']))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        return

    needle = query.strip()
    like = f"%{needle}%"

    # ---------------- alerts ----------------------------------------------
    alert_matches = safe_fetch_all(
        """
        SELECT a.*, u.unit_callsign AS assigned_callsign
        FROM sos_alerts a
        LEFT JOIN patrol_units u ON u.unit_id = a.assigned_unit_id
        WHERE a.citizen_name   LIKE ?
           OR a.phone_number   LIKE ?
           OR a.emergency_type LIKE ?
           OR a.description    LIKE ?
           OR ('SOS-' || printf('%05d', a.alert_id)) LIKE ?
           OR CAST(a.alert_id AS TEXT) LIKE ?
        ORDER BY a.alert_id DESC
        """,
        (like, like, like, like, like, like),
        "matching alerts",
    )

    unit_matches = safe_fetch_all(
        """
        SELECT * FROM patrol_units
        WHERE unit_callsign LIKE ? OR officer_name LIKE ?
        ORDER BY unit_callsign
        """,
        (like, like),
        "matching patrol units",
    )

    station_matches = safe_fetch_all(
        """
        SELECT * FROM police_stations
        WHERE station_name LIKE ? OR address LIKE ?
        ORDER BY station_name
        """,
        (like, like),
        "matching divisions",
    )

    total = len(alert_matches) + len(unit_matches) + len(station_matches)

    if total == 0:
        st.warning(
            f"No records found for **{html_lib.escape(needle)}**. "
            "Try a shorter term, or check the spelling."
        )
        return

    st.success(
        f"Found **{total}** matching record(s): {len(alert_matches)} incident(s), "
        f"{len(unit_matches)} patrol unit(s), {len(station_matches)} division(s)."
    )

    # ---------------- incident results ------------------------------------
    if alert_matches:
        section_title(f"🚨 Incidents ({len(alert_matches)})")
        units_all = load_units()
        for alert in alert_matches:
            nearest = haversine.find_nearest_units(
                alert["latitude"], alert["longitude"], units_all, top_n=1, available_only=True
            )
            nearest_text = (
                f"{nearest[0]['unit_callsign']} · {nearest[0]['distance_km']:.2f} km · "
                f"ETA {nearest[0]['eta_text']}" if nearest else "no available unit"
            )
            st.markdown(
                f"""
                <div class="info-card">
                    <div class="callsign">{TYPE_ICON.get(alert['emergency_type'],'📞')}
                        SOS-{int(alert['alert_id']):05d} {status_pill(alert['status'])}</div>
                    <div class="stats">
                        <b>{html_lib.escape(str(alert['emergency_type']))}</b> ·
                        {html_lib.escape(str(alert['citizen_name']))} ·
                        {html_lib.escape(str(alert['phone_number']))}<br>
                        📍 {float(alert['latitude']):.5f}, {float(alert['longitude']):.5f} ·
                        🕒 {html_lib.escape(format_timestamp(alert['created_at']))}<br>
                        🚔 Nearest available: <b>{html_lib.escape(nearest_text)}</b><br>
                        <span class="small-note">
                        {html_lib.escape(str(alert.get('description') or 'No description.')[:170])}
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        section_title("🔎 Inspect a matching incident")
        options = {
            f"SOS-{int(a['alert_id']):05d} · {a['emergency_type']} · {a['citizen_name']}": a["alert_id"]
            for a in alert_matches
        }
        picked = st.selectbox("Select an incident to view in full", list(options.keys()),
                              key="search_alert_pick")
        selected_id = options[picked]
        selected = get_alert(selected_id)

        if selected:
            col_left, col_right = st.columns([1, 1.6], gap="medium")
            with col_left:
                st.markdown("##### Full incident particulars")
                st.markdown(
                    f"""
                    <div class="info-card">
                        <div class="stats">
                            <b>Incident ID:</b> SOS-{int(selected['alert_id']):05d}<br>
                            <b>Citizen:</b> {html_lib.escape(str(selected['citizen_name']))}<br>
                            <b>Telephone:</b> {html_lib.escape(str(selected['phone_number']))}<br>
                            <b>Emergency type:</b> {html_lib.escape(str(selected['emergency_type']))}<br>
                            <b>Status:</b> {html_lib.escape(str(selected['status']))}<br>
                            <b>Coordinates:</b> {float(selected['latitude']):.6f}, {float(selected['longitude']):.6f}<br>
                            <b>Reported:</b> {html_lib.escape(format_timestamp(selected['created_at']))}<br>
                            <b>Resolved:</b> {html_lib.escape(format_timestamp(selected['resolved_at']))}
                        </div>
                        <div style="margin-top:8px;padding-top:8px;border-top:1px solid #eceff1">
                            {html_lib.escape(str(selected.get('description') or 'No description supplied.'))}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                b1, b2 = st.columns(2)
                with b1:
                    st.button(
                        "🧭 Nearest units", **FULL_WIDTH,
                        on_click=nav_callback, args=("🧭 Nearest Unit Calculator",),
                        kwargs={"updates": {"calc_alert_id": selected_id}},
                    )
                with b2:
                    st.button(
                        "📄 Incident report", **FULL_WIDTH,
                        on_click=nav_callback, args=("📄 Incident Report",),
                        kwargs={"updates": {"report_alert_id": selected_id}},
                    )

            with col_right:
                st.markdown("##### Location on the map")
                fmap = build_folium_map(
                    alerts=alert_matches, units=units_all,
                    stations=load_stations(), highlight_alert_id=selected_id,
                    map_key="search_map",
                )
                st_folium(fmap, height=420, use_container_width=True,
                          returned_objects=[], key="search_map_render")

    # ---------------- patrol unit results ---------------------------------
    if unit_matches:
        section_title(f"🚔 Patrol units ({len(unit_matches)})")
        frame = pd.DataFrame(
            [
                {
                    "Callsign": u["unit_callsign"],
                    "Officer": u["officer_name"],
                    "Status": u["status"],
                    "Latitude": round(float(u["current_lat"]), 5),
                    "Longitude": round(float(u["current_long"]), 5),
                    "Last Updated": format_timestamp(u["last_updated"]),
                }
                for u in unit_matches
            ]
        )
        st.dataframe(frame, **FULL_WIDTH, hide_index=True)

    # ---------------- station results -------------------------------------
    if station_matches:
        section_title(f"🏛️ Police stations ({len(station_matches)})")
        frame = pd.DataFrame(
            [
                {
                    "Station": s["station_name"],
                    "Address": s.get("address") or "—",
                    "Latitude": round(float(s["latitude"]), 5),
                    "Longitude": round(float(s["longitude"]), 5),
                }
                for s in station_matches
            ]
        )
        st.dataframe(frame, **FULL_WIDTH, hide_index=True)


# =================================================================================
# 15. PAGE: USER MANAGEMENT (Admin only)
# =================================================================================
def page_users() -> None:
    command_header(
        "User & Access Management",
        f"{COMMAND_NAME} · Control room accounts and role assignment",
        badge="ADMIN ONLY",
    )

    users = auth.list_users()

    c1, c2, c3 = st.columns(3, gap="medium")
    c1.metric("👤 Accounts", len(users))
    c2.metric("🛡️ Admins / Commanders", len([u for u in users if u["role"] == "Admin"]))
    c3.metric("👁️ Viewers / Dispatchers", len([u for u in users if u["role"] == "Viewer"]))

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    section_title("🔐 Role permissions matrix")
    st.dataframe(
        pd.DataFrame(
            [
                {"Capability": "View dashboard, maps and registers",
                 "Admin / Commander": "✅ Yes", "Viewer / Dispatcher": "✅ Yes"},
                {"Capability": "Search and retrieve records",
                 "Admin / Commander": "✅ Yes", "Viewer / Dispatcher": "✅ Yes"},
                {"Capability": "Generate and download incident reports",
                 "Admin / Commander": "✅ Yes", "Viewer / Dispatcher": "✅ Yes"},
                {"Capability": "Log / edit / delete SOS alerts",
                 "Admin / Commander": "✅ Yes", "Viewer / Dispatcher": "⛔ No"},
                {"Capability": "Dispatch patrol units",
                 "Admin / Commander": "✅ Yes", "Viewer / Dispatcher": "⛔ No"},
                {"Capability": "Manage patrol fleet and divisions",
                 "Admin / Commander": "✅ Yes", "Viewer / Dispatcher": "⛔ No"},
                {"Capability": "Manage user accounts",
                 "Admin / Commander": "✅ Yes", "Viewer / Dispatcher": "⛔ No"},
            ]
        ),
        **FULL_WIDTH, hide_index=True,
    )

    left, right = st.columns([1.2, 1], gap="medium")

    with left:
        section_title("👥 Registered accounts")
        if users:
            frame = pd.DataFrame(
                [
                    {
                        "User ID": u["user_id"],
                        "Username": u["username"],
                        "Role": auth.ROLE_LABELS.get(u["role"], u["role"]),
                        "Created": format_timestamp(u["created_at"]),
                    }
                    for u in users
                ]
            )
            st.dataframe(frame, **FULL_WIDTH, hide_index=True)

    with right:
        section_title("➕ Create a new account")
        with st.form("create_user_form", clear_on_submit=True):
            new_username = st.text_input("Username", placeholder="e.g. dpo_ogui")
            new_password = st.text_input("Password", type="password",
                                         help="Minimum 6 characters.")
            new_role = st.selectbox("Role", ["Viewer", "Admin"],
                                    help="Viewer = read-only dispatcher. Admin = full command access.")
            if st.form_submit_button("👤 Create account", type="primary"):
                ok, message = auth.create_user(new_username, new_password, new_role)
                notify("success" if ok else "error", message)
                st.rerun()

        if new_password:
            score, label = auth.password_strength(new_password)
            st.progress(score / 4, text=f"Password strength: {label}")

        section_title("🔑 Reset a password")
        with st.form("reset_password_form", clear_on_submit=True):
            target = st.selectbox(
                "Account", [u["username"] for u in users] or ["—"],
            )
            reset_password = st.text_input("New password", type="password")
            if st.form_submit_button("🔑 Reset password"):
                match = next((u for u in users if u["username"] == target), None)
                if not match:
                    st.error("⛔ Account not found.")
                else:
                    ok, message = auth.change_password(match["user_id"], reset_password)
                    notify("success" if ok else "error", message)
                    st.rerun()

    section_title("🗑️ Remove an account")
    removable = [u for u in users if u["username"] != auth.current_username()]
    if removable:
        c1, c2 = st.columns([2, 1])
        with c1:
            target_name = st.selectbox("Select account", [u["username"] for u in removable])
        with c2:
            st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
            confirm = st.checkbox("Confirm deletion")
        if st.button("🗑️ Delete account", type="primary", disabled=not confirm):
            match = next((u for u in removable if u["username"] == target_name), None)
            if match:
                ok, message = auth.delete_user(match["user_id"])
                notify("success" if ok else "error", message)
                st.rerun()
    else:
        st.caption("There are no other accounts that can be removed.")


# =================================================================================
# 16. TWO-MODE ARCHITECTURE
# ---------------------------------------------------------------------------------
# The SAME Streamlit script now serves TWO completely different front ends, and
# both of them read from and write to the SAME SQLite file (data/sos_emergency.db):
#
#   MODE 1 - CITIZEN SOS APP      -> no login. A mobile-shaped panic-button page.
#                                    Writes a new row into sos_alerts (status
#                                    'Active') using the citizen's GPS position.
#
#   MODE 2 - POLICE COMMAND       -> the existing control-room dashboard, behind
#                                    the commander/dispatcher login. Polls the
#                                    database every 3 seconds, and RINGS LOUDLY
#                                    the moment a new ACTIVE alert appears.
#
# Switching is held in st.session_state["app_mode"] and mirrored into the URL
# query string (?mode=citizen / ?mode=police) so that the two modes can be
# opened side by side in two browser tabs - or on a laptop and a phone -
# and each tab keeps its own mode across a refresh.
# =================================================================================

MODE_CITIZEN = "🚨 Citizen SOS App"
MODE_POLICE = "👮 Police Command"
APP_MODES = [MODE_CITIZEN, MODE_POLICE]

#: How often the police dashboard polls the database for new SOS alerts.
ALARM_REFRESH_SECONDS = 3

#: An alert younger than this (in minutes) always rings, even if it was created
#: before the officer signed in - which covers the case where the citizen sends
#: the SOS first and the officer logs in a moment later.
ALARM_FRESH_MINUTES = 5

#: How long the "test alarm" diagnostic sounds for.
ALARM_TEST_SECONDS = 8


# ---------------------------------------------------------------------------------
# Mode switching
# ---------------------------------------------------------------------------------
def _mode_from_query() -> Optional[str]:
    """Read the requested mode from the URL query string, if present."""
    try:
        requested = str(st.query_params.get("mode") or "").strip().lower()
    except Exception:  # pragma: no cover - defensive
        return None

    if requested in ("citizen", "sos", "citizen-sos"):
        return MODE_CITIZEN
    if requested in ("police", "command", "dashboard", "police-command"):
        return MODE_POLICE
    return None


def get_app_mode() -> str:
    """
    Return the active mode, defaulting to the Police Command dashboard.

    A ``?mode=`` query parameter always wins on a fresh session, which is what
    makes it easy to open the citizen app on a phone by simply typing a URL.
    """
    if "app_mode" not in st.session_state:
        st.session_state["app_mode"] = _mode_from_query() or MODE_POLICE
    return st.session_state["app_mode"]


def set_app_mode(mode: str) -> None:
    """Switch modes and mirror the choice into the URL query string."""
    st.session_state["app_mode"] = mode
    try:
        wanted = "citizen" if mode == MODE_CITIZEN else "police"
        if str(st.query_params.get("mode") or "") != wanted:
            st.query_params["mode"] = wanted
    except Exception:  # pragma: no cover - query params are a convenience only
        pass


MODE_SWITCH_CSS = """
<style>
    .mode-brand {
        background: linear-gradient(120deg, #0b2545 0%, #13315c 55%, #1b4079 100%);
        border-radius: 12px; padding: 13px 20px; margin-bottom: 10px;
        border-left: 6px solid #ffd54f; box-shadow: 0 4px 14px rgba(11,37,69,.25);
        display: flex; align-items: center; justify-content: space-between;
        flex-wrap: wrap; gap: 8px;
    }
    .mode-brand .title { color: #ffffff; font-size: 17px; font-weight: 700; letter-spacing: .3px; }
    .mode-brand .sub { color: #b8c7dc; font-size: 11.5px; letter-spacing: .5px; margin-top: 2px; }
    .mode-brand .chip {
        font-size: 11px; font-weight: 700; padding: 3px 12px; border-radius: 11px;
        letter-spacing: .6px; background: #ffd54f; color: #0b2545;
    }
    .mode-brand .chip.police { background: #90caf9; color: #0b2545; }
    div[data-testid="stSegmentedControl"] button p { font-size: 14px; font-weight: 600; }
</style>
"""


def render_mode_switcher() -> str:
    """
    Draw the mode switcher at the very top of the page (before any login) and
    return the mode that is now active.
    """
    st.markdown(MODE_SWITCH_CSS, unsafe_allow_html=True)

    current = get_app_mode()
    is_citizen = current == MODE_CITIZEN

    chip_class = "chip" if is_citizen else "chip police"
    chip_text = "CITIZEN VIEW · NO LOGIN" if is_citizen else "COMMAND VIEW · STAFF ONLY"

    st.markdown(
        f"""
        <div class="mode-brand">
            <div>
                <div class="title">🚨 Emergency Response &amp; SOS Location Tracking System</div>
                <div class="sub">NIGERIA POLICE FORCE · ENUGU STATE COMMAND</div>
            </div>
            <div class="{chip_class}">{chip_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # A pair of large buttons acts as the mode switch.  Buttons are used
    # deliberately: they behave identically on every Streamlit version, on
    # desktop and on a phone touch screen, and the active mode is obvious
    # because it is drawn as the primary (filled) button.
    switch_left, switch_right = st.columns(2)
    with switch_left:
        if st.button("🚨  CITIZEN SOS", key="mode_btn_citizen",
                     type="primary" if is_citizen else "secondary", **FULL_WIDTH):
            if not is_citizen:
                set_app_mode(MODE_CITIZEN)
                st.session_state["page"] = None
                st.rerun()
    with switch_right:
        if st.button("👮  POLICE COMMAND", key="mode_btn_police",
                     type="primary" if not is_citizen else "secondary", **FULL_WIDTH):
            if is_citizen:
                set_app_mode(MODE_POLICE)
                st.rerun()

    if is_citizen:
        st.caption(
            "You are in the **Citizen SOS** view — no login required. Citizens use this "
            "page on their phone to send a distress call. Switch to **Police Command** "
            "for the control-room dashboard."
        )
    else:
        st.caption(
            "You are in the **Police Command** view — the control-room dashboard. Staff "
            "sign-in is required. Switch to **Citizen SOS** to see what the citizen sees "
            "on their phone."
        )

    return current


# ---------------------------------------------------------------------------------
# Small shared helpers used by both modes
# ---------------------------------------------------------------------------------
def parse_utc(value: Any) -> Optional[datetime]:
    """Parse a stored SQLite UTC timestamp into a ``datetime``."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def alert_age_minutes(value: Any) -> float:
    """Age of an alert in minutes (9999 when the timestamp cannot be read)."""
    stamp = parse_utc(value)
    if stamp is None:
        return 9999.0
    return max(0.0, (datetime.utcnow() - stamp).total_seconds() / 60.0)


def sound_bytes(which: str) -> bytes:
    """Return a generated WAV file as bytes, cached in the session."""
    key = f"_sound_bytes_{which}"
    if key not in st.session_state:
        st.session_state[key] = sounds.read_sound_bytes(which)
    return st.session_state[key]


def kick_html_audio() -> None:
    """
    Nudge any audio element in the page to play.

    Browsers block sound until the user has interacted with the page (Chrome's
    autoplay policy).  An officer has already clicked 'Sign in', so the document
    has "sticky activation" and playback is allowed - but calling ``play()``
    explicitly makes the alarm far more reliable, especially in the iframe that
    a Streamlit component renders in.
    """
    components.html(
        """
        <script>
        (function () {
            try {
                var doc = window.parent.document;
                function kick() {
                    var players = doc.querySelectorAll('audio');
                    for (var i = 0; i < players.length; i++) {
                        var a = players[i];
                        a.loop = true;
                        a.volume = 1.0;
                        var p = a.play();
                        if (p && p.catch) { p.catch(function () {}); }
                    }
                }
                kick();
                setTimeout(kick, 350);
                setTimeout(kick, 1200);
            } catch (e) { /* never let sound break the alert */ }
        })();
        </script>
        """,
        height=0,
    )


# =================================================================================
# 17. MODE 1 — THE CITIZEN SOS APP (mobile view, no login)
# =================================================================================
CITIZEN_CSS = """
<style>
    /* ---- mobile phone frame ------------------------------------------------- */
    .block-container { max-width: 640px !important; padding: 0.5rem 1rem 3rem 1rem !important; }
    header[data-testid="stHeader"] { display: none !important; }
    section[data-testid="stSidebar"],
    div[data-testid="stSidebarCollapsedControl"] { display: none !important; }
    #MainMenu, footer { visibility: hidden; }

    /* ---- compact app header ------------------------------------------------- */
    .ci-head {
        background: linear-gradient(140deg, #0b2545 0%, #13315c 55%, #1b4079 100%);
        border-radius: 0 0 20px 20px; padding: 12px 18px 15px 18px; text-align: center;
        box-shadow: 0 6px 18px rgba(11,37,69,.32); margin-bottom: 12px;
    }
    .ci-head .crest { font-size: 26px; line-height: 1; }
    .ci-head h2 { color: #fff; font-size: 15.5px; margin: 5px 0 2px 0; font-weight: 700; }
    .ci-head .sub { color: #b8c7dc; font-size: 10.5px; letter-spacing: .6px; }

    /* ---- section cards ------------------------------------------------------ */
    .ci-card {
        background: #ffffff; border: 1px solid #e2e8f0; border-radius: 14px;
        padding: 14px 16px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(16,39,57,.06);
    }
    .ci-card .ci-step,
    .ci-step {
        font-size: 11px; font-weight: 800; color: #0b2545; letter-spacing: 1px;
        text-transform: uppercase; margin-bottom: 6px;
    }
    .ci-prompt {
        font-size: 15px; font-weight: 700; color: #102027; text-align: center;
        margin: 2px 0 9px 0;
    }
    .ci-hint {
        font-size: 12.5px; color: #546e7a; text-align: center;
        margin: 10px 4px 14px 4px; line-height: 1.5;
    }

    /* ---- THE PANIC BUTTON --------------------------------------------------- */
    .st-key-sos_panic_button button {
        width: 100% !important; height: 200px !important; border-radius: 999px !important;
        background: radial-gradient(circle at 50% 28%, #ff7b7b 0%, #ef5350 28%,
                    #c62828 62%, #7f0000 100%) !important;
        color: #ffffff !important; font-size: 29px !important; font-weight: 900 !important;
        letter-spacing: 2.5px !important; line-height: 1.2 !important;
        border: 10px solid rgba(255,255,255,.92) !important;
        text-shadow: 0 3px 8px rgba(0,0,0,.45) !important;
        animation: sosPulse 1.6s infinite !important;
        margin: 0;
    }
    .st-key-sos_panic_button button:hover { filter: brightness(1.08); }
    .st-key-sos_panic_button button:active { transform: scale(.97); }
    @keyframes sosPulse {
        0%   { box-shadow: 0 0 0 0 rgba(229,57,53,.55), 0 12px 30px rgba(0,0,0,.35); }
        70%  { box-shadow: 0 0 0 36px rgba(229,57,53,0), 0 12px 30px rgba(0,0,0,.35); }
        100% { box-shadow: 0 0 0 0 rgba(229,57,53,0), 0 12px 30px rgba(0,0,0,.35); }
    }

    /* ---- the three one-tap categories --------------------------------------- */
    .st-key-citizen_quick_0 button,
    .st-key-citizen_quick_1 button,
    .st-key-citizen_quick_2 button {
        height: 86px !important; font-size: 14.5px !important; font-weight: 700 !important;
        white-space: normal !important; line-height: 1.3 !important;
        border-radius: 14px !important; padding: 6px 4px !important;
    }

    /* ---- success screen ----------------------------------------------------- */
    .ci-success {
        background: linear-gradient(150deg, #1b5e20 0%, #2e7d32 55%, #43a047 100%);
        border-radius: 18px; padding: 26px 22px; text-align: center; color: #fff;
        box-shadow: 0 10px 26px rgba(27,94,32,.35); margin-bottom: 16px;
    }
    .ci-success .big { font-size: 54px; line-height: 1; }
    .ci-success h2 { color: #fff; font-size: 24px; margin: 12px 0 6px 0; font-weight: 800; }
    .ci-success p { color: #dcedc8; font-size: 14px; margin: 4px 0 0 0; }

    .ci-track {
        background: #ffffff; border: 1px solid #e2e8f0; border-left: 6px solid #0b2545;
        border-radius: 12px; padding: 14px 16px; margin-bottom: 10px;
    }
    .ci-track .label { font-size: 11px; letter-spacing: 1px; color: #78909c;
                       text-transform: uppercase; font-weight: 700; }
    .ci-track .value { font-size: 16px; font-weight: 700; color: #102027; margin-top: 3px; }

    .ci-note { font-size: 12.5px; color: #546e7a; text-align: center; margin-top: 10px; }
</style>
"""

#: The THREE one-tap choices on the citizen screen, in priority order.
#:
#: (icon, button label, value stored in sos_alerts.emergency_type, phrase used
#:  in the description)
#:
#: A frightened caller must be able to raise an alarm in one press, so only
#: three broad choices are offered - and none of them is compulsory.  They map
#: onto the five values the database CHECK constraint accepts, which keeps the
#: police register fully classified, while the caller's own words are always
#: preserved in the description so nothing is lost if an officer reclassifies
#: the incident later.
CITIZEN_QUICK_CATEGORIES = [
    ("🔫", "Robbery / Theft", "Armed Robbery",
     "robbery, theft or armed attack"),
    ("🥊", "Fight / Attack", "Other",
     "fight, assault or physical attack"),
    ("🚑", "Health Emergency", "Medical",
     "medical emergency - someone is ill or injured"),
]


def _citizen_defaults() -> None:
    """Seed the citizen form fields the first time the page is opened."""
    # NOTE ON WHY THE SAVED_* KEYS EXIST
    # Widget values live under the widget's own key, and Streamlit discards that
    # state if the widget is not rendered during a run.  Pressing the SOS button
    # ends its run with st.rerun() *before* the inputs further down the page are
    # drawn, so those inputs would be reset.  Copying the caller's details into
    # ordinary (non-widget) keys lets them survive and be offered again for a
    # second SOS from the same phone.
    st.session_state.setdefault("citizen_saved_name", "")
    st.session_state.setdefault("citizen_saved_phone", "")

    st.session_state.setdefault("citizen_name", st.session_state["citizen_saved_name"])
    st.session_state.setdefault("citizen_phone", st.session_state["citizen_saved_phone"])
    st.session_state.setdefault("citizen_note", "")
    #: Index into CITIZEN_QUICK_CATEGORIES, or None for "not specified".
    #: None is perfectly acceptable - the SOS button works without a choice.
    st.session_state.setdefault("citizen_quick", None)
    st.session_state.setdefault("citizen_lat", float(haversine.ENUGU_CENTER_LAT))
    st.session_state.setdefault("citizen_lon", float(haversine.ENUGU_CENTER_LON))
    st.session_state.setdefault("citizen_gps_note", "")


def _citizen_pick_category(index: int) -> None:
    """
    ``on_click`` callback for the one-tap emergency category chips.

    A callback is used rather than ``if st.button(...): ... st.rerun()`` on
    purpose.  An explicit ``st.rerun()`` aborts the current run at that point,
    which would prevent every widget further down the page from being rendered -
    and Streamlit would then discard whatever the caller had already typed into
    them.  Callbacks run *before* the page is drawn, so nothing is lost.
    """
    st.session_state["citizen_quick"] = (
        None if st.session_state.get("citizen_quick") == index else index
    )


def _citizen_use_simulated_location() -> None:
    """``on_click`` callback: drop the caller at Ogui Road, Enugu."""
    st.session_state["citizen_lat"] = 6.4521
    st.session_state["citizen_lon"] = 7.5089
    st.session_state["citizen_gps_note"] = (
        "📍 Simulated location applied: Ogui Road, Enugu (6.452100, 7.508900)"
    )


def _consume_citizen_query_params() -> None:
    """
    Pick up the coordinates that the browser's GPS button put into the URL.

    The geolocation API only exists in JavaScript, so the mobile page hands the
    position back to Python by reloading the app with ``?lat=..&lon=..`` in the
    query string.  This function reads those values (exactly once per distinct
    position) and drops them into the form.
    """
    try:
        params = st.query_params
        latitude = params.get("lat")
        longitude = params.get("lon")
    except Exception:  # pragma: no cover - defensive
        return

    if latitude and longitude:
        token = f"{latitude}|{longitude}"
        if token != st.session_state.get("_citizen_gps_token"):
            try:
                st.session_state["_citizen_gps_token"] = token
                st.session_state["citizen_lat"] = float(latitude)
                st.session_state["citizen_lon"] = float(longitude)
                st.session_state["citizen_gps_note"] = (
                    f"📡 GPS captured from this device: "
                    f"{float(latitude):.6f}, {float(longitude):.6f}"
                )
            except (TypeError, ValueError):
                pass

    # Carry the typed-in details across the reload as well.
    for query_key, state_key in (("name", "citizen_name"),
                                 ("phone", "citizen_phone"),
                                 ("etype", "citizen_type")):
        try:
            value = params.get(query_key)
        except Exception:  # pragma: no cover
            value = None
        if not value:
            continue
        if value == st.session_state.get(f"_qp_{query_key}"):
            continue
        st.session_state[f"_qp_{query_key}"] = value
        if state_key == "citizen_type" and value not in EMERGENCY_TYPES:
            continue
        st.session_state[state_key] = value


def _geolocation_panel() -> None:
    """
    Render the "read my GPS" panel.

    This is a small HTML component because ``navigator.geolocation`` only exists
    in JavaScript.  The button inside it obtains the fix and then reloads the
    top-level page with the coordinates in the query string.
    """
    name_js = json.dumps(str(st.session_state.get("citizen_name") or ""))
    phone_js = json.dumps(str(st.session_state.get("citizen_phone") or ""))
    type_js = json.dumps(str(st.session_state.get("citizen_type") or ""))

    components.html(
        f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif">
          <div style="font-size:12.5px;color:#546e7a;margin-bottom:8px" id="geoStatus">
            Tap the button to read the coordinates from this phone's GPS receiver.
          </div>
          <button id="geoBtn" style="
              width:100%; padding:13px 16px; border-radius:10px; cursor:pointer;
              border:1px solid #0b2545; background:#ffffff; color:#0b2545;
              font-size:14.5px; font-weight:700; font-family:inherit;">
            📡 Detect My GPS Location
          </button>
        </div>
        <script>
        (function () {{
            var NAME = {name_js}, PHONE = {phone_js}, ETYPE = {type_js};
            var status = document.getElementById('geoStatus');
            document.getElementById('geoBtn').onclick = function () {{
                if (!navigator.geolocation) {{
                    status.textContent = 'This browser does not support GPS. Use the simulated Enugu location below.';
                    return;
                }}
                status.textContent = 'Reading GPS fix... please tap ALLOW if your browser asks.';
                navigator.geolocation.getCurrentPosition(function (pos) {{
                    var la = pos.coords.latitude.toFixed(6);
                    var lo = pos.coords.longitude.toFixed(6);
                    status.textContent = 'GPS fix found: ' + la + ', ' + lo + ' — sending to the app...';
                    var q = new URLSearchParams();
                    q.set('mode', 'citizen');
                    q.set('lat', la);
                    q.set('lon', lo);
                    q.set('gps', '1');
                    if (NAME)  {{ q.set('name', NAME); }}
                    if (PHONE) {{ q.set('phone', PHONE); }}
                    if (ETYPE) {{ q.set('etype', ETYPE); }}
                    window.parent.location.href =
                        window.parent.location.pathname + '?' + q.toString();
                }}, function (err) {{
                    status.textContent = 'GPS unavailable (' + err.message +
                        '). Please tap "Use Simulated Enugu Location" instead.';
                }}, {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }});
            }};
        }})();
        </script>
        """,
        height=105,
    )


def _citizen_form_screen() -> None:
    """The main panic-button screen."""
    _citizen_defaults()
    _consume_citizen_query_params()

    # ---------------- validation errors from the previous attempt ----------
    for message in st.session_state.pop("citizen_errors", []):
        st.error(f"⛔ {message}")

    # ==================================================================
    #  DESIGN RULE: the victim is frightened and in a hurry.
    #  Nothing on this screen may be required.  The page is therefore
    #  ordered as
    #      1. one optional one-tap category  (three choices, not a form)
    #      2. THE BIG RED BUTTON            (above the fold, works alone)
    #      3. everything else               (optional, AFTER the button)
    # ==================================================================

    # ---------------- OPTIONAL: one-tap category ---------------------------
    quick = st.session_state.get("citizen_quick")
    st.markdown(
        "<div class='ci-prompt'>What is happening? "
        "<span style='font-weight:400;color:#78909c'>(optional — tap one, or just press SOS)</span></div>",
        unsafe_allow_html=True,
    )

    quick_columns = st.columns(3)
    for index, (icon, label, _db_type, _phrase) in enumerate(CITIZEN_QUICK_CATEGORIES):
        with quick_columns[index]:
            is_selected = quick == index
            st.button(
                f"{icon} {label}",
                key=f"citizen_quick_{index}",
                type="primary" if is_selected else "secondary",
                on_click=_citizen_pick_category,
                args=(index,),
                **FULL_WIDTH,
            )

    # ---------------- THE PANIC BUTTON (nothing required above it) ---------
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if st.button("🚨  SOS  EMERGENCY", key="sos_panic_button", **FULL_WIDTH):
        _submit_citizen_sos()
        st.rerun()

    st.markdown(
        "<div class='ci-hint'>Press the button — that is all you have to do. "
        "Your position is sent automatically and help is on the way. "
        "You can add your name and number afterwards if you are able to.</div>",
        unsafe_allow_html=True,
    )

    # ---------------- OPTIONAL: location (already set sensibly) ------------
    with st.container(border=True):
        st.markdown("<div class='ci-step'>📍 Your location (already set)</div>",
                    unsafe_allow_html=True)
        st.markdown(
            f"""
            <div style="font-size:13px;color:#37474f;margin-bottom:8px">
                Sending:
                <b style="font-family:Consolas,monospace">
                    {float(st.session_state['citizen_lat']):.6f},
                    {float(st.session_state['citizen_lon']):.6f}
                </b>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.get("citizen_gps_note"):
            st.success(st.session_state["citizen_gps_note"])

        # The reliable, always-works option - used for the defence demonstration.
        # An on_click callback is used so that pressing it cannot discard the
        # details the caller has already typed (see _citizen_pick_category).
        st.button("📍 Use Simulated Enugu Location  (Ogui Road area)",
                  key="citizen_sim_loc",
                  on_click=_citizen_use_simulated_location,
                  **FULL_WIDTH)

        # The real device GPS, handed back to Python through the URL.
        _geolocation_panel()

        with st.expander("⌨️ Enter the coordinates manually"):
            st.number_input("Latitude", key="citizen_lat", format="%.6f",
                            min_value=-90.0, max_value=90.0, step=0.000100)
            st.number_input("Longitude", key="citizen_lon", format="%.6f",
                            min_value=-180.0, max_value=180.0, step=0.000100)
            if not haversine.is_within_command_area(st.session_state["citizen_lat"],
                                                    st.session_state["citizen_lon"]):
                st.warning("⚠️ These coordinates are outside the Enugu State Command area.")

    # ---------------- OPTIONAL: who is calling -----------------------------
    with st.container(border=True):
        st.markdown(
            "<div class='ci-step'>👤 Your details "
            "<span style='font-weight:400;color:#78909c'>(optional)</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Only so that an officer can call you back. Leave blank and the alert "
            "is still sent."
        )
        st.text_input("Your name", key="citizen_name",
                      placeholder="e.g. John Doe", autocomplete="name")
        st.text_input("Your phone number", key="citizen_phone",
                      placeholder="e.g. 08034567890", autocomplete="tel")
        st.text_area("Anything else the officers should know", key="citizen_note",
                     height=70,
                     placeholder="e.g. Two armed men, one is wearing a black cap...")


#: How long after sending an SOS a second press is ignored.
#:
#: A frightened caller very often taps the button twice, and Streamlit delivers
#: a press as a single-run trigger - so this debounce prevents one person's panic
#: from putting two incidents on the control room's board (and setting off two
#: alarms).  It also makes the citizen screen safe to double-tap on a phone.
CITIZEN_DOUBLE_TAP_SECONDS = 8.0


def _submit_citizen_sos() -> None:
    """
    Write the SOS alert immediately.

    IMPORTANT: nothing is validated as mandatory here.  In a real emergency the
    only thing that matters is that a location reaches the control room, and the
    location always has a value.  Name and phone number are recorded when the
    caller supplied them and marked as not provided otherwise - the officers can
    still see the incident, find it on the map and dispatch a unit.
    """
    # ---- debounce: ignore a second press straight after a successful one ----
    previous_id = st.session_state.get("citizen_last_alert_id")
    last_sent = float(st.session_state.get("citizen_last_send_ts") or 0)
    if previous_id and last_sent and (time.time() - last_sent) < CITIZEN_DOUBLE_TAP_SECONDS:
        # The alert is already with the Command; just show the tracking screen.
        return

    name = (st.session_state.get("citizen_name") or "").strip()
    phone = (st.session_state.get("citizen_phone") or "").strip()
    note = (st.session_state.get("citizen_note") or "").strip()

    quick = st.session_state.get("citizen_quick")
    if isinstance(quick, int) and 0 <= quick < len(CITIZEN_QUICK_CATEGORIES):
        _icon, quick_label, emergency_type, quick_phrase = CITIZEN_QUICK_CATEGORIES[quick]
    else:
        quick_label = "Not specified"
        emergency_type = "Other"
        quick_phrase = "Emergency of unspecified type"

    try:
        latitude = float(st.session_state.get("citizen_lat"))
        longitude = float(st.session_state.get("citizen_lon"))
    except (TypeError, ValueError):
        st.session_state["citizen_errors"] = [
            "Your position could not be read. Please press the SOS button again."
        ]
        return

    # Describe the call in the officer's language, starting with what the
    # caller tapped so it survives even if the type is later reclassified.
    parts = [f"SOS raised from the Citizens' SOS app. Reported as: {quick_phrase}."]
    if note:
        parts.append(note)
    if not name and not phone:
        parts.append("Caller did not leave a name or call-back number.")
    description = " ".join(parts)

    ok, message, alert_id = create_alert(
        {
            "citizen_name": name or "Unknown caller",
            "phone_number": phone or "Not provided",
            "latitude": latitude,
            "longitude": longitude,
            "emergency_type": emergency_type,
            "description": description,
            "status": "Active",
        },
        actor=f"citizen:{name}" if name else "citizen:app",
    )

    if not ok:
        st.session_state["citizen_errors"] = [message]
        return

    # Remember which alert this phone created so we can track its progress.
    st.session_state["citizen_last_alert_id"] = alert_id
    st.session_state["citizen_last_send_ts"] = time.time()
    # Keep the caller's details outside the widget keys so they are still there
    # for a second SOS (this run ends with st.rerun(), which resets the inputs).
    st.session_state["citizen_saved_name"] = name
    st.session_state["citizen_saved_phone"] = phone
    st.session_state["citizen_sent_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["citizen_beep_pending"] = True
    st.session_state["citizen_quick_label"] = quick_label
    st.session_state.pop("citizen_errors", None)


def _citizen_tracking_body() -> None:
    """Live status panel - re-runs every 3 seconds so the citizen sees progress."""
    alert_id = st.session_state.get("citizen_last_alert_id")
    alert = get_alert(int(alert_id)) if alert_id else None

    if not alert:
        st.warning("Your alert could not be found. Please send a new SOS.")
        return

    status = alert["status"]
    meta = STATUS_META.get(status, {"colour": "#424242", "icon": "🔵"})

    assigned = None
    if alert.get("assigned_unit_id"):
        assigned = safe_fetch_one(
            "SELECT * FROM patrol_units WHERE unit_id = ?", (alert["assigned_unit_id"],),
            "the responding unit",
        )

    if status == "Active":
        headline = "Your SOS has reached the control room"
        detail = ("A dispatcher is looking at your location now. "
                  "Keep this screen open and keep your phone line free.")
    elif status == "Dispatched":
        headline = "A patrol unit has been dispatched to you"
        detail = ("Stay where you are if it is safe to do so. "
                  "The officers are on their way to your GPS position.")
    elif status == "Resolved":
        headline = "This incident has been marked as resolved"
        detail = "If you still need help, send a new SOS immediately."
    else:
        headline = "This alert was closed as a false alarm"
        detail = "If this was a mistake, please send a new SOS."

    st.markdown(
        f"""
        <div class="ci-track" style="border-left-color:{meta['colour']}">
            <div class="label">Live status · updates every 3 seconds</div>
            <div class="value">{meta['icon']} {html_lib.escape(status)}</div>
            <div style="font-size:13.5px;color:#37474f;margin-top:8px">{html_lib.escape(headline)}</div>
            <div style="font-size:12.5px;color:#607d8b;margin-top:5px">{html_lib.escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    with cols[0]:
        st.markdown(
            f"""
            <div class="ci-track">
                <div class="label">Incident number</div>
                <div class="value">SOS-{int(alert['alert_id']):05d}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f"""
            <div class="ci-track">
                <div class="label">Emergency type</div>
                <div class="value">{TYPE_ICON.get(alert['emergency_type'], '📞')}
                    {html_lib.escape(str(alert['emergency_type']))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if assigned:
        distance = haversine.calculate_distance(
            alert["latitude"], alert["longitude"],
            assigned["current_lat"], assigned["current_long"],
        )
        eta = haversine.estimate_arrival_time(distance)
        st.markdown(
            f"""
            <div class="ci-track" style="border-left-color:#2e7d32">
                <div class="label">Responding unit</div>
                <div class="value">🚔 {html_lib.escape(str(assigned['unit_callsign']))}</div>
                <div style="font-size:13px;color:#37474f;margin-top:5px">
                    Officer: {html_lib.escape(str(assigned['officer_name']))}<br>
                    Distance from you: <b>{distance:.2f} km</b> ·
                    Estimated arrival: <b>{haversine.format_eta(eta)}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="ci-track" style="border-left-color:#ef6c00">
                <div class="label">Responding unit</div>
                <div class="value">🕒 Being assigned</div>
                <div style="font-size:12.5px;color:#607d8b;margin-top:5px">
                    The nearest available patrol unit is being alerted.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


if hasattr(st, "fragment"):
    _citizen_tracking_live = st.fragment(run_every=ALARM_REFRESH_SECONDS)(_citizen_tracking_body)
else:  # pragma: no cover - older Streamlit builds
    _citizen_tracking_live = _citizen_tracking_body


def _citizen_success_screen() -> None:
    """Confirmation screen shown immediately after the SOS is saved."""
    alert_id = st.session_state.get("citizen_last_alert_id")
    alert = get_alert(int(alert_id)) if alert_id else None
    if not alert:
        st.session_state.pop("citizen_last_alert_id", None)
        st.rerun()
        return

    # ---- the confirmation chime (plays once, on this phone) ---------------
    if st.session_state.get("citizen_beep_pending"):
        st.session_state["citizen_beep_pending"] = False
        beep = sound_bytes("beep")
        if beep:
            st.audio(beep, format="audio/wav", autoplay=True)
            kick_html_audio()

    st.markdown(
        f"""
        <div class="ci-success">
            <div class="big">🚨</div>
            <h2>SOS SENT!</h2>
            <p style="font-size:16px;font-weight:600">Help is on the way. Stay calm.</p>
            <p>Your distress call has reached the Enugu State Police Command control room.</p>
            <div style="margin-top:14px;font-size:13px;color:#f1f8e9">
                Incident ID <b>SOS-{int(alert['alert_id']):05d}</b> ·
                {html_lib.escape(str(alert['emergency_type']))} ·
                sent {html_lib.escape(format_timestamp(alert['created_at']))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown("<div class='ci-step'>What happens now</div>", unsafe_allow_html=True)
        st.markdown(
            """
            1. The control room dashboard **rings an alarm** and shows your exact position on the map.
            2. The system **calculates which patrol unit is nearest** to you.
            3. The nearest unit is **dispatched to your GPS coordinates**.
            4. This screen updates automatically so you can see the officer's arrival time.
            """
        )

    _citizen_tracking_live()

    # ---------------- OPTIONAL: add details AFTER the alert is already sent --
    # The alert is already with the control room.  Anything here simply
    # improves the record, so a caller who is hiding, running or injured can
    # ignore it completely.
    current_name = str(alert.get("citizen_name") or "")
    current_phone = str(alert.get("phone_number") or "")
    already_given = current_name not in ("", "Unknown caller") or current_phone not in ("", "Not provided")

    with st.container(border=True):
        st.markdown(
            "<div class='ci-step'>➕ Add your details "
            "<span style='font-weight:400;color:#78909c'>(optional)</span></div>",
            unsafe_allow_html=True,
        )
        if already_given:
            st.caption("So far the Command has: "
                       f"**{html_lib.escape(current_name)}** · "
                       f"**{html_lib.escape(current_phone)}**. "
                       "You can still correct it below.")
        else:
            st.caption(
                "Only if you are able to. Giving an officer a number to call back "
                "makes it faster — but your SOS has already been sent."
            )

        with st.form("citizen_add_details", clear_on_submit=False):
            add_name = st.text_input("Your name", value="" if current_name == "Unknown caller" else current_name)
            add_phone = st.text_input("Phone number",
                                      value="" if current_phone == "Not provided" else current_phone)
            if st.form_submit_button("💾 Send these details to the Command", **FULL_WIDTH):
                try:
                    db.execute_query(
                        """
                        UPDATE sos_alerts
                        SET citizen_name = ?, phone_number = ?
                        WHERE alert_id = ?
                        """,
                        (add_name.strip() or "Unknown caller",
                         add_phone.strip() or "Not provided",
                         int(alert["alert_id"])),
                    )
                    db.log_activity(
                        "ALERT_UPDATED",
                        f"Citizen supplied further details for SOS-{int(alert['alert_id']):05d}",
                        actor="citizen:app",
                        alert_id=int(alert["alert_id"]),
                    )
                    # keep them for any future SOS from this phone
                    st.session_state["citizen_name"] = add_name.strip()
                    st.session_state["citizen_phone"] = add_phone.strip()
                    notify("success", "Details sent to the control room.")
                    st.rerun()
                except db.DatabaseError as exc:
                    st.error(f"⛔ Could not save your details: {exc}")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    if st.button("🏠 Back to the SOS home screen", key="citizen_back", **FULL_WIDTH):
        st.session_state.pop("citizen_last_alert_id", None)
        st.session_state.pop("citizen_gps_note", None)
        st.session_state["citizen_last_send_ts"] = 0
        st.session_state["citizen_note"] = ""
        st.rerun()


def render_citizen_app() -> None:
    """Entry point for MODE 1 - the Citizen SOS app."""
    st.markdown(CITIZEN_CSS, unsafe_allow_html=True)

    st.markdown(
        """
        <div class="ci-head">
            <div class="crest">🚨</div>
            <h2>Enugu State Police — SOS</h2>
            <div class="sub">NIGERIA POLICE FORCE · EMERGENCY RESPONSE</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.session_state.get("citizen_last_alert_id"):
        _citizen_success_screen()
    else:
        _citizen_form_screen()


# =================================================================================
# 18. MODE 2 — THE POLICE ALARM SYSTEM (auto-refresh + ringing + flashing border)
# =================================================================================
def _ensure_alarm_state() -> None:
    """
    Prepare the alarm bookkeeping for this officer's session.

    ``alarm_baseline_max`` records the highest alert id that existed when the
    officer signed in.  Anything above it is unambiguously a NEW arrival, so
    signing in never sets the alarm off for old incidents.
    """
    if "alarm_baseline_max" not in st.session_state:
        try:
            st.session_state["alarm_baseline_max"] = int(
                db.fetch_scalar("SELECT COALESCE(MAX(alert_id), 0) FROM sos_alerts",
                                default=0) or 0
            )
        except db.DatabaseError:
            st.session_state["alarm_baseline_max"] = 0
    if "alarm_acknowledged" not in st.session_state:
        st.session_state["alarm_acknowledged"] = set()


def alarm_snapshot() -> tuple[list[dict], list[dict]]:
    """
    Return ``(pending, ringing)``.

    pending
        Active alerts this officer has not yet acknowledged - these are shown in
        the "NEW EMERGENCY" banner.
    ringing
        The subset that should actually make a noise: either a genuinely new
        arrival (alert_id above the sign-in baseline) or a very recent one
        (raised within ALARM_FRESH_MINUTES), which covers a citizen sending the
        SOS moments before the officer signs in.
    """
    _ensure_alarm_state()

    rows = db.fetch_all(
        "SELECT * FROM sos_alerts WHERE status = 'Active' ORDER BY alert_id DESC"
    )
    acknowledged = st.session_state.get("alarm_acknowledged") or set()
    baseline = int(st.session_state.get("alarm_baseline_max") or 0)

    pending = [row for row in rows if int(row["alert_id"]) not in acknowledged]
    ringing = [
        row for row in pending
        if int(row["alert_id"]) > baseline
        or alert_age_minutes(row.get("created_at")) <= ALARM_FRESH_MINUTES
    ]
    return pending, ringing


def _render_flashing_border() -> None:
    """Draw the flashing red frame around the whole dashboard."""
    st.markdown(
        """
        <div class="sos-flash-frame"></div>
        <style>
            .sos-flash-frame {
                position: fixed; inset: 0; pointer-events: none; z-index: 99999;
                border: 11px solid #ff1744;
                box-shadow: inset 0 0 70px rgba(255, 23, 68, .55);
                animation: sosFlash .75s steps(1) infinite;
            }
            @keyframes sosFlash {
                0%, 49%   { opacity: 1;   border-color: #ff1744; }
                50%, 100% { opacity: .12; border-color: #ff1744; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_new_emergency_banner(alert: dict, ringing: bool) -> None:
    """The big banner naming the citizen, the emergency type and the location."""
    if ringing:
        background = "linear-gradient(90deg,#b71c1c 0%,#e53935 60%,#ff5252 100%)"
        title = "🚨 NEW EMERGENCY! 🚨"
        pulse = "animation: sosBannerPulse 1s infinite;"
    else:
        background = "linear-gradient(90deg,#e65100 0%,#ef6c00 60%,#fb8c00 100%)"
        title = "⚠️ ACTIVE EMERGENCY AWAITING ATTENTION"
        pulse = ""

    st.markdown(
        f"""
        <style>@keyframes sosBannerPulse {{
            0%   {{ box-shadow: 0 0 0 0 rgba(183,28,28,.7); }}
            70%  {{ box-shadow: 0 0 0 18px rgba(183,28,28,0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(183,28,28,0); }}
        }}</style>
        <div style="background:{background};color:#fff;border-radius:12px;
                    padding:16px 20px;margin-bottom:12px;{pulse}
                    box-shadow:0 6px 20px rgba(183,28,28,.4)">
            <div style="font-size:13px;font-weight:800;letter-spacing:2.5px">{title}</div>
            <div style="font-size:24px;font-weight:800;margin-top:6px;line-height:1.25">
                {TYPE_ICON.get(alert['emergency_type'], '📞')}
                {html_lib.escape(str(alert['emergency_type']))}
                &nbsp;·&nbsp; {html_lib.escape(str(alert['citizen_name']))}
            </div>
            <div style="font-size:14px;margin-top:8px;color:#ffe4e1">
                📞 {html_lib.escape(str(alert['phone_number']))}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                📍 {float(alert['latitude']):.6f}, {float(alert['longitude']):.6f}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                🕒 received {html_lib.escape(rel_time(alert['created_at']))}
                &nbsp;&nbsp;|&nbsp;&nbsp;
                🆔 SOS-{int(alert['alert_id']):05d}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_alarm_nearest_units(alert: dict) -> None:
    """Show the three nearest patrol units inside the alarm panel."""
    try:
        units = load_units()
    except db.DatabaseError:
        return

    ranked = haversine.find_nearest_units(
        alert["latitude"], alert["longitude"], units, top_n=3, available_only=True
    )
    if not ranked:
        st.warning("No patrol unit is currently available for dispatch.")
        return

    section_title("🧭 Nearest available patrol units (calculated automatically)")
    medals = ["🥇", "🥈", "🥉"]
    columns = st.columns(len(ranked))
    for index, match in enumerate(ranked):
        with columns[index]:
            st.markdown(
                f"""
                <div class="info-card rank{min(index + 1, 3)}">
                    <div class="callsign">{medals[index]} {html_lib.escape(str(match['unit_callsign']))}</div>
                    <div class="officer">👮 {html_lib.escape(str(match['officer_name']))}</div>
                    <div class="stats">
                        📏 <b>{match['distance_km']:.2f} km</b> away<br>
                        ⏱️ ETA <b>{html_lib.escape(match['eta_text'])}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _alarm_monitor_body() -> None:
    """
    The police alarm monitor - re-runs every ALARM_REFRESH_SECONDS.

    It is rendered on EVERY police page, so the alarm finds the officer wherever
    they are in the dashboard.
    """
    if not auth.is_authenticated():
        return

    try:
        pending, ringing = alarm_snapshot()
    except db.DatabaseError as exc:
        st.warning(f"⚠️ Could not poll for new SOS alerts: {exc}")
        return

    # ---- a brand new arrival: refresh the WHOLE page once ---------------
    # The monitor itself re-runs every 3 seconds, but the rest of the page
    # (the overview map, the KPI cards, the alert register) only redraws on a
    # full application re-run.  When a genuinely new alert appears we therefore
    # trigger exactly one full re-run, guarded by _alarm_last_broadcast so it
    # can never loop.
    newest_id = int(ringing[0]["alert_id"]) if ringing else 0
    if newest_id and newest_id != int(st.session_state.get("_alarm_last_broadcast") or 0):
        st.session_state["_alarm_last_broadcast"] = newest_id
        st.rerun(scope="app")

    # ---- the manual "test alarm" diagnostic ------------------------------
    testing = time.time() < float(st.session_state.get("alarm_test_until") or 0)
    alarm_on = bool(ringing) or testing

    focus_alert = ringing[0] if ringing else (pending[0] if pending else None)

    # ---- SOUND + FLASHING BORDER ----------------------------------------
    if alarm_on:
        _render_flashing_border()
        alarm_wav = sound_bytes("alarm")
        if alarm_wav:
            # loop=True keeps ringing until the alert is acknowledged or the
            # element disappears from the page.
            st.audio(alarm_wav, format="audio/wav", autoplay=True, loop=True)
            kick_html_audio()

    # ---- BANNER ----------------------------------------------------------
    if focus_alert is not None:
        _render_new_emergency_banner(focus_alert, ringing=bool(ringing))

        if len(pending) > 1:
            st.caption(f"ℹ️ {len(pending)} active SOS alerts are awaiting acknowledgement.")

        # ---- the three nearest units -------------------------------------
        _render_alarm_nearest_units(focus_alert)

        # ---- action buttons ----------------------------------------------
        action_left, action_mid, action_right, action_last = st.columns([1, 1.15, 1, 1])

        with action_left:
            if st.button("🔔 Silence Alarm", key="alarm_silence", type="primary", **FULL_WIDTH):
                acknowledged = set(st.session_state.get("alarm_acknowledged") or set())
                acknowledged.update(int(row["alert_id"]) for row in pending)
                st.session_state["alarm_acknowledged"] = acknowledged
                st.session_state["alarm_test_until"] = 0
                db.log_activity(
                    "ALARM_SILENCED",
                    f"Alarm silenced by {auth.current_username()} "
                    f"({len(pending)} active alert(s) acknowledged)",
                    actor=auth.current_username(),
                    alert_id=int(focus_alert["alert_id"]),
                )
                st.rerun(scope="app")

        with action_mid:
            if st.button("📲 Mark as Dispatched", key="alarm_dispatch", **FULL_WIDTH,
                         help="Sends the nearest available patrol unit and stops the alarm."):
                _dispatch_nearest_from_alarm(focus_alert)

        with action_right:
            if st.button("🎭 DEMO MODE", key="alarm_demo", **FULL_WIDTH,
                         help="Injects a simulated incoming SOS alert - your backup if the "
                              "live phone demonstration fails."):
                _inject_demo_alert()

        with action_last:
            if st.button("🗺️ Open live map", key="alarm_map", **FULL_WIDTH):
                nav_callback("🗺️ Live SOS Map",
                             {"focus_alert_id": int(focus_alert["alert_id"])})
                st.rerun(scope="app")

    else:
        # ---- quiet state ---------------------------------------------------
        beats = st.columns([2.6, 1, 1])
        with beats[0]:
            st.markdown(
                """
                <div style="border:1px solid #c8e6c9;background:#f1f8e9;border-radius:10px;
                            padding:9px 14px;font-size:13px;color:#2e7d32;font-weight:600">
                    ✅ Control room quiet — no unacknowledged SOS alerts.
                </div>
                """,
                unsafe_allow_html=True,
            )
        with beats[1]:
            if st.button("🔔 Test alarm", key="alarm_test", **FULL_WIDTH,
                         help="Plays the ringing alarm for a few seconds to check the speakers."):
                st.session_state["alarm_test_until"] = time.time() + ALARM_TEST_SECONDS
                st.rerun(scope="app")
        with beats[2]:
            if st.button("🎭 DEMO MODE", key="alarm_demo_quiet", **FULL_WIDTH,
                         help="Injects a simulated incoming SOS alert."):
                _inject_demo_alert()

    st.caption(
        f"📡 Monitoring for new SOS alerts every {ALARM_REFRESH_SECONDS} seconds · "
        f"last check {datetime.utcnow().strftime('%H:%M:%S')} UTC · "
        f"citizen app writes to the same database file"
    )


def _dispatch_nearest_from_alarm(alert: dict) -> None:
    """Send the nearest available patrol unit to the alert and stop the alarm."""
    try:
        units = load_units()
        ranked = haversine.find_nearest_units(
            alert["latitude"], alert["longitude"], units, top_n=1, available_only=True
        )
        if not ranked:
            notify("error", "No patrol unit is available. Bring a unit back online first.")
            st.rerun(scope="app")
            return

        ok, message = dispatch_unit(int(alert["alert_id"]), ranked[0]["unit_id"],
                                    actor=auth.current_username())

        acknowledged = set(st.session_state.get("alarm_acknowledged") or set())
        acknowledged.add(int(alert["alert_id"]))
        st.session_state["alarm_acknowledged"] = acknowledged
        st.session_state["alarm_test_until"] = 0
        st.session_state["focus_alert_id"] = int(alert["alert_id"])

        notify("success" if ok else "error", message)
        st.rerun(scope="app")
    except db.DatabaseError as exc:
        notify("error", str(exc))
        st.rerun(scope="app")


def _inject_demo_alert() -> None:
    """DEMO MODE: inject a realistic incoming SOS call as a backup."""
    ok, message, alert_id = simulate_incoming_alert(auth.current_username())
    if ok and alert_id:
        st.session_state["focus_alert_id"] = int(alert_id)
        # Make sure the new alert is treated as a fresh arrival so it rings.
        acknowledged = set(st.session_state.get("alarm_acknowledged") or set())
        acknowledged.discard(int(alert_id))
        st.session_state["alarm_acknowledged"] = acknowledged
        notify("error", f"🎭 DEMO SOS injected — {message}")
    else:
        notify("error", message)
    st.rerun(scope="app")


if hasattr(st, "fragment"):
    _alarm_monitor = st.fragment(run_every=ALARM_REFRESH_SECONDS)(_alarm_monitor_body)
else:  # pragma: no cover - older Streamlit builds
    _alarm_monitor = _alarm_monitor_body


# =================================================================================
# 19. NAVIGATION & APPLICATION ENTRY POINT
# =================================================================================
PAGE_REGISTRY = {
    "📊 Command Dashboard": page_dashboard,
    "🗺️ Live SOS Map": page_live_map,
    "🚨 SOS Alert Management": page_sos_alerts,
    "🧭 Nearest Unit Calculator": page_nearest_units,
    "🚔 Patrol Units": page_patrol_units,
    "🏛️ Police Stations": page_stations,
    "📄 Incident Report": page_incident_report,
    "🔍 Search & Retrieve": page_search,
    "👤 User Management": page_users,
}

ADMIN_ONLY_PAGES = {"👤 User Management"}


def render_sidebar() -> str:
    """Draw the sidebar and return the selected page label."""
    user = auth.get_current_user() or {}
    is_admin = user.get("role") == "Admin"

    with st.sidebar:
        st.markdown(
            """
            <div style="background:linear-gradient(135deg,#0b2545,#1b4079);border-radius:10px;
                        padding:14px 16px;color:#fff;margin-bottom:12px">
                <div style="font-size:20px">🚨</div>
                <div style="font-weight:700;font-size:14.5px;line-height:1.25;margin-top:4px">
                    NPF Enugu Command
                </div>
                <div style="font-size:11.5px;color:#b8c7dc;margin-top:3px">
                    Emergency Response &amp; SOS Tracking
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        role_label = auth.ROLE_LABELS.get(user.get("role", ""), user.get("role", ""))
        badge_colour = "#2e7d32" if is_admin else "#1b4079"
        st.markdown(
            f"""
            <div style="border:1px solid #dde3ea;border-radius:10px;padding:10px 13px;
                        margin-bottom:12px;background:#ffffff">
                <div style="font-size:13px;font-weight:700;color:#102027">
                    👮 {html_lib.escape(str(user.get('username','')))}</div>
                <div style="margin-top:5px">
                    <span style="background:{badge_colour};color:#fff;font-size:10.5px;
                                 font-weight:700;padding:2px 9px;border-radius:9px;
                                 letter-spacing:.5px">{html_lib.escape(str(role_label).upper())}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        pages = [p for p in PAGE_REGISTRY if not (p in ADMIN_ONLY_PAGES and not is_admin)]

        # A pending programmatic navigation request must be applied BEFORE the
        # radio is created, otherwise Streamlit refuses to overwrite its state.
        pending = st.session_state.pop("_nav_request", None)
        if pending and pending in pages:
            st.session_state.pop("nav_radio", None)  # clear widget state so index applies
            st.session_state["page"] = pending

        if "page" not in st.session_state or st.session_state["page"] not in pages:
            # Either a fresh session or a page that this role may not open
            # (for example a Viewer inheriting the previous Admin's selection).
            st.session_state["page"] = pages[0]
            st.session_state.pop("nav_radio", None)

        st.caption("NAVIGATION")
        selected = st.radio(
            "Navigation", pages,
            index=pages.index(st.session_state["page"]),
            label_visibility="collapsed", key="nav_radio",
        )
        st.session_state["page"] = selected

        st.divider()

        # ---- live counters in the sidebar --------------------------------
        try:
            active = db.fetch_scalar(
                "SELECT COUNT(*) FROM sos_alerts WHERE status = 'Active'", default=0
            )
            available = db.fetch_scalar(
                "SELECT COUNT(*) FROM patrol_units WHERE status = 'Available'", default=0
            )
            st.markdown(
                f"""
                <div style="font-size:12.5px;color:#37474f;line-height:1.9">
                    <span style="color:#c62828;font-weight:700">● {int(active)}</span> active SOS alert(s)<br>
                    <span style="color:#2e7d32;font-weight:700">● {int(available)}</span> unit(s) available
                </div>
                """,
                unsafe_allow_html=True,
            )
        except db.DatabaseError:
            st.caption("Counters unavailable.")

        st.divider()
        if st.session_state.get("focus_alert_id"):
            st.caption(f"🎯 Focused incident: SOS-{int(st.session_state['focus_alert_id']):05d}")
            if st.button("Clear focus", **FULL_WIDTH):
                st.session_state["focus_alert_id"] = None
                st.rerun()

        if st.button("🚪 Sign out", **FULL_WIDTH):
            db.log_activity("LOGOUT", f"{user.get('username','')} signed out",
                            actor=str(user.get("username", "system")))
            auth.logout_user()
            # The login page does not render the navigation radio, so Streamlit
            # discards that widget's state automatically on the next run.
            st.session_state["page"] = None
            st.rerun()

        st.markdown(
            f"<div style='font-size:10.5px;color:#90a4ae;margin-top:10px'>"
            f"Version {APP_VERSION} · SQLite + Streamlit + Folium</div>",
            unsafe_allow_html=True,
        )

    return selected


def ensure_database() -> bool:
    """
    Guarantee that the database exists before the UI is drawn.

    If ``data/sos_emergency.db`` is missing (for example on a fresh clone or on
    Streamlit Community Cloud), the schema is created and seeded automatically
    so the demonstration never fails to start.

    The same function is used by BOTH modes, which is what guarantees that the
    citizen app and the police dashboard are reading and writing one shared
    database file.
    """
    try:
        if not db.database_exists():
            import setup_db

            setup_db.create_tables()
            setup_db.seed_users()
            setup_db.seed_stations()
            setup_db.seed_patrol_units()
            setup_db.seed_alerts()
            setup_db.seed_activity_log()
        return True
    except Exception as exc:  # noqa: BLE001 - report and continue
        st.error(
            "⛔ The SOS database could not be initialised.\n\n"
            f"Reason: {exc}\n\n"
            "Run `python setup_db.py` from the project folder, then reload this page."
        )
        return False


def render_police_shell() -> None:
    """
    MODE 2 shell: sign-in gate, sidebar, alarm monitor and the selected page.

    The alarm monitor is deliberately drawn BEFORE the page body so that the
    ringing alarm, the flashing border and the "NEW EMERGENCY" banner appear at
    the top of whichever page the officer happens to be on.
    """
    if not auth.is_authenticated():
        render_login()
        return

    flush_toasts()
    selected_page = render_sidebar()

    # --- the live alarm watch (re-runs every ALARM_REFRESH_SECONDS) ---------
    _alarm_monitor()

    try:
        PAGE_REGISTRY[selected_page]()
    except db.DatabaseError as exc:
        st.error(f"⛔ Database error on this page. {exc}")
        st.caption("If the problem persists, run `python setup_db.py --reset` to rebuild the demo database.")
    except Exception as exc:  # noqa: BLE001 - keep the dashboard alive
        st.error(f"⛔ An unexpected error occurred while rendering '{selected_page}'.")
        with st.expander("Technical details (for troubleshooting)"):
            import traceback

            st.code(traceback.format_exc(), language="text")
        st.caption(f"Error summary: {exc}")

    st.markdown(
        f"""
        <div style="text-align:center;color:#90a4ae;font-size:11.5px;margin-top:26px;
                    border-top:1px solid #eceff1;padding-top:12px">
            {html_lib.escape(COMMAND_NAME)} · {html_lib.escape(APP_NAME)} · v{APP_VERSION}<br>
            Demonstration prototype — all records are sample data.
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """
    Application entry point - dispatches to one of the TWO modes.

        MODE 1  Citizen SOS App     (no login, mobile-shaped panic button)
        MODE 2  Police Command      (login required, live alarm + all dashboards)

    Both run from this single script and share one SQLite database file.
    """
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    if not ensure_database():
        return

    # Sound files are synthesised once, on first run, with no internet needed.
    try:
        sounds.ensure_sounds()
    except Exception:  # noqa: BLE001 - sound must never block the application
        pass

    # ---------------- MODE SWITCHER (visible before login) -----------------
    mode = render_mode_switcher()
    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    if mode == MODE_CITIZEN:
        # ---------------- MODE 1: CITIZEN SOS (no login) -------------------
        try:
            render_citizen_app()
        except db.DatabaseError as exc:
            st.error(f"⛔ The SOS could not be processed. {exc}")
            st.caption("Please try again, or call the Command on 112.")
        except Exception as exc:  # noqa: BLE001
            st.error("⛔ An unexpected error occurred.")
            with st.expander("Technical details (for troubleshooting)"):
                import traceback

                st.code(traceback.format_exc(), language="text")
            st.caption(f"Error summary: {exc}")
        return

    # ---------------- MODE 2: POLICE COMMAND (login required) --------------
    render_police_shell()


if __name__ == "__main__":
    main()
