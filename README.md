# 🚨 Emergency Response and SOS Location Tracking System

### A Case Study of the Nigeria Police Force, Enugu State Command

A working, demo-ready system with **TWO modes running from one codebase and one
database**:

| | Mode | Who uses it | Login |
|---|---|---|---|
| **1** | **🚨 Citizen SOS App** | A citizen in distress, on a phone | **None required** |
| **2** | **👮 Police Command** | The Enugu State Command control room | `commander / npf123` |

The citizen presses one big red button → the police dashboard **rings an alarm within
3 seconds**, drops a pin on the map, and has already calculated the **nearest patrol
unit** using the **Haversine great-circle distance formula**.

---

## 1. Project Folder Structure

```
sos/                                     <- project root (keep the folder name short)
│
├── app.py                     ★ THE WHOLE APPLICATION - both modes live here
├── setup_db.py                ★ Creates and seeds the SQLite database
├── setup_and_start.bat        ★ One-click Windows launcher (env + install + run)
├── run_server.bat               Starts the one server (called by the launcher)
├── requirements.txt           ★ Python dependencies
├── README.md                    This file
├── DEMO_SCRIPT.txt            ★ Defence-day runbook (step by step - print it)
├── DEMO_DAY_SCRIPT.md           Longer presentation guide with Q&A preparation
├── DEPLOYMENT_GUIDE.md          GitHub + Streamlit Cloud deployment
│
├── auth.py                      Password hashing (hashlib/PBKDF2), login, roles
├── db.py                        SQLite connection, WAL, safe concurrent writes
├── haversine.py                 Distance, ETA and nearest-unit calculations
├── reports.py                   Incident report generator (HTML / text / PDF)
├── sounds.py                  ★ Generates the alarm and confirmation WAV files
│
├── tests/
│   ├── functional_test.py       Logic, schema, Haversine accuracy, PDF, concurrency
│   ├── smoke_test_ui.py         Renders every page in both roles
│   └── two_mode_test.py       ★ The full citizen → police → dispatch demonstration
│
├── assets/sounds/               Created on first run by sounds.py (no internet)
│   ├── sos_beep.wav             Citizen confirmation chime (0.8 s)
│   └── sos_alarm.wav            Police ringing alarm (6.3 s, looped)
│
├── .gitignore                   Keeps venv/ and the database out of Git
├── .streamlit/
│   └── config.toml              Navy/gold police theme + server settings
│
├── data/                        Created automatically by setup_db.py
│   └── sos_emergency.db       ★ THE SHARED DATABASE - both modes read/write this
│
└── venv/                        Only created if no environment already exists
    ├── Scripts/python.exe
    └── Lib/site-packages/...
```

> Files marked ★ are the ones you will show your supervisor.

---

## 2. The Two Modes

### 🚨 MODE 1 — Citizen SOS App  (no login)

Opened with **`?mode=citizen`** — a mobile-shaped page built around one rule:
**press first, details later.**

* **A huge red pulsing SOS button** — and it is the ONLY thing required.
  It works with the form completely blank
* **Three optional one-tap categories** (not a five-item form):
  🔫 Robbery / Theft · 🥊 Fight / Attack · 🚑 Health Emergency — tapping the
  selected one again clears it, and skipping them entirely is fine
* Name, phone number, location controls and a description sit **below** the
  button, marked optional, so nothing delays the alarm
* Three ways to set the location:
  1. **📡 Detect My GPS Location** — reads the phone's real GPS through
     `navigator.geolocation`, then hands the coordinates back to Python through
     the URL query string
  2. **📍 Use Simulated Enugu Location** — instantly sets Ogui Road
     (6.452100, 7.508900) so a demonstration always works
  3. Manual coordinate entry
* Pressing the button **inserts a row into `sos_alerts` with status `Active`**,
  shows **"🚨 SOS SENT! Help is on the way. Stay calm."**, and plays a
  **confirmation chime**
* Missing details are recorded honestly — `Unknown caller` and `Not provided` —
  never invented
* An **8-second debounce** ignores a double-tap so one panicking caller cannot
  raise two incidents
