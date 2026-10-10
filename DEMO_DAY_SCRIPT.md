# 🎤 DEMO DAY SCRIPT

## Emergency Response and SOS Location Tracking System
### A Case Study of the Nigeria Police Force, Enugu State Command

**Total time: 22 minutes** (a 10-minute cut-down version is at the end)

> **Golden rule:** never read code from the screen. Show the system *working*.
> Your two wow moments are the **Live SOS Map** and the **Nearest Unit Calculator** —
> build everything else toward them.

---

## 0. Pre-Demo Checklist (do this 30 minutes before)

| ✔ | Task |
|---|---|
| ☐ | Laptop plugged into power; screen mirroring tested |
| ☐ | Close WhatsApp, email, music and every other app |
| ☐ | Disable Windows notifications (`Focus assist` → Alarms only) |
| ☐ | Internet is **on** (needed only for map tiles) |
| ☐ | Run `setup_and_start.bat reset` to give a clean, predictable dataset |
| ☐ | Confirm the browser opens `http://localhost:8501` and the login page shows |
| ☐ | Log in as `commander` / `npf123`, open every page once to warm the cache |
| ☐ | Sign out again so you start the demo from the login screen |
| ☐ | Zoom the browser to **110 %** so the panel is readable on the projector |
| ☐ | Second browser tab already open at `http://localhost:8501` as a backup |

**If your supervisor's laptop has no internet**, maps will show a grey background but
**everything else still works** — the markers, popups and all the calculations are local.
Mention this proactively: it is a strength (the Command does not depend on an external service).

---

## 1. Opening (2 minutes) — say this

> "Good morning sir. My project is the **Design and Implementation of an Emergency Response
> and SOS Location Tracking System**, using the **Nigeria Police Force, Enugu State Command**
> as a case study.
>
> The problem is simple: when a citizen calls the Command in distress, the control room
> currently relies on the caller describing a landmark — *'opposite Shoprite, along Ogui Road'*.
> That costs time, and time is what a kidnapping or an armed robbery victim does not have.
>
> What I have built is a Command dashboard where a distress call becomes a **GPS point on a
> map within seconds**, and the system **automatically computes which patrol unit is nearest**
> using the Haversine great-circle distance formula — so the dispatcher knows *exactly* who to
> send and *how long* they will take.
>
> Everything runs on free, open-source tools: Python, Streamlit, SQLite, Pandas and Folium.
> May I show you?"

**Then show the login screen.** Do not touch the keyboard for 3 seconds — let them look.

---

## 2. ACT 1 — Login and Role-Based Access Control (3 minutes)

**Do:** Type `commander` / `npf123` slowly and sign in.

**Say:**

> "Access is controlled by role. Passwords are never stored as plain text — they are hashed
> with **PBKDF2-HMAC-SHA256**, 120 000 iterations with a unique random salt per user, and
> compared in constant time to prevent timing attacks."

**Then sign out and sign in as `dispatcher` / `npf123`.**

**Say:**

> "This is the **Viewer / Dispatcher** role. Notice what has disappeared — there is no
> 'add alert', no 'dispatch', no 'delete' button anywhere. A dispatcher on the night shift
> can monitor and print reports but cannot alter the record. That is a deliberate
> **separation of duties** control."

**Point at the sidebar:** "The User Management page has also vanished from the menu."

---

## 3. ACT 2 — The Command Dashboard (2 minutes)

Sign back in as `commander`, land on **📊 Command Dashboard**.

**Say, pointing at each metric in turn:**

> "Four live indicators at a glance: **Active SOS alerts**, **incidents logged today**,
> **patrol units available**, and the **average response time** across all closed incidents.
>
> Below it, the red banner is announcing the newest open emergency, the map on the left is
> the whole Command area, and on the right is the live queue with the recent control-room
> activity trail — so a supervisor walking in can tell the state of the Command in five seconds."

**Do:** Scroll down to the three charts. "Incidents by emergency type, status breakdown, and fleet readiness."

---

## 4. ACT 3 — THE LIVE SOS MAP 🗺️ (5 minutes) — **WOW MOMENT #1**

**Click: 🗺️ Live SOS Map**

**Pause. Let them look at the map first.**

**Say:**

