# ðŸš¨ Emergency Response and SOS Location Tracking System

### A Case Study of the Nigeria Police Force, Enugu State Command

A working, demo-ready command dashboard that receives citizen distress calls (SOS),
plots them live on an interactive map of Enugu State, and dispatches the **nearest
patrol unit** using the **Haversine great-circle distance formula**.

---

## 1. Project Folder Structure

```
sos/                                     <- project root (keep the folder name short)
â”‚
â”œâ”€â”€ app.py                     â˜… MAIN APPLICATION - the whole Streamlit dashboard
â”œâ”€â”€ setup_db.py                â˜… Creates and seeds the SQLite database
â”œâ”€â”€ setup_and_start.bat        â˜… One-click Windows launcher (env + install + run)
â”œâ”€â”€ run_server.bat               Starts the Streamlit server (called by the launcher)
â”œâ”€â”€ requirements.txt           â˜… Python dependencies
â”œâ”€â”€ README.md                    This file
â”œâ”€â”€ DEMO_DAY_SCRIPT.md         â˜… Step-by-step supervisor presentation guide
â”œâ”€â”€ DEPLOYMENT_GUIDE.md          GitHub + Streamlit Cloud deployment
â”‚
â”œâ”€â”€ auth.py                      Password hashing (hashlib/PBKDF2), login, roles
â”œâ”€â”€ db.py                        SQLite connection + query helpers
â”œâ”€â”€ haversine.py                 Distance, ETA and nearest-unit calculations
â”œâ”€â”€ reports.py                   Incident report generator (HTML / text / PDF)
â”‚
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ functional_test.py       Automated test of the logic, schema and PDF output
â”‚   â””â”€â”€ smoke_test_ui.py         Runs every page in both roles and checks for crashes
â”‚
â”œâ”€â”€ .gitignore                   Keeps venv/ and the database out of Git
â”œâ”€â”€ .streamlit/
â”‚   â””â”€â”€ config.toml              Navy/gold police theme + server settings
â”‚
â”œâ”€â”€ data/                        Created automatically by setup_db.py
â”‚   â””â”€â”€ sos_database.db          The SQLite database file
â”‚
â””â”€â”€ venv/                        Only created if no environment already exists
    â”œâ”€â”€ Scripts/python.exe
    â””â”€â”€ Lib/site-packages/...
```

> Files marked â˜… are the ones you will show your supervisor.

---

## 2. Quick Start (Windows)

### Option A â€” one click (recommended)

1. Double-click **`setup_and_start.bat`**
2. Wait while it installs packages, builds the database and starts the server
3. Your browser opens automatically at **http://localhost:8501**

The launcher picks its Python environment in this order, so it reuses what you already have:

1. a virtual environment that is already **activated** in that window
2. `..\myenv` â€” a shared environment sitting next to the project folder
3. `.\venv` â€” this project's own environment
4. otherwise it creates a fresh `.\venv` from the system Python

To wipe the demo data and start fresh:
```
setup_and_start.bat reset
```
To ignore `myenv` and build a clean local environment:
```
setup_and_start.bat fresh
```

### Option B â€” manual

```bat
cd C:\path\to\sos
C:\path\to\myenv\Scripts\activate
pip install -r requirements.txt
python setup_db.py
streamlit run app.py
```

---

## 3. Login Accounts

| Username     | Password | Role                      | Permissions                                  |
|--------------|----------|---------------------------|----------------------------------------------|
| `commander`  | `npf123` | **Admin / Commander**     | Full access â€” add, edit, delete, dispatch    |
| `dispatcher` | `npf123` | **Viewer / Dispatcher**   | Read-only â€” view, search and print reports   |

> Demonstrating both accounts is the quickest way to prove the role-based access
> control works: sign in as `dispatcher` and show that every add/edit/delete
> button has disappeared.

---

## 4. Features