* After sending, optional fields let the caller **add their name and number to
  the same incident** if they are able to
* A **live tracking screen** then follows the alert from *Active → Dispatched*,
  showing which unit is coming, its distance and its ETA

### 👮 MODE 2 — Police Command Dashboard  (login required)

Opened with **`?mode=police`**. Everything in the original dashboard, plus:

* **Auto-refresh every 3 seconds**, polling the database for new citizen alerts
* **A loud ringing alarm** that plays automatically — a telephone-style ring, looped
  until it is acknowledged
* **A flashing red border** around the whole dashboard
* **A "🚨 NEW EMERGENCY!" banner** showing the citizen's name, phone number,
  emergency type, exact GPS coordinates and the time received
* **The three nearest patrol units, already ranked** with distance in km and ETA
* **🔔 Silence Alarm** — stops the ringing but keeps the incident on screen
* **📲 Mark as Dispatched** — sends the nearest unit, changes the status and stops the
  alarm in one click
* **🎭 DEMO MODE** — injects a simulated incoming SOS as a backup if the live phone
  demonstration fails

### How the two modes stay in step

```
  CITIZEN (phone)                 ONE SERVER                 POLICE (control room)
  ───────────────                 ───────────                ─────────────────────
  Press SOS  ──INSERT──►  data/sos_emergency.db  ◄──SELECT─── poll every 3 s
                          (SQLite, WAL mode)                ├─ new row? RING + FLASH
                                                            ├─ show banner
  Tracking  ◄──SELECT────  same table          ◄──UPDATE──── └─ rank nearest units
  screen      every 3 s                          Mark Dispatched
```

Both modes are served by **one `streamlit run app.py` process**. The database is
SQLite in **WAL mode** with a busy timeout and automatic retries, so the citizen's
insert and the police poll cannot lock each other out.

---

## 2. Quick Start (Windows)

### Option A — one click (recommended)

1. Double-click **`setup_and_start.bat`**
2. Wait while it installs packages, builds the database and starts the server
3. Your browser opens automatically at **http://localhost:8501**

The launcher picks its Python environment in this order, so it reuses what you already have:

1. a virtual environment that is already **activated** in that window
2. `..\myenv` — a shared environment sitting next to the project folder
3. `.\venv` — this project's own environment
4. otherwise it creates a fresh `.\venv` from the system Python

To wipe the demo data and start fresh:
```
setup_and_start.bat reset
```
To ignore `myenv` and build a clean local environment:
```
setup_and_start.bat fresh
```

### Option B — manual

```bat
cd C:\path\to\sos
C:\path\to\myenv\Scripts\activate
pip install -r requirements.txt
python setup_db.py
python sounds.py          REM generates the alarm + chime (optional, done automatically)
streamlit run app.py
```

Then open both modes:

```
Police Command  :  http://localhost:8501/?mode=police
Citizen SOS     :  http://localhost:8501/?mode=citizen
On a phone      :  http://<laptop-LAN-IP>:8501/?mode=citizen
```

### Running both modes at the same time

The demonstration needs two clients viewing the **same server**:

| Option | How |
|---|---|
| **Two browser tabs** (recommended, always works) | Open `?mode=police` in Tab 1 and `?mode=citizen` in Tab 2. Each tab remembers its own mode. |
| **Laptop + phone** (most impressive) | Run the laptop as normal, then open `http://<LAN-IP>:8501/?mode=citizen` on the handset. Both devices must be on the same Wi-Fi. The launcher prints this URL for you. |
| **Two browser windows side by side** | Drag one window to each half of the screen so the panel can see both at once. |

> **Windows Firewall:** if the phone cannot connect, allow Python through it, or run
> once in an Administrator Command Prompt:
> ```
> netsh advfirewall firewall add rule name="NPF SOS 8501" dir=in action=allow protocol=TCP localport=8501
> ```

---

## 3. Login Accounts

| Username     | Password | Role                      | Permissions                                  |
|--------------|----------|---------------------------|----------------------------------------------|
| *(citizen)*  | *(none)* | **Citizen SOS App**       | Can send an SOS alert only — no login        |
| `commander`  | `npf123` | **Admin / Commander**     | Full access — add, edit, delete, dispatch    |
| `dispatcher` | `npf123` | **Viewer / Dispatcher**   | Read-only — view, search and print reports   |