> "This is the heart of the system. This is Enugu State Command — you can see Ogui Road,
> Abakpa Nike, Trans-Ekulu, Independence Layout and Nsukka.
>
> **Red** markers are active SOS calls. **Orange** are incidents already dispatched.
> **Green** are patrol units that are available right now. **Blue** are the divisional
> headquarters. The grey ones are units that are offline."

**Do:** Click one red marker. Let the popup appear.

**Say:**

> "Every marker carries the full call record: incident number, citizen's name, telephone
> number, status, time received, exact GPS coordinates and the description of what the
> caller reported. So the dispatcher is not guessing."

**Do:** Toggle **Satellite imagery** on from the layer control (top-right of the map).

**Say:**

> "You can switch to satellite imagery to see the actual terrain — useful when directing a
> team to a location that has no street name."

**Do:** Toggle back to street map, then point to the "Auto-refresh" switch.

> "The map **auto-refreshes every five seconds**. This is the same behaviour you would get
> from a live feed from the 112 emergency line or a citizen mobile app — new calls appear on
> their own without the operator touching anything."

**⚠️ Important:** switch **Auto-refresh OFF** before you pan or zoom, otherwise the map
resets every 5 seconds. Say: *"I'll pause the refresh so I can move around freely."*

---

## 5. ACT 4 — Simulate an Incoming Emergency 📲 (3 minutes)

**Still on the Live map.** Make sure auto-refresh is **ON**.

**Do:** Click **🎲 Simulate an incoming SOS call**.

**Say (immediately, before the toast disappears):**

> "That represents a fresh distress call arriving at the control room. Watch the top of the page…"

**A full-width red banner appears:** *NEW SOS ALERT RECEIVED — SOS-00006…*

**Say:**

> "The system has flagged the new call prominently, dropped a pulsing red ring on the map at
> the exact coordinates, and it has **already computed the nearest available patrol unit**
> in the live queue on the right — see the callsign and the ETA without anyone pressing a button."

**Do:** Click the new marker and read the citizen's name, phone number and description out loud.

**If you want a bigger reaction:** click **🎬 Simulate a burst of 3 incoming calls** and say
*"Three simultaneous emergency calls — and the Command can see all three instantly."*

---

## 6. ACT 5 — NEAREST UNIT CALCULATOR 🧭 (5 minutes) — **WOW MOMENT #2**

**Click: 🧭 Nearest Unit Calculator**

**Do:** Select the **active Armed Robbery** alert (SOS-00001, Chief Anthony Nwankwo, Ogui Road).
Leave *Available units only* ticked.

**Say:**

> "This is the decision-support feature, and this is the academic contribution of the work.
>
> Historically, dispatch is done from memory or by radioing units one after another. The
> system instead computes the **great-circle distance from the incident to every patrol unit**
> using the **Haversine formula**, and ranks them **nearest first**."

**Point at the three medal cards:**

> "🥇 PATROL-01-OGUI is 0.9 km away with an ETA of about 1.5 minutes. 🥈 and 🥉 follow behind.
> The ETA assumes an average speed of 40 km/h inside Enugu metropolis with a 15% allowance
> for traffic lights, potholes and checkpoints."

**Do:** Open the **📊 Full ranking of every patrol unit** expander.

> "Every unit is ranking-numbered with its exact distance in kilometres and its ETA in minutes —
> and note that offline units are excluded automatically, because you cannot dispatch a vehicle
> that is not on the road."

**Do:** Untick *Available units only*, then re-tick it.

> "If I remove that filter you can see the units that are already committed or offline — the
> dispatcher can then decide whether to pull a unit off a lesser incident."

**Do:** Scroll to the map and point at the green solid line.

> "The nearest unit is drawn as a solid green dispatch route from the incident, with the
> runners-up in dashed blue. It converts an abstract number into an operational decision."

**Then deliver the technical line — this is what an examiner wants to hear:**

> "The Haversine formula is used rather than ordinary Pythagoras because latitude and
> longitude are angles on a sphere. The derivation is:
> `a = sin²(Δφ/2) + cos φ₁·cos φ₂·sin²(Δλ/2)`, then `c = 2·atan2(√a, √(1−a))`,
> and finally `d = R·c` with R = 6 371.0088 km, the Earth's mean radius.
> I used `atan2` instead of `asin` because it stays numerically stable for very small and
> very large distances.
>
> I validated it: the State Headquarters to Ogui Road Division computes as **0.843 km**,
> which matches Google Maps to within a few metres."

