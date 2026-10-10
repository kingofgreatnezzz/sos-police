"""
reports.py
=================================================================
Emergency Incident Report generator
Emergency Response and SOS Location Tracking System
Nigeria Police Force - Enugu State Command
=================================================================

Produces the official "EMERGENCY RESPONSE INCIDENT REPORT" in three
formats:

    1. A structured ``dict``  -> generate_incident_report(alert_id)
    2. A print-ready HTML block -> format_report_as_html(report_data)
    3. A real PDF file (bytes)  -> generate_pdf_bytes(report_data)

The PDF writer at the bottom of this module is intentionally written
from scratch using nothing but the Python standard library, so the
system needs no ReportLab / fpdf / wkhtmltopdf installation and stays
within the "free and built-in tools only" constraint of the project.
It emits a valid PDF 1.4 document with a Helvetica font resource,
drawn borders and a proper cross-reference table.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta
from typing import Any, Optional

import db
import haversine

# ---------------------------------------------------------------------
# Command identity (printed on every report)
# ---------------------------------------------------------------------
COMMAND_NAME = "NIGERIA POLICE FORCE"
COMMAND_SUB = "ENUGU STATE COMMAND"
REPORT_TITLE = "EMERGENCY RESPONSE INCIDENT REPORT"
REPORT_TAGLINE = "Emergency Response and SOS Location Tracking System"

STATUS_COLOURS = {
    "Active": "#c62828",
    "Dispatched": "#ef6c00",
    "Resolved": "#2e7d32",
    "False Alarm": "#616161",
}


# ---------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------
def generate_incident_report(alert_id: int) -> dict:
    """
    Build the complete incident report payload for one SOS alert.

    Combines three sources:
      * the ``sos_alerts`` record,
      * the assigned (or nearest available) patrol unit,
      * the nearest police division with jurisdiction over the location.

    Returns
    -------
    dict
        Ready-to-render report data.  Raises ``ValueError`` when the
        alert does not exist, and ``db.DatabaseError`` on a SQL fault.
    """
    alert = db.fetch_one("SELECT * FROM sos_alerts WHERE alert_id = ?", (int(alert_id),))
    if not alert:
        raise ValueError(f"SOS alert #{alert_id} was not found in the register.")

    patrol_units = db.fetch_all("SELECT * FROM patrol_units ORDER BY unit_callsign")
    stations = db.fetch_all("SELECT * FROM police_stations ORDER BY station_name")

    alert_lat = float(alert["latitude"])
    alert_lon = float(alert["longitude"])

    # ---- 1. Resolve the responding unit -----------------------------
    assigned_unit: Optional[dict] = None
    assigned_unit_id = alert.get("assigned_unit_id")
    if assigned_unit_id:
        assigned_unit = next(
            (u for u in patrol_units if u.get("unit_id") == assigned_unit_id), None
        )

    # Fallback: recommend the nearest available unit (or nearest of all).
    ranked_available = haversine.find_nearest_units(
        alert_lat, alert_lon, patrol_units, top_n=1, available_only=True
    )
    ranked_all = haversine.find_nearest_units(
        alert_lat, alert_lon, patrol_units, top_n=1, available_only=False
    )

    if assigned_unit is not None:
        distance_km = haversine.calculate_distance(
            alert_lat, alert_lon,
            float(assigned_unit["current_lat"]), float(assigned_unit["current_long"]),
        )
        responding_unit = assigned_unit
        unit_source = "Assigned"
    elif ranked_available:
        responding_unit = ranked_available[0]["units"]
        distance_km = ranked_available[0]["distance_km"]
        unit_source = "Recommended (nearest available)"
    elif ranked_all:
        responding_unit = ranked_all[0]["units"]
        distance_km = ranked_all[0]["distance_km"]
        unit_source = "Nearest unit on strength (none available)"
    else:
        responding_unit = None
        distance_km = 0.0
        unit_source = "No patrol unit on strength"

    eta_minutes = haversine.estimate_arrival_time(distance_km)
    nearest_division = haversine.nearest_station(alert_lat, alert_lon, stations, top_n=1)

    # ---- 2. Build the response block ---------------------------------
    response = {
        "unit_callsign": (responding_unit or {}).get("unit_callsign", "N/A"),
        "officer_name": (responding_unit or {}).get("officer_name", "Not yet assigned"),
        "unit_status": (responding_unit or {}).get("status", "N/A"),
        "unit_source": unit_source,
        "distance_km": round(distance_km, 2),
        "eta_minutes": eta_minutes,
        "eta_text": haversine.format_eta(eta_minutes),
        "division": nearest_division[0]["station_name"] if nearest_division else "N/A",
        "division_address": nearest_division[0]["address"] if nearest_division else "",
        "division_distance_km": (
            round(nearest_division[0]["distance_km"], 2) if nearest_division else 0.0
        ),
    }

    # ---- 3. Timeline / response-time computation ---------------------
    created = _parse_ts(alert.get("created_at")) or datetime.utcnow()
    resolved = _parse_ts(alert.get("resolved_at"))

    response_minutes: Optional[float] = None
    if resolved:
        response_minutes = round((resolved - created).total_seconds() / 60.0, 1)

    return {
        # --- identification
        "alert_id": alert["alert_id"],
        "reference": f"NPF/EN/ER/{created.strftime('%Y')}/{int(alert['alert_id']):05d}",
        "generated_at": datetime.utcnow(),
        "generated_by": "Enugu State Command Control Room",
        # --- incident particulars
        "citizen_name": alert.get("citizen_name", ""),
        "phone_number": alert.get("phone_number", ""),
        "emergency_type": alert.get("emergency_type", ""),
        "description": (alert.get("description") or "No additional details supplied.").strip(),
        "latitude": alert_lat,
        "longitude": alert_lon,
        "location_text": f"{alert_lat:.6f}, {alert_lon:.6f}",
        "status": alert.get("status", "Active"),
        "created_at": created,
        "resolved_at": resolved,
        "created_at_text": _fmt_ts(created),
        "resolved_at_text": _fmt_ts(resolved) if resolved else "Not yet resolved",
        "response_minutes": response_minutes,
        "response_minutes_text": (
            f"{response_minutes:.1f} minutes" if response_minutes is not None else "Pending"
        ),
        # --- dispatch block
        "response": response,
        # --- verification
        "verification_code": _verification_code(
            alert["alert_id"], alert.get("phone_number", ""), created
        ),
    }


# ---------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------
def format_report_as_html(report_data: dict) -> str:
    """
    Render the report as a self-contained, printable HTML document.

    The returned string is a complete ``<html>`` page (inline CSS only)
    so it can be shown with ``st.markdown(..., unsafe_allow_html=True)``,
    embedded in an iframe, or downloaded and opened in any browser and
    printed to paper / PDF with Ctrl+P.
    """
    response = report_data.get("response", {})
    status = report_data.get("status", "Active")
    status_colour = STATUS_COLOURS.get(status, "#424242")
    esc = html.escape

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{esc(report_data.get('reference', 'Incident Report'))}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Segoe UI", Arial, Helvetica, sans-serif;
    background: #eceff1; margin: 0; padding: 18px; color: #1c2833;
  }}
  .sheet {{
    max-width: 820px; margin: 0 auto; background: #ffffff;
    border: 2px solid #0b2545; border-radius: 6px; overflow: hidden;
    box-shadow: 0 6px 18px rgba(0,0,0,.15);
  }}
  .letterhead {{
    background: #0b2545; color: #ffffff; padding: 16px 22px; text-align: center;
  }}
  .letterhead .force {{ font-size: 21px; font-weight: 700; letter-spacing: 2px; }}
  .letterhead .command {{ font-size: 14px; letter-spacing: 3px; color: #ffd54f; margin-top: 2px; }}
  .letterhead .doctype {{
    font-size: 15px; font-weight: 600; margin-top: 10px; padding-top: 9px;
    border-top: 1px solid rgba(255,255,255,.35); letter-spacing: 1px;
  }}
  .letterhead .tagline {{ font-size: 11px; color: #b0bec5; margin-top: 4px; }}
  .band {{
    display: flex; justify-content: space-between; align-items: center;
    background: #f5f7fa; border-bottom: 1px solid #cfd8dc; padding: 8px 22px;
    font-size: 12px; color: #37474f;
  }}
  .status-pill {{
    background: {status_colour}; color: #fff; padding: 3px 12px;
    border-radius: 11px; font-size: 11px; font-weight: 700;
    letter-spacing: .6px; text-transform: uppercase;
  }}
  .section-title {{
    background: #0b2545; color: #fff; font-size: 12px; font-weight: 700;
    letter-spacing: 1.4px; padding: 7px 22px; text-transform: uppercase;
  }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 9px 22px; font-size: 13px; vertical-align: top; border-bottom: 1px solid #eceff1; }}
  td.label {{ width: 32%; color: #546e7a; font-weight: 600; }}
  td.value {{ color: #102027; }}
  .mono {{ font-family: "Consolas", "Courier New", monospace; }}
  .desc {{ padding: 10px 22px 14px 22px; font-size: 13px; line-height: 1.55; color: #102027; }}
  .highlight {{ background: #fffde7; }}
  .footer {{
    display: flex; justify-content: space-between; padding: 12px 22px;
    border-top: 2px solid #0b2545; background: #f5f7fa; font-size: 11px; color: #455a64;
  }}
  .sig {{ margin-top: 4px; border-top: 1px dotted #90a4ae; padding-top: 3px; }}
</style>
</head>
<body>
<div class="sheet">

  <div class="letterhead">
    <div class="force">{esc(COMMAND_NAME)}</div>
    <div class="command">{esc(COMMAND_SUB)}</div>
    <div class="doctype">{esc(REPORT_TITLE)}</div>
    <div class="tagline">{esc(REPORT_TAGLINE)}</div>
  </div>

  <div class="band">
    <span><strong>Reference:</strong> <span class="mono">{esc(report_data.get('reference',''))}</span></span>
    <span class="status-pill">{esc(status)}</span>
  </div>

  <div class="section-title">Part A &mdash; Incident Particulars</div>
  <table>
    <tr>
      <td class="label">Incident ID</td>
      <td class="value mono">SOS-{int(report_data.get('alert_id', 0)):05d}</td>
      <td class="label">Date / Time Reported</td>
      <td class="value">{esc(report_data.get('created_at_text',''))}</td>
    </tr>
    <tr>
      <td class="label">Citizen Name</td>
      <td class="value">{esc(report_data.get('citizen_name',''))}</td>
      <td class="label">Telephone Number</td>
      <td class="value mono">{esc(report_data.get('phone_number',''))}</td>
    </tr>
    <tr>
      <td class="label">Emergency Type</td>
      <td class="value"><strong>{esc(report_data.get('emergency_type',''))}</strong></td>
      <td class="label">Current Status</td>
      <td class="value">{esc(status)}</td>
    </tr>
    <tr>
      <td class="label">GPS Coordinates</td>
      <td class="value mono">{esc(report_data.get('location_text',''))}</td>
      <td class="label">Time Resolved</td>
      <td class="value">{esc(report_data.get('resolved_at_text',''))}</td>
    </tr>
    <tr>
      <td class="label">Total Response Time</td>
      <td class="value" colspan="3">{esc(report_data.get('response_minutes_text',''))}</td>
    </tr>
  </table>

  <div class="section-title">Part B &mdash; Description of Distress Call</div>
  <div class="desc">{esc(report_data.get('description',''))}</div>

  <div class="section-title">Part C &mdash; Response Dispatch</div>
  <table>
    <tr class="highlight">
      <td class="label">Nearest / Responding Unit</td>
      <td class="value mono"><strong>{esc(response.get('unit_callsign','N/A'))}</strong></td>
      <td class="label">Distance from Incident</td>
      <td class="value">{response.get('distance_km', 0):.2f} km</td>
    </tr>
    <tr>
      <td class="label">Estimated Time of Arrival</td>
      <td class="value">{esc(response.get('eta_text',''))}</td>
      <td class="label">Unit Status</td>
      <td class="value">{esc(response.get('unit_status','N/A'))}</td>
    </tr>
    <tr>
      <td class="label">Responding Officer</td>
      <td class="value">{esc(response.get('officer_name','Not yet assigned'))}</td>
      <td class="label">Assignment Basis</td>
      <td class="value">{esc(response.get('unit_source',''))}</td>
    </tr>
    <tr>
      <td class="label">Division with Jurisdiction</td>
      <td class="value">{esc(response.get('division','N/A'))}</td>
      <td class="label">Distance to Division</td>
      <td class="value">{response.get('division_distance_km', 0):.2f} km</td>
    </tr>
  </table>

  <div class="footer">
    <div>
      <div>Report generated: {esc(_fmt_ts(report_data.get('generated_at')))}</div>
      <div>Issued by: {esc(report_data.get('generated_by',''))}</div>
    </div>
    <div style="text-align:right">
      <div class="mono">Auth. Code: {esc(report_data.get('verification_code',''))}</div>
      <div class="sig">Officer's Signature / Date</div>
    </div>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------
# Plain-text rendering (for copy/paste into the incident register book)
# ---------------------------------------------------------------------
def format_report_as_text(report_data: dict, width: int = 74) -> str:
    """Render the report as monospaced text matching the official layout."""
    response = report_data.get("response", {})
    line = "+" + "-" * (width - 2) + "+"

    def row(left: str, right: str = "") -> str:
        inner = f" {left}"
        if right:
            inner = f" {left:<36}{right}"
        return "|" + inner.ljust(width - 2)[: width - 2] + "|"

    def centre(text: str) -> str:
        return "|" + text.center(width - 2)[: width - 2] + "|"

    out = [
        line,
        centre(COMMAND_NAME),
        centre(COMMAND_SUB),
        centre(REPORT_TITLE),
        line,
        row(f"Incident ID: SOS-{int(report_data.get('alert_id', 0)):05d}",
            f"Date/Time: {report_data.get('created_at_text', '')}"),
        row(f"Citizen Name: {report_data.get('citizen_name', '')}",
            f"Phone: {report_data.get('phone_number', '')}"),
        row(f"Emergency Type: {report_data.get('emergency_type', '')}",
            f"Status: {report_data.get('status', '')}"),
        row(f"Location: {report_data.get('location_text', '')}"),
        row(f"Reference: {report_data.get('reference', '')}"),
        line,
        centre("DESCRIPTION"),
        line,
        row(report_data.get("description", "")[: width - 4]),
        line,
        centre("RESPONSE DISPATCH"),
        line,
        row(f"Nearest Unit: {response.get('unit_callsign', 'N/A')}",
            f"Distance: {response.get('distance_km', 0):.2f} km"),
        row(f"ETA: {response.get('eta_text', '')}",
            f"Status: {response.get('unit_status', 'N/A')}"),
        row(f"Responding Officer: {response.get('officer_name', 'N/A')}"),
        row(f"Division: {response.get('division', 'N/A')}"),
        row(f"Total Response Time: {report_data.get('response_minutes_text', 'Pending')}"),
        line,
        row(f"Generated: {_fmt_ts(report_data.get('generated_at'))}"),
        row(f"Auth. Code: {report_data.get('verification_code', '')}"),
        line,
    ]
    return "\n".join(out)


# ---------------------------------------------------------------------
# Minimal, dependency-free PDF writer
# ---------------------------------------------------------------------
PAGE_WIDTH = 595.0     # A4 width  in points (72 dpi)
PAGE_HEIGHT = 842.0    # A4 height in points
MARGIN = 46.0

NAVY = (0.043, 0.145, 0.271)
GOLD = (1.0, 0.835, 0.310)
GREY = (0.35, 0.40, 0.44)
LIGHT = (0.90, 0.92, 0.94)


class _PDFPage:
    """Accumulates PDF content-stream operators for a single page."""

    def __init__(self) -> None:
        self.ops: list[str] = []
        self.y: float = PAGE_HEIGHT - MARGIN

    # -- primitives ---------------------------------------------------
    def text(self, x: float, y: float, size: float, font: str, value: str) -> None:
        self.ops.append(
            f"BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ({_pdf_escape(value)}) Tj ET"
        )

    def rect(self, x: float, y: float, w: float, h: float,
             stroke: Optional[tuple] = None, fill: Optional[tuple] = None,
             line_width: float = 0.8) -> None:
        if fill:
            self.ops.append(f"{fill[0]:.3f} {fill[1]:.3f} {fill[2]:.3f} rg")
        if stroke:
            self.ops.append(f"{stroke[0]:.3f} {stroke[1]:.3f} {stroke[2]:.3f} RG")
            self.ops.append(f"{line_width:.2f} w")
        self.ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill and stroke:
            self.ops.append("B")
        elif fill:
            self.ops.append("f")
        else:
            self.ops.append("S")

    def hline(self, x1: float, x2: float, y: float,
              colour: tuple = GREY, width: float = 0.6) -> None:
        self.ops.append(f"{colour[0]:.3f} {colour[1]:.3f} {colour[2]:.3f} RG {width:.2f} w")
        self.ops.append(f"{x1:.2f} {y:.2f} m {x2:.2f} {y:.2f} l S")

    def data(self) -> bytes:
        return ("\n".join(self.ops) + "\n").encode("latin-1", "replace")


def generate_pdf_bytes(report_data: dict) -> bytes:
    """
    Produce a genuine PDF file (as ``bytes``) for one incident report.

    Suitable for ``st.download_button(data=..., mime="application/pdf")``.
    """
    page = _PDFPage()
    left = MARGIN
    right = PAGE_WIDTH - MARGIN
    usable = right - left

    response = report_data.get("response", {})

    # ---------------- letterhead -------------------------------------
    band_height = 74.0
    band_top = PAGE_HEIGHT - MARGIN
    page.rect(left, band_top - band_height, usable, band_height, fill=NAVY)

    _centred(page, PAGE_HEIGHT - MARGIN - 24, 19, "F2", COMMAND_NAME, bold=True)
    _centred(page, PAGE_HEIGHT - MARGIN - 40, 11.5, "F2", COMMAND_SUB, bold=True, colour=GOLD)
    _centred(page, PAGE_HEIGHT - MARGIN - 57, 12.5, "F2", REPORT_TITLE, bold=True)
    _centred(page, PAGE_HEIGHT - MARGIN - 70, 8.5, "F1", REPORT_TAGLINE, colour=LIGHT)

    y = band_top - band_height - 18

    # ---------------- reference / status row -------------------------
    page.text(left, y, 9, "F1", "Reference:")
    page.text(left + 52, y, 9, "F3", str(report_data.get("reference", "")))
    status = str(report_data.get("status", "Active")).upper()
    status_text = f"STATUS: {status}"
    page.text(right - _text_width(status_text, 9, bold=True) - 8, y, 9, "F2", status_text)
    y -= 16
    page.hline(left, right, y, NAVY, 1.1)

    # ---------------- Part A ----------------------------------------
    y = _section(page, "PART A  -  INCIDENT PARTICULARS", left, usable, y - 12)

    rows_a = [
        ("Incident ID", f"SOS-{int(report_data.get('alert_id', 0)):05d}",
         "Date/Time Reported", _fmt_ts(report_data.get("created_at"))),
        ("Citizen Name", str(report_data.get("citizen_name", "")),
         "Telephone Number", str(report_data.get("phone_number", ""))),
        ("Emergency Type", str(report_data.get("emergency_type", "")),
         "Current Status", str(report_data.get("status", ""))),
        ("GPS Coordinates", str(report_data.get("location_text", "")),
         "Time Resolved", str(report_data.get("resolved_at_text", ""))),
        ("Total Response Time", str(report_data.get("response_minutes_text", "Pending")), "", ""),
    ]
    for label_l, value_l, label_r, value_r in rows_a:
        y = _field_row(page, left, right, y, label_l, value_l, label_r, value_r)
    page.hline(left, right, y, LIGHT, 0.7)
    y -= 8

    # ---------------- Part B ----------------------------------------
    y = _section(page, "PART B  -  DESCRIPTION OF DISTRESS CALL", left, usable, y - 6)
    description = str(report_data.get("description", "")) or "No additional details supplied."
    for chunk in _wrap(description, 96)[:6]:
        y -= 12.5
        page.text(left + 6, y, 9.5, "F1", chunk)
    y -= 8
    page.hline(left, right, y, LIGHT, 0.7)
    y -= 8

    # ---------------- Part C ----------------------------------------
    y = _section(page, "PART C  -  RESPONSE DISPATCH", left, usable, y - 6)
    rows_c = [
        ("Nearest / Responding Unit", str(response.get("unit_callsign", "N/A")),
         "Distance from Incident", f"{response.get('distance_km', 0):.2f} km"),
        ("Estimated Time of Arrival", str(response.get("eta_text", "")),
         "Unit Status", str(response.get("unit_status", "N/A"))),
        ("Responding Officer", str(response.get("officer_name", "Not yet assigned")),
         "Assignment Basis", str(response.get("unit_source", ""))),
        ("Division with Jurisdiction", str(response.get("division", "N/A")),
         "Distance to Division", f"{response.get('division_distance_km', 0):.2f} km"),
    ]
    for label_l, value_l, label_r, value_r in rows_c:
        y = _field_row(page, left, right, y, label_l, value_l, label_r, value_r)
    page.hline(left, right, y, LIGHT, 0.7)

    # ---------------- footer ----------------------------------------
    footer_y = MARGIN + 62
    page.hline(left, right, footer_y + 44, NAVY, 1.2)
    page.text(left, footer_y + 28, 8.5, "F1",
              f"Report generated: {_fmt_ts(report_data.get('generated_at'))}")
    page.text(left, footer_y + 16, 8.5, "F1",
              f"Issued by: {report_data.get('generated_by', '')}")
    page.text(left, footer_y + 4, 8.5, "F3",
              f"Authentication code: {report_data.get('verification_code', '')}")
    page.text(right - 150, footer_y + 4, 8.5, "F1",
              "Officer's Signature / Date")
    page.hline(right - 152, right, footer_y + 16, GREY, 0.5)

    return _build_pdf([page.data()])


def _section(page: _PDFPage, title: str, left: float, usable: float, y: float) -> float:
    """Draw a navy section heading bar and return the new cursor Y."""
    bar_height = 17.0
    page.rect(left, y - bar_height + 4, usable, bar_height, fill=NAVY)
    page.text(left + 7, y - bar_height + 9, 9.5, "F2", title)
    return y - bar_height - 2


def _field_row(page: _PDFPage, left: float, right: float, y: float,
               label_l: str, value_l: str, label_r: str, value_r: str) -> float:
    """Draw a two-column label/value row and return the new cursor Y."""
    col_split = left + (right - left) * 0.5
    y -= 15
    page.text(left + 6, y, 8.5, "F1", label_l)
    page.text(left + 6, y - 11, 9.5, "F2", str(value_l)[:52])
    if label_r:
        page.text(col_split + 6, y, 8.5, "F1", label_r)
        page.text(col_split + 6, y - 11, 9.5, "F2", str(value_r)[:52])
    return y - 16


def _centred(page: _PDFPage, y: float, size: float, font: str, value: str,
             bold: bool = False, colour: Optional[tuple] = None) -> None:
    width = _text_width(value, size, bold)
    x = (PAGE_WIDTH - width) / 2.0
    if colour:
        page.ops.append(f"{colour[0]:.3f} {colour[1]:.3f} {colour[2]:.3f} rg")
    page.text(x, y, size, font, value)
    page.ops.append("0.043 0.145 0.271 rg")


# Approximate Helvetica glyph widths as a fraction of the font size.
# Good enough for centring and truncating display strings.
def _text_width(value: str, size: float, bold: bool = False) -> float:
    factor = 0.556 if bold else 0.512
    return len(str(value)) * size * factor


def _wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word-wrap producing lines of at most ``max_chars``."""
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= max_chars:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _pdf_escape(value: str) -> str:
    """Escape a string for a PDF literal string object (ASCII only)."""
    text = str(value).encode("latin-1", "replace").decode("latin-1")
    text = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in text)