> Demonstrating both staff accounts is the quickest way to prove the role-based access
> control works: sign in as `dispatcher` and show that every add/edit/delete button
> has disappeared.

---

## 4. Features

### 🚨 Citizen SOS app (new)
* Mobile-shaped layout with **one dramatically large red panic button**
* Three-tier location capture: real device GPS, simulated Enugu location, manual entry
* Writes directly into the shared `sos_alerts` table with status `Active`
* Full-screen **"SOS SENT! Help is on the way. Stay calm."** confirmation
* **Confirmation chime** generated locally — no downloaded audio
* **Live tracking screen** that follows the incident to *Dispatched* and shows the
  responding unit, its distance from the citizen and its ETA

### 🔔 Police alarm system (new)
* **Polls the database every 3 seconds** for new citizen alerts
* **Rings loudly** — a 6.3 s telephone-style alarm looped until acknowledged
* **Flashing red border** around the entire dashboard
* **"NEW EMERGENCY!" banner** with citizen name, phone, type, coordinates and time
* **Three nearest units already ranked** with distance and ETA
* **Silence Alarm** and **Mark as Dispatched** buttons, both of which stop the ringing
* **🎭 DEMO MODE** injects a simulated alert as a fallback for the live demo
* A **🔔 Test alarm** button so the officer can check the speakers beforehand
* Ringing is suppressed for old incidents on sign-in — the alarm means *new* emergency

### 🔐 Login system
* Two roles: **Admin/Commander** (full) and **Viewer/Dispatcher** (read-only)
* Passwords hashed with **PBKDF2-HMAC-SHA256**, 120 000 iterations, unique random salt
* Constant-time comparison (`hmac.compare_digest`) prevents timing attacks
* Session managed with `st.session_state`

### 📊 Command dashboard
* Four KPI cards: Active SOS Alerts · Total Incidents Today · Available Patrol Units ·
  Average Response Time
* Flashing red banner for the newest open incident
* Command overview map, recent-alert feed and control-room activity trail
* Charts: incidents by emergency type, alert status breakdown, fleet readiness

### 🗺️ Live SOS map (the flagship feature)
* Folium map centred on Enugu State with a street / satellite layer switch
* 🔴 **Red** markers for active SOS alerts (with a pulsing emphasis ring)
* 🟠 Orange for dispatched incidents · 🟢 Green for available patrol units ·
  ⚫ Grey for offline units · 🔵 Blue for police divisions
* Rich popups showing citizen name, phone, status, coordinates and description
* **Auto-refreshes every 3 seconds** (toggle it off to pan freely)
* New alerts are announced with a full-width red banner

### 🚨 SOS alert management (CRUD)
* Log a distress call with: citizen name, phone, latitude, longitude, emergency type
  (Armed Robbery / Kidnapping / Accident / Medical / Other), description and status
* Searchable, filterable, exportable Pandas register (CSV download)
* Update status, edit particulars, dispatch a unit, delete with confirmation
* Built-in **SOS simulator** that injects realistic distress calls at real Enugu landmarks

### 🚔 Patrol unit management
* Register units with callsign, officer, live coordinates and status
* Fleet readiness summary and unit positions on the map
* Update position/status, delete with confirmation
* Foreign key `ON DELETE SET NULL` releases any incident the unit was attending

### 🏛️ Police stations database
* Pre-loaded with six divisions of the Enugu State Command and their real GPS coordinates
* Distance-from-any-incident table for every division

### 🧭 Nearest unit calculator (the "wow" feature)
* Select any incident → instantly ranks **every** patrol unit by Haversine distance
* 🥇🥈🥉 podium cards showing distance in km and ETA (40 km/h + 15% urban delay)
* Straight-line dispatch routes drawn on the map
* One-click dispatch of the recommended unit

### 📄 Emergency incident report generator
* Formatted **NIGERIA POLICE FORCE / ENUGU STATE COMMAND / EMERGENCY RESPONSE
  INCIDENT REPORT** document