**Optional show-stopper:** Scroll further down to **🏛️ Division with jurisdiction** —
the system names the nearest division and its distance too.

---

## 7. ACT 6 — Dispatch and the Incident Lifecycle (3 minutes)

**Do:** Choose the top-ranked unit in the *Dispatch* section and click **📲 Dispatch now**.

**Say:**

> "The unit is now assigned. Watch the state changes:"

**Click: 🚨 SOS Alert Management → scroll to the register table.**

> "The alert status has changed from **Active** to **Dispatched**, the assigned unit is
> recorded against the incident, and that same unit has automatically been marked
> **Dispatched** in the fleet register so it cannot be double-booked to another call.
> That is a **foreign key relationship** between the `sos_alerts` and `patrol_units` tables,
> enforced by the database itself."

**Do:** Go to the **✏️ Update status** tab → click **✅ Mark resolved**.

**Say:**

> "When the incident is closed, the closure timestamp is recorded — which is what produces
> the average response-time metric on the dashboard — and the patrol unit is **released back
> to Available** automatically. No manual housekeeping."

**Do:** Go back to the map (or dashboard) and show that the incident is now green and the unit is green again.

---

## 8. ACT 7 — The Emergency Incident Report 📄 (3 minutes)

**Click: 📄 Incident Report**

**Do:** Select the Armed Robbery incident. Scroll slowly through the printable preview.

**Say:**

> "For the Command diary and for any subsequent investigation, the system generates the formal
> **Emergency Response Incident Report** on the Nigeria Police Force, Enugu State Command
> letterhead: incident ID, date and time, citizen particulars, emergency type, GPS coordinates,
> the description of the distress call, and then the whole **response dispatch block** —
> which unit responded, its distance from the incident, the ETA, the responding officer, the
> division with jurisdiction and the **total response time**.
>
> Every report carries a unique authentication code, so a report can be verified as genuine."

**Do:** Click **📄 Download as PDF**. Open the downloaded file in the browser/PDF viewer.

> "And it is a **real PDF** — generated internally by the application, with no paid library
> and no external service. It can be printed and filed physically."

**Do:** Also point at the **🌐 Download as HTML** button.

> "The HTML version can be opened in any browser and printed with Ctrl+P if the Command
> prefers to print from the web."

---

## 9. ACT 8 — Search and Retrieve 🔍 (2 minutes)

**Click: 🔍 Search & Retrieve**

**Say:**

> "One search box covers everything an investigating officer might have — a citizen's name,
> an incident number, a telephone number, an emergency type, a patrol callsign or a division."

**Do:** Type `Nwankwo` → results appear. Then type `SOS-00001`. Then `PATROL-01-OGUI`.

**Say:**

> "Results are grouped into incidents, patrol units and divisions. Each incident result shows
> the nearest available unit and its distance, and I can click straight through to the map or
> to the incident report."

**Do:** Click **🧭 Nearest units** on a result — you land on the calculator with that incident preselected.

---

## 10. ACT 9 — Fleet and Divisions (2 minutes, optional if time is short)

**Click: 🚔 Patrol Units**

> "The fleet register: callsign, officer, live position, status and when it was last updated.
> Unit positions are plotted on the map on the right."

**Click: 🏛️ Police Stations**

> "And these are the six divisions of the Command with their **real GPS coordinates** —
> State Headquarters, Ogui Road, Abakpa Nike, Trans-Ekulu, Independence Layout and Nsukka.
> On the left, the distance and ETA from any selected incident to every division."

---

## 11. Closing (1 minute) — say this

> "To summarise: the system delivers a **complete digital workflow** — a distress call is
> received and logged, it appears on a live command map within seconds, the **nearest patrol
> unit is computed mathematically** rather than guessed, the dispatch is tracked through to
> closure, and a formal incident report is produced.
>
> It is built entirely on **free and open-source tools** — Python, Streamlit, SQLite, Pandas
> and Folium — with **no licensing cost** to the Nigeria Police Force, and it runs on an
> ordinary laptop without any special hardware.
>
> Future work would be a **citizen mobile application** with one-tap SOS that writes directly
> into this same database, and **GSM tower triangulation** for callers whose GPS is unavailable.
>
> Thank you sir. I am ready for your questions."