### ðŸ” Login system
* Two roles: **Admin/Commander** (full) and **Viewer/Dispatcher** (read-only)
* Passwords hashed with **PBKDF2-HMAC-SHA256**, 120 000 iterations, unique random salt
* Constant-time comparison (`hmac.compare_digest`) prevents timing attacks
* Session managed with `st.session_state`

### ðŸ“Š Command dashboard
* Four KPI cards: Active SOS Alerts Â· Total Incidents Today Â· Available Patrol Units Â·
  Average Response Time
* Flashing red banner for the newest open incident
* Command overview map, recent-alert feed and control-room activity trail
* Charts: incidents by emergency type, alert status breakdown, fleet readiness

### ðŸ—ºï¸ Live SOS map (the flagship feature)
* Folium map centred on Enugu State with a street / satellite layer switch
* ðŸ”´ **Red** markers for active SOS alerts (with a pulsing emphasis ring)
* ðŸŸ  Orange for dispatched incidents Â· ðŸŸ¢ Green for available patrol units Â·
  âš« Grey for offline units Â· ðŸ”µ Blue for police divisions
* Rich popups showing citizen name, phone, status, coordinates and description
* **Auto-refreshes every 5 seconds** (toggle it off to pan freely)
* New alerts are announced with a full-width red banner

### ðŸš¨ SOS alert management (CRUD)
* Log a distress call with: citizen name, phone, latitude, longitude, emergency type
  (Armed Robbery / Kidnapping / Accident / Medical / Other), description and status
* Searchable, filterable, exportable Pandas register (CSV download)
* Update status, edit particulars, dispatch a unit, delete with confirmation
* Built-in **SOS simulator** that injects realistic distress calls at real Enugu landmarks

### ðŸš” Patrol unit management
* Register units with callsign, officer, live coordinates and status
* Fleet readiness summary and unit positions on the map
* Update position/status, delete with confirmation
* Foreign key `ON DELETE SET NULL` releases any incident the unit was attending

### ðŸ›ï¸ Police stations database
* Pre-loaded with six divisions of the Enugu State Command and their real GPS coordinates
* Distance-from-any-incident table for every division

### ðŸ§­ Nearest unit calculator (the "wow" feature)
* Select any incident â†’ instantly ranks **every** patrol unit by Haversine distance
* ðŸ¥‡ðŸ¥ˆðŸ¥‰ podium cards showing distance in km and ETA (40 km/h + 15% urban delay)
* Straight-line dispatch routes drawn on the map
* One-click dispatch of the recommended unit

### ðŸ“„ Emergency incident report generator
* Formatted **NIGERIA POLICE FORCE / ENUGU STATE COMMAND / EMERGENCY RESPONSE
  INCIDENT REPORT** document
* Download as **PDF** (generated by a built-in PDF writer â€” no paid library),
  HTML (printable) or plain text for the incident register book
* Includes incident particulars, response dispatch block, total response time,
  the division with jurisdiction and a tamper-evident authentication code

### ðŸ” Search & retrieve
* One search box covering citizen names, phone numbers, incident IDs (`SOS-00001`),
  emergency types, descriptions, patrol unit callsigns, officer names and divisions
* Organised result sections with drill-down and an inline map

---

## 5. Database Schema (SQLite)

```
users(user_id PK, username UNIQUE, password_hash, role CHECK(Admin|Viewer), created_at)

police_stations(station_id PK, station_name, latitude, longitude, address)

patrol_units(unit_id PK, unit_callsign UNIQUE, officer_name,
             current_lat, current_long, status CHECK(Available|Dispatched|Offline),
             last_updated)

sos_alerts(alert_id PK, citizen_name, phone_number, latitude, longitude,
           emergency_type CHECK(Armed Robbery|Kidnapping|Accident|Medical|Other),
           description, status CHECK(Active|Dispatched|Resolved|False Alarm),
           assigned_unit_id FK -> patrol_units(unit_id) ON DELETE SET NULL,
           created_at, resolved_at)

activity_log(log_id PK, action, details, actor, alert_id, logged_at)
```

