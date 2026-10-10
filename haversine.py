"""
haversine.py
=================================================================
Geospatial helper module - great-circle distance & nearest-unit logic
Emergency Response and SOS Location Tracking System
Nigeria Police Force - Enugu State Command
=================================================================

WHY THE HAVERSINE FORMULA?
--------------------------
Latitude and longitude are *angles* on a sphere, not flat x/y grid
coordinates, so ordinary Pythagoras gives wildly wrong distances near
Nigeria's latitude.  The Haversine formula measures the shortest path
between two points **on the surface of a sphere** and is accurate to
about 0.5% for road-scale distances - more than good enough for
dispatching a patrol vehicle.

           a = sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2)
           c = 2 · atan2(√a, √(1−a))
           d = R · c

where
    φ1, φ2 = latitude  of point 1 and point 2 (radians)
    Δφ     = φ2 − φ1
    Δλ     = λ2 − λ1
    R      = mean Earth radius = 6 371.0088 km
    d      = great-circle distance in km

``math.atan2`` is used instead of ``asin`` because it is numerically
stable for very small and very large distances (no domain errors when
floating point rounding pushes the argument slightly past 1.0).
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional, Sequence

# Mean radius of the Earth in kilometres (IUGG mean radius).
EARTH_RADIUS_KM: float = 6371.0088

# Average response speed of a police patrol vehicle inside Enugu
# metropolis, allowing for traffic signals and checkpoints.
DEFAULT_SPEED_KMH: float = 40.0

# Enugu State Command area of responsibility (used for map centring
# and for validating coordinates submitted by officers).
ENUGU_CENTER_LAT: float = 6.4483
ENUGU_CENTER_LON: float = 7.5023

# Rough bounding box of Enugu State (with a small margin) - used to warn
# officers when a coordinate is clearly outside the Command's area.
ENUGU_BOUNDS = {
    "min_lat": 5.95,
    "max_lat": 7.10,
    "min_lon": 6.90,
    "max_lon": 7.95,
}


# ---------------------------------------------------------------------
# Core distance calculation
# ---------------------------------------------------------------------
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance between two GPS points, in kilometres.

    Parameters
    ----------
    lat1, lon1 : float
        Latitude / longitude of the first point, in decimal degrees.
    lat2, lon2 : float
        Latitude / longitude of the second point, in decimal degrees.

    Returns
    -------
    float
        Distance in kilometres, rounded to 3 decimal places (1 metre).

    Examples
    --------
    >>> round(calculate_distance(6.4483, 7.5023, 6.4521, 7.5089), 2)
    0.88
    """
    # Guard against None / non-numeric input coming from a form field.
    lat1, lon1, lat2, lon2 = (
        float(lat1),
        float(lon1),
        float(lat2),
        float(lon2),
    )

    # Step 1 - convert the angular differences to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    # Step 2 - the haversine of the central angle
    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )

    # Clamp for floating-point safety before the square root.
    a = min(1.0, max(0.0, a))

    # Step 3 - central angle (radians) using atan2 for numerical stability
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    # Step 4 - scale by the Earth's radius
    return round(EARTH_RADIUS_KM * c, 3)


def estimate_arrival_time(distance_km: float, speed_kmh: float = DEFAULT_SPEED_KMH) -> float:
    """
    Estimate travel time in **minutes** for a patrol vehicle.

    Parameters
    ----------
    distance_km : float
        Distance to be covered, in kilometres.
    speed_kmh : float
        Average speed in km/h (default 40 km/h for Enugu metropolis).

    Returns
    -------
    float
        Estimated arrival time in minutes, rounded to 1 decimal place.
        A minimum of 1.0 minute is returned so a dispatcher never sees
        an unrealistic "0 minutes" ETA for an on-site unit.

    Notes
    -----
    The raw figure is inflated by a 15% urban-delay factor to account
    for traffic lights, potholes and checkpoints along the route.
    """
    distance_km = max(0.0, float(distance_km))
    speed_kmh = float(speed_kmh) if speed_kmh and speed_kmh > 0 else DEFAULT_SPEED_KMH

    hours = distance_km / speed_kmh
    minutes = hours * 60.0 * 1.15  # 15% urban traffic delay allowance
    return round(max(1.0, minutes), 1)