---

## 12. Q&A — Prepare These Answers

**Q1. Where does the SOS alert actually come from? Is this real?**
> "In this prototype the alerts are logged by the control room operator or injected by the
> simulator, because we do not have a deployed citizen mobile app. The database schema and the
> intake function are already written to accept a mobile app or the 112 emergency line —
> that is the next phase. The tracking, dispatch and reporting logic is fully functional."

**Q2. Is SQLite strong enough? Why not MySQL or PostgreSQL?**
> "SQLite was chosen because it is built into Python, has zero installation and administration
> overhead, and is fully ACID-compliant with real foreign keys and CHECK constraints — which I
> demonstrate. For a single Command control room, that is the correct engineering trade-off.
> The data layer is isolated in one module, `db.py`, so migrating to PostgreSQL later only
> means changing that one file."

**Q3. How accurate is your distance calculation?**
> "Haversine assumes a perfect sphere, which gives an error of about 0.3–0.5%. That is a few
> metres over the distances we dispatch across — far below the GPS accuracy of a phone.
> For a very large-scale deployment the Vincenty formula on the WGS-84 ellipsoid would be the
> next step, at the cost of a much heavier computation."

**Q4. What about traffic? The ETA could be wrong.**
> "Correct — the ETA is an estimate. I use 40 km/h with a 15% delay allowance, and the speed
> is a parameter the operator can change on screen. Integrating live traffic data or historical
> travel times from the Command's own records would improve it. The important operational
> output is the **ranking** — which unit is nearest — and that is exact."

**Q5. What if the network goes down?**
> "The application, the database and every calculation run locally on the laptop. Only the map
> tiles come from the internet. If the network fails, all markers, popups, distances, ETAs and
> reports still work; only the background map image is missing."

**Q6. How secure is the login?**
> "Passwords are hashed with PBKDF2-HMAC-SHA256, 120 000 iterations, unique 16-byte salt per
> user, and verified with a constant-time comparison. The database never stores a password.
> The demo accounts both use `npf123`, which is why I would enforce a password policy before
> any real deployment — the strength meter for that is already in the user-creation form."

**Q7. Can a dispatcher tamper with records?**
> "No. The Viewer/Dispatcher role is read-only at the interface level, and every write action
> is restricted to the Admin/Commander role. Every write is also written to an `activity_log`
> table with the actor's username and a timestamp, so there is an audit trail."

**Q8. What is the difference between your system and Google Maps?**
> "Google Maps gives a citizen directions. This system gives the **Command** a decision: which
> of *my* units is closest to *this* incident, is that unit available, how long will it take,
> and has it been dispatched? It is a command-and-control tool, not a navigation tool."

**Q9. Did you write the map code yourself?**
> "The mapping is rendered with **Folium**, which is the Python interface to Leaflet — the same
> open-source JavaScript mapping library used by many commercial products. Writing a map
> renderer from scratch would be reinventing a solved problem, and the assessment is about the
> **emergency-response logic**, which is entirely my own: the schema, the dispatch algorithm,
> the nearest-unit computation, the role-based access control and the report generator."

**Q10. How would this scale to the whole of Nigeria?**
> "The architecture already separates concerns: `db.py` for storage, `haversine.py` for
> geospatial logic, `auth.py` for access control and `app.py` for presentation. Scaling means
> moving the data layer to PostgreSQL with the PostGIS extension — which does spatial indexing —
> and adding a `state` or `command` column so each Command sees only its own jurisdiction."

**Q11. Why is the Haversine formula needed at all? Why not just subtract the coordinates?**
> "Because a degree of longitude is not a fixed distance. At the equator one degree of
> longitude is about 111 km, but at Enugu's latitude of 6.45° north it is only about 110 km —
> and the error grows as you move away from the equator. Straight subtraction also treats a
> spherical surface as a flat plane. Haversine accounts for the curvature of the Earth."

**Q12. Can this work on a phone?**
> "The dashboard is responsive and works in a mobile browser. The proper mobile use case,
> however, is the citizen SOS app, which would post a GPS position straight into the same
> database — that is the recommended next phase of the work."