Indexes are created on the columns used by the dashboard (`status`, `emergency_type`,
`created_at`, `citizen_name`), and `PRAGMA foreign_keys = ON` is issued on every
connection so the dispatch relationship is genuinely enforced.

---

## 6. How the Haversine Calculation Works

Latitude and longitude are angles on a sphere, not flat grid coordinates, so ordinary
Pythagoras would give badly wrong distances. The Haversine formula measures the shortest
path between two points **on the surface of the sphere**:

```
a = sinÂ²(Î”Ï†/2) + cos Ï†â‚ Â· cos Ï†â‚‚ Â· sinÂ²(Î”Î»/2)
c = 2 Â· atan2(âˆša, âˆš(1âˆ’a))
d = R Â· c                       R = 6 371.0088 km   (Earth's mean radius)

Ï†â‚, Ï†â‚‚ = latitudes of the two points (radians)
Î”Ï†     = Ï†â‚‚ âˆ’ Ï†â‚        Î”Î» = Î»â‚‚ âˆ’ Î»â‚
```

`math.atan2` is used instead of `asin` because it stays numerically stable for both very
small and very large distances. The estimated travel time is:

```
ETA (minutes) = (distance_km Ã· 40 km/h) Ã— 60 Ã— 1.15      â† 15% urban traffic allowance
```

Verified example: Enugu State HQ (6.4483, 7.5023) â†’ Ogui Road Division (6.4521, 7.5089)
= **0.843 km**, which matches Google Maps to within a few metres.

---

## 7. Automated Tests

Two self-contained test suites are included. Run them from the project root:

```bat
python tests\functional_test.py     REM logic, schema, Haversine accuracy, PDF structure
python tests\smoke_test_ui.py       REM renders every page as both roles
```

| Suite | What it proves |
|---|---|
| `tests/functional_test.py` | Tables and seed data exist Â· foreign keys enforced Â· create â†’ dispatch â†’ resolve â†’ delete lifecycle Â· `ON DELETE SET NULL` behaviour Â· UNIQUE and CHECK constraints reject bad data Â· Haversine distances match known values Â· the nearest-unit ranking is correct Â· the generated PDF has a valid header, trailer and cross-reference table |
| `tests/smoke_test_ui.py` | The login page renders Â· a wrong password is rejected Â· all nine pages render with **zero exceptions** as Admin Â· the Viewer sees no admin-only page Â· search works across names, IDs, callsigns and types |

Both suites currently pass with **0 failures**.

---

## 8. Troubleshooting

| Problem | Solution |
|---|---|
| `python` is not recognised | Install Python 3.10+ and tick **Add python.exe to PATH** |
| `pip install` fails | Check your internet connection / proxy settings |
| Dashboard shows "database could not be initialised" | Run `python setup_db.py --reset` |
| Port 8501 already in use | `setup_and_start.bat` automatically switches to 8502 |
| Map tiles do not load | The machine needs internet access for map tiles only |
| Blank page after login | Press `R` in the browser to reload the Streamlit session |

---

## 9. Technology Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.10+ | Standard for academic prototypes |
| Web UI | Streamlit | Fast, professional dashboards without HTML/JS |
| Database | SQLite (built into Python) | Zero-configuration, file-based, ACID |
| Data tables | Pandas | Filtering, aggregation, CSV export |
| Maps | Folium + streamlit-folium | Leaflet.js maps rendered straight from Python |
| Geospatial | Haversine formula (`math` only) | Accurate great-circle distance, no dependencies |
| Security | `hashlib` PBKDF2-HMAC-SHA256 | Industry-standard password hashing |
| Reporting | Built-in PDF writer (`reports.py`) | Real PDF download with no paid library |

Everything used is **free, open-source or built into Python**.

---

*Demonstration prototype â€” all records in the seeded database are sample data.
Nigeria Police Force, Enugu State Command.*
"# sos-police" 