* Download as **PDF** (generated by a built-in PDF writer — no paid library),
  HTML (printable) or plain text for the incident register book
* Includes incident particulars, response dispatch block, total response time,
  the division with jurisdiction and a tamper-evident authentication code

### 🔍 Search & retrieve
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

The database is stored at **`data/sos_emergency.db`** and is shared by both modes.
It runs in **WAL (write-ahead logging)** mode with a busy timeout of 8 seconds and
automatic retries, which is what makes simultaneous writes from the citizen app and
the police dashboard safe.

---

## 6. How the Haversine Calculation Works

Latitude and longitude are angles on a sphere, not flat grid coordinates, so ordinary
Pythagoras would give badly wrong distances. The Haversine formula measures the shortest
path between two points **on the surface of the sphere**:

```
a = sin²(Δφ/2) + cos φ₁ · cos φ₂ · sin²(Δλ/2)
c = 2 · atan2(√a, √(1−a))
d = R · c                       R = 6 371.0088 km   (Earth's mean radius)

φ₁, φ₂ = latitudes of the two points (radians)
Δφ     = φ₂ − φ₁        Δλ = λ₂ − λ₁
```

`math.atan2` is used instead of `asin` because it stays numerically stable for both very
small and very large distances. The estimated travel time is:

```
ETA (minutes) = (distance_km ÷ 40 km/h) × 60 × 1.15      ← 15% urban traffic allowance
```

Verified example: Enugu State HQ (6.4483, 7.5023) → Ogui Road Division (6.4521, 7.5089)
= **0.843 km**, which matches Google Maps to within a few metres.

---

## 7. Automated Tests

Three self-contained test suites are included. Run them from the project root:

```bat
python tests\functional_test.py     REM logic, schema, Haversine accuracy, PDF, concurrency
python tests\smoke_test_ui.py       REM renders every page in both roles
python tests\two_mode_test.py       REM the complete citizen -> police -> dispatch flow
```

| Suite | What it proves |
|---|---|
| `tests/functional_test.py` | Tables and seed data exist · foreign keys enforced · create → dispatch → resolve → delete lifecycle · `ON DELETE SET NULL` behaviour · UNIQUE and CHECK constraints reject bad data · Haversine distances match known values · the nearest-unit ranking is correct · the generated PDF has a valid header, trailer and cross-reference table · **40 simultaneous inserts from 5 concurrent connections with zero "database is locked" errors** |
| `tests/smoke_test_ui.py` | The login page renders · a wrong password is rejected · all nine pages render with **zero exceptions** as Admin · the Viewer sees no admin-only page · search works across names, IDs, callsigns and types |
| `tests/two_mode_test.py` | The citizen app renders **without any login** · the form validates · pressing the SOS button **inserts a real row** with the right name, phone, type and coordinates · the police session detects it and **flags it as ringing** · **Mark as Dispatched** assigns the nearest unit and **stops the alarm** · the citizen's tracking screen shows the responding unit · then it cleans up after itself |

All three suites currently pass with **0 failures**.

---

## 8. Troubleshooting

| Problem | Solution |
|---|---|
| `python` is not recognised | Install Python 3.10+ and tick **Add python.exe to PATH** |
| `pip install` fails | Check your internet connection / proxy settings |
| Dashboard shows "database could not be initialised" | Run `python setup_db.py --reset` |
| Port 8501 already in use | `setup_and_start.bat` automatically switches to 8502 |
| Map tiles do not load | The machine needs internet access for map tiles only |
| **The alarm does not ring** | Click anywhere on the police tab once (browsers block sound until the page has been clicked), check the volume, then use **🔔 Test alarm** to confirm the speakers work |
| **The phone cannot reach the laptop** | Both must be on the same Wi-Fi; allow Python through Windows Firewall (see §2). Use a second browser tab as the fallback. |
| The alarm rings on sign-in | Only alerts newer than 5 minutes ring; run `setup_and_start.bat reset` to clear old test alerts |
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

*Demonstration prototype — all records in the seeded database are sample data.
Nigeria Police Force, Enugu State Command.*
"# sos-police" 
