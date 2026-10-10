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
import random
from datetime import datetime, timedelta

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

import auth
import db
import haversine
import reports

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

MAP_REFRESH_SECONDS = 5
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
# 16. NAVIGATION & APPLICATION ENTRY POINT
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

    If ``data/sos_database.db`` is missing (for example on a fresh clone
    or on Streamlit Community Cloud), the schema is created and seeded
    automatically so the demonstration never fails to start.
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


def main() -> None:
    """Application entry point."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    if not ensure_database():
        return

    # ---------------- authentication gate ---------------------------------
    if not auth.is_authenticated():
        render_login()
        return

    # ---------------- authenticated shell ---------------------------------
    flush_toasts()
    selected_page = render_sidebar()

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


if __name__ == "__main__":
    main()