**Q13. How did you test it?**
> "I wrote two automated test suites. `tests/functional_test.py` tests the data layer and the
> business logic — creating, dispatching, resolving and deleting an incident, the foreign-key
> behaviour, the CHECK and UNIQUE constraints, the Haversine accuracy against known distances,
> and the structural validity of every generated PDF. `tests/smoke_test_ui.py` drives the real
> application through Streamlit's official test harness and asserts that every page renders
> without an exception for both roles. Both suites currently pass with zero failures."

**Q14. What was the most difficult part?**
> *(Pick one and be specific — examiners respect honesty.)*
> "Keeping the live map consistent. The map refreshes every five seconds to simulate real-time
> data, but re-rendering a map resets the operator's pan and zoom. I solved it by isolating the
> map inside a Streamlit fragment that re-runs on its own, and by giving the operator a toggle
> to freeze the refresh while they inspect an area."

**Q15. If you had three more months, what would you add?**
> "A citizen mobile app with one-tap SOS; integration with the 112 emergency line; automatic
> SMS acknowledgement to the caller; live traffic feeds for more accurate ETAs; and role-based
> dashboards per division so each DPO sees only their own area of responsibility."

**If you do not know an answer, say:**
> "That is a good question sir. I have not implemented that, but my understanding is …
> and I would approach it by …"

Never bluff. A clear "I do not know, but here is how I would find out" scores better than
an invented answer.

---

## 13. If Something Goes Wrong — Recovery Plan

| Problem | What to do (and say) |
|---|---|
| Browser shows a blank page | Press **R** to reload. Streamlit reconnects automatically. |
| "Port 8501 is already in use" | The launcher automatically switches to **8502**. Open `http://localhost:8502`. |
| The dashboard stops responding | Close the green server window, run `setup_and_start.bat` again (takes ~20 seconds). |
| Data looks messy after experiments | `setup_and_start.bat reset` — the database is rebuilt and re-seeded in seconds. |
| Map area is grey | No internet. Continue — say "only the background tiles need internet; every marker, distance and ETA is computed locally." |
| Typo in the terminal | Just scroll on; the terminal is not part of the demonstration. |
| A page shows a red error box | Stay calm: it is caught by the error handler, not a crash. Note the incident id, click another menu item, and continue. |

**Before the demo, rehearse the recovery once.** Confidence in the recovery is worth more
than perfection in the first run.

---

## 14. Short on Time? The 10-Minute Version

| Minute | Show |
|---|---|
| 0–1 | Login as `commander`, say the problem statement in two sentences |
| 1–2 | Dashboard — point at the four metrics only |
| 2–6 | **Live SOS Map** — toggle auto-refresh on, click **Simulate incoming SOS**, show the red banner and the new marker popup, toggle satellite |
| 6–9 | **Nearest Unit Calculator** — the three medal cards, the full ranking table, the green dispatch route, then state the Haversine formula and the 0.843 km validation |
| 9–10 | **Dispatch now** → show the status changing to Dispatched → **Incident Report** → **Download as PDF** and open it |

Close with the "free and open-source, no licensing cost, runs on an ordinary laptop" line.

---

## 15. One-Page Cheat Sheet (print this)

```
LOGIN          commander / npf123     (full access)
               dispatcher / npf123    (read-only)

MENU           📊 Dashboard · 🗺️ Live Map · 🚨 SOS Alerts · 🧭 Nearest Unit
               🚔 Patrol Units · 🏛️ Stations · 📄 Report · 🔍 Search · 👤 Users

WOW #1         Live SOS Map      → auto-refresh 5 s → Simulate incoming SOS
WOW #2         Nearest Unit Calc → 🥇🥈🥉 cards → full ranking → green route line

KEY NUMBER     0.843 km  =  State HQ → Ogui Road Division  (validated)

FORMULA        a = sin²(Δφ/2) + cosφ₁·cosφ₂·sin²(Δλ/2)
               c = 2·atan2(√a, √(1−a))
               d = R·c          R = 6 371.0088 km

ETA            (km ÷ 40 km/h) × 60 × 1.15

STACK          Python · Streamlit · SQLite · Pandas · Folium · Haversine
SECURITY       PBKDF2-HMAC-SHA256, 120 000 iterations, unique salt
TESTING        tests/functional_test.py · tests/smoke_test_ui.py  → 0 failures
RESET          setup_and_start.bat reset
```