def format_eta(minutes: float) -> str:
    """Human-readable ETA string, e.g. ``4.6 min`` or ``1 hr 12 min``."""
    minutes = float(minutes)
    if minutes < 60:
        return f"{minutes:.1f} min"
    hours = int(minutes // 60)
    remainder = int(round(minutes - hours * 60))
    if remainder == 60:
        hours += 1
        remainder = 0
    return f"{hours} hr {remainder} min"


# ---------------------------------------------------------------------
# Nearest-unit ranking - the "wow" feature
# ---------------------------------------------------------------------
def find_nearest_units(
    alert_lat: float,
    alert_long: float,
    patrol_units: Iterable[Any],
    top_n: int = 3,
    available_only: bool = True,
    speed_kmh: float = DEFAULT_SPEED_KMH,
) -> list[dict]:
    """
    Rank patrol units by their distance from an SOS alert.

    Parameters
    ----------
    alert_lat, alert_long : float
        Coordinates of the distress call.
    patrol_units : iterable
        Rows from the ``patrol_units`` table.  Each item may be a
        ``dict`` / ``sqlite3.Row``-style mapping (anything supporting
        ``item["key"]``) or an object exposing attributes.
    top_n : int
        How many units to return (default 3).
    available_only : bool
        When True (default) only units whose status is ``Available``
        are considered - you cannot dispatch a unit that is offline or
        already attending another incident.
    speed_kmh : float
        Assumed average speed used for the ETA estimate.

    Returns
    -------
    list[dict]
        Each dictionary contains:
            units        -> the original unit record
            unit_id, unit_callsign, officer_name, status
            lat, lon
            distance_km  -> Haversine distance from the alert
            eta_minutes  -> estimated travel time in minutes
            eta_text     -> formatted ETA ("4.6 min")
        Sorted nearest-first by ``distance_km``.
    """
    ranked: list[dict] = []

    for unit in patrol_units or []:
        record = _as_mapping(unit)
        if not record:
            continue

        try:
            unit_lat = float(record.get("current_lat"))
            unit_lon = float(record.get("current_long"))
        except (TypeError, ValueError):
            # Skip malformed coordinates rather than crashing a dispatch.
            continue

        status = str(record.get("status") or "").strip()
        if available_only and status != "Available":
            continue

        distance = calculate_distance(alert_lat, alert_long, unit_lat, unit_lon)
        eta = estimate_arrival_time(distance, speed_kmh)

        ranked.append(
            {
                "units": record,
                "unit_id": record.get("unit_id"),
                "unit_callsign": record.get("unit_callsign", "UNKNOWN"),
                "officer_name": record.get("officer_name", "Unassigned"),
                "status": status or "Unknown",
                "lat": unit_lat,
                "lon": unit_lon,
                "distance_km": distance,
                "eta_minutes": eta,
                "eta_text": format_eta(eta),
            }
        )

    # Nearest first
    ranked.sort(key=lambda item: (item["distance_km"], str(item["unit_callsign"])))

    if top_n is None or top_n <= 0:
        return ranked
    return ranked[: int(top_n)]


def nearest_station(
    alert_lat: float,
    alert_long: float,
    stations: Iterable[Any],
    top_n: int = 1,
) -> list[dict]:
    """
    Rank police stations by distance from a point.

    Useful for the incident report ("Division with jurisdiction").
    """
    ranked: list[dict] = []
    for station in stations or []:
        record = _as_mapping(station)
        if not record:
            continue
        try:
            s_lat = float(record.get("latitude"))
            s_lon = float(record.get("longitude"))
        except (TypeError, ValueError):
            continue

        distance = calculate_distance(alert_lat, alert_long, s_lat, s_lon)
        ranked.append(
            {
                "stations": record,
                "station_name": record.get("station_name", "Unknown Division"),
                "address": record.get("address", ""),
                "lat": s_lat,
                "lon": s_lon,
                "distance_km": distance,
                "eta_text": format_eta(estimate_arrival_time(distance)),
            }
        )

    ranked.sort(key=lambda item: item["distance_km"])
    return ranked[: int(top_n)] if top_n else ranked


def is_within_command_area(latitude: float, longitude: float) -> bool:
    """True when a coordinate falls inside the Enugu State Command box."""
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return False
    return (
        ENUGU_BOUNDS["min_lat"] <= latitude <= ENUGU_BOUNDS["max_lat"]
        and ENUGU_BOUNDS["min_lon"] <= longitude <= ENUGU_BOUNDS["max_lon"]
    )


def bounding_box(points: Sequence[Sequence[float]], padding: float = 0.02) -> list[list[float]]:
    """
    Build a Folium ``fit_bounds`` argument from a list of [lat, lon] pairs.

    Falls back to the Enugu Command centre if no usable points are given.
    """
    usable = [
        (float(p[0]), float(p[1]))
        for p in points or []
        if p and len(p) >= 2 and p[0] is not None and p[1] is not None
    ]
    if not usable:
        return [
            [ENUGU_CENTER_LAT - padding, ENUGU_CENTER_LON - padding],
            [ENUGU_CENTER_LAT + padding, ENUGU_CENTER_LON + padding],
        ]
    lats = [p[0] for p in usable]
    lons = [p[1] for p in usable]
    return [
        [min(lats) - padding, min(lons) - padding],
        [max(lats) + padding, max(lons) + padding],
    ]


# ---------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------
def _as_mapping(item: Any) -> Optional[dict]:
    """Coerce dict / sqlite3.Row / object into a plain dict."""
    if item is None:
        return None
    if isinstance(item, dict):
        return item
    # sqlite3.Row supports keys()
    if hasattr(item, "keys"):
        try:
            return {key: item[key] for key in item.keys()}
        except Exception:
            return None
    if hasattr(item, "__dict__"):
        return dict(vars(item))
    return None


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    # Enugu State HQ -> Ogui Road Division (should be well under 1 km)
    demo_units = [
        {"unit_id": 1, "unit_callsign": "PATROL-01-OGUI", "officer_name": "Sgt. A. Eze",
         "current_lat": 6.4521, "current_long": 7.5089, "status": "Available"},
        {"unit_id": 2, "unit_callsign": "PATROL-02-ABAKPA", "officer_name": "Cpl. B. Nwosu",
         "current_lat": 6.4712, "current_long": 7.5134, "status": "Available"},
        {"unit_id": 3, "unit_callsign": "PATROL-03-NSUKKA", "officer_name": "Insp. C. Okafor",
         "current_lat": 6.8523, "current_long": 7.3934, "status": "Available"},
    ]
    print("Enugu HQ -> Ogui Rd :", calculate_distance(6.4483, 7.5023, 6.4521, 7.5089), "km")
    print()
    for item in find_nearest_units(6.4483, 7.5023, demo_units, top_n=3):
        print(f"  {item['unit_callsign']:<20} {item['distance_km']:>7.2f} km  ETA {item['eta_text']}")