def _build_pdf(pages_content: list[bytes]) -> bytes:
    """
    Assemble content streams into a valid single/multi-page PDF document.

    Object numbering:
        1 -> Catalog
        2 -> Pages tree
        3 -> Font Helvetica (F1)
        4 -> Font Helvetica-Bold (F2)
        5 -> Font Courier (F3)
        6,8,10... -> Page objects
        7,9,11... -> Content streams
    """
    objects: list[bytes] = []
    n_pages = max(1, len(pages_content))
    first_page_obj = 6
    kids = " ".join(f"{first_page_obj + 2 * i} 0 R" for i in range(n_pages))

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("ascii"))
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>"
    )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>"
    )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier "
        b"/Encoding /WinAnsiEncoding >>"
    )

    for index, content in enumerate(pages_content):
        page_obj = first_page_obj + 2 * index
        content_obj = page_obj + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH:.0f} {PAGE_HEIGHT:.0f}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
            + content + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_position = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def generate_incident_pdf(alert_id: int) -> tuple[bytes, str]:
    """
    Convenience wrapper: build the report for ``alert_id`` and return
    ``(pdf_bytes, suggested_filename)`` - ready for st.download_button.
    """
    report = generate_incident_report(alert_id)
    pdf = generate_pdf_bytes(report)
    filename = f"NPF_Enugu_Incident_Report_SOS-{int(alert_id):05d}.pdf"
    return pdf, filename


# ---------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------
def _parse_ts(value: Any) -> Optional[datetime]:
    """Parse the SQLite timestamp formats into a ``datetime``."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _fmt_ts(value: Any) -> str:
    """
    Format a stored UTC timestamp for display in West Africa Time (UTC+1)
    as ``01 Jan 2025, 14:32 WAT``.
    """
    stamp = _parse_ts(value)
    if stamp is None:
        return "N/A"
    wat = stamp + timedelta(hours=1)
    return wat.strftime("%d %b %Y, %H:%M WAT")


def _verification_code(alert_id: Any, phone: str, created: datetime) -> str:
    """Deterministic authentication code printed on the report."""
    import hashlib

    seed = f"{alert_id}|{phone}|{created.strftime('%Y%m%d%H%M%S')}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()
    return f"{digest[:4]}-{digest[4:8]}-{digest[8:12]}"


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    try:
        data = generate_incident_report(1)
    except Exception as exc:  # noqa: BLE001
        print("Run setup_db.py first:", exc)
    else:
        print(format_report_as_text(data))
        pdf_bytes = generate_pdf_bytes(data)
        print(f"\nPDF generated: {len(pdf_bytes)} bytes, header={pdf_bytes[:8]!r}")
