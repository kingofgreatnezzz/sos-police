# 🚀 DEPLOYMENT GUIDE

## Emergency Response and SOS Location Tracking System
### Nigeria Police Force — Enugu State Command

This guide takes you from your laptop to a **live link you can send your supervisor**,
using only free services.

| Option | Cost | Best for | Difficulty |
|---|---|---|---|
| **A. GitHub + Streamlit Community Cloud** | Free | A permanent public link for your supervisor | Easy |
| **B. Temporary public link from your laptop** | Free | A live demo *right now*, no account needed | Easiest |
| **C. Hugging Face Spaces** | Free | An alternative host with the same result | Easy |

**Recommended: Option A**, with Option B as an instant fallback on demo day.

---

# PART A — GitHub + Streamlit Community Cloud

## A1. Prerequisites

1. A free **GitHub** account → https://github.com/signup
2. A free **Streamlit Community Cloud** account → https://share.streamlit.io
   (sign in with GitHub — no card details required)
3. **Git** installed → https://git-scm.com/download/win
   Verify with: `git --version`

---

## A2. Prepare the project folder

Open a Command Prompt in the project folder and confirm the structure:

```bat
cd C:\Users\TECHDEBIA\Documents\pro\sos
dir
```

You should see:

```
app.py            auth.py           db.py             haversine.py
reports.py        setup_db.py       requirements.txt  setup_and_start.bat
run_server.bat    README.md         DEMO_DAY_SCRIPT.md
DEPLOYMENT_GUIDE.md  .gitignore     .streamlit\       tests\
```

### ⚠️ Two things to check before pushing

**1. The database must NOT be pushed.**
The `.gitignore` already excludes it, but confirm the `data/` folder is ignored.
This is deliberate: the app **creates and seeds the database automatically** on first run
(`ensure_database()` in `app.py`), which is what makes cloud deployment work with no setup.

**2. The virtual environment must NOT be pushed.** `venv/` is already ignored.

Verify with:

```bat
git status --porcelain
```
If you see `venv/` or `data/sos_database.db` in the list, stop and check `.gitignore`.

---

## A3. Push to GitHub

### First time only — create the repository

Go to https://github.com/new and create a repository:

| Field | Value |
|---|---|
| Repository name | `sos-emergency-response-enugu` |
| Description | Emergency Response and SOS Location Tracking System — NPF Enugu State Command |
| Visibility | **Public** (required for the free Streamlit Cloud tier) |
| Initialise with README | **Leave unticked** (you already have one) |

Then, in the project folder:

```bat
cd C:\Users\TECHDEBIA\Documents\pro\sos

git init
git branch -M main
git add .
git commit -m "Emergency Response and SOS Location Tracking System - NPF Enugu State Command"
git remote add origin https://github.com/YOUR-USERNAME/sos-emergency-response-enugu.git
git push -u origin main
```

> Replace `YOUR-USERNAME` with your GitHub username. Git will open a browser window
> asking you to sign in to GitHub — approve it, and the push completes.

### For later changes

```bat
git add .
git commit -m "Describe what you changed"
git push
```

Verify by opening your repository page — you should see `app.py`, `requirements.txt` and the
other files, but **no** `venv/` folder and **no** `.db` file.

---

## A4. Deploy on Streamlit Community Cloud

1. Go to **https://share.streamlit.io** and sign in with GitHub
2. Click **Create app** (or **New app**)
3. Choose **Deploy a public app from GitHub**
4. Fill in the form:

| Field | Value |
|---|---|
| Repository | `YOUR-USERNAME/sos-emergency-response-enugu` |
| Branch | `main` |
| Main file path | `app.py` |
| App URL | choose a short name, e.g. `npf-enugu-sos-tracking` |
| Python version (Advanced settings) | `3.11` (or 3.10) |

5. Click **Deploy!**

The first build takes **2–4 minutes** (it installs Streamlit, Pandas, Folium).
You will see the build log stream live. When it finishes, the app opens automatically.

### ⚠️ If Python 3.13 is selected and the build fails

Streamlit Cloud may default to a very new Python. Two fixes:

* In **Advanced settings → Python version**, select **3.11**; or
* Add a file named `runtime.txt` to the project root containing exactly:

```
python-3.11
```

then commit and push. The app redeploys automatically.

---

## A5. Share the live link

Your app is now at:

```
https://npf-enugu-sos-tracking.streamlit.app
```

Send it to your supervisor like this:

> **Subject:** Emergency Response and SOS Location Tracking System — live demonstration
>
> Good day sir. The system is deployed and can be viewed at the link below:
>
> **https://npf-enugu-sos-tracking.streamlit.app**
>
> **Login credentials**
> * Admin / Commander (full access): `commander` / `npf123`
> * Viewer / Dispatcher (read-only): `dispatcher` / `npf123`
>
> Suggested path: sign in as **commander**, open **🗺️ Live SOS Map**, and click
> **"Simulate an incoming SOS call"** — a new emergency will appear on the map
> within five seconds. Then open **🧭 Nearest Unit Calculator** to see the nearest
> patrol units ranked by distance with their ETAs.
>
> Thank you.

---

## A6. Important: how the cloud database behaves

Streamlit Community Cloud gives each app an **ephemeral filesystem**:

* On the **first** visit the app detects that no database exists, creates it and seeds the
  demo data automatically — so the app is never empty.
* Data you add is kept **while the app is running**, but a **reboot or a redeploy resets it**
  back to the seeded demo state.
* This is ideal for a demonstration (the data is always clean and predictable) but it is
  **not** suitable for real operational records.

**For a real deployment**, replace SQLite in `db.py` with a hosted database. Suitable free
tiers include **Supabase** or **Neon** (PostgreSQL) and **Turso** (hosted SQLite). Because all
database access is isolated in `db.py`, only that one file needs to change.

---

# PART B — A Temporary Public Link From Your Laptop (no account needed)

Use this if a supervisor asks to see the system **right now**, or as a backup on demo day.

### B1. Start the system normally

```bat
setup_and_start.bat
```

The dashboard runs at `http://localhost:8501`.

### B2. Create a public tunnel with Cloudflare (free, no account)

Download `cloudflared.exe` once from
https://github.com/cloudflare/cloudflared/releases/latest
(choose `cloudflared-windows-amd64.exe`, rename it to `cloudflared.exe`).

Then, in a **new** Command Prompt while the dashboard is running:

```bat
cloudflared.exe tunnel --url http://localhost:8501
```

After a few seconds it prints a public URL such as:

```
https://random-words-here.trycloudflare.com
```

Share that link. It works for as long as the Command Prompt window and the dashboard stay open.

> **Note:** Your laptop must remain switched on and online for the link to work.
> The URL changes every time you restart the tunnel, so this is for live demonstrations only.

### B3. Alternative: ngrok

```bat
ngrok http 8501
```

Same idea, but ngrok requires a free account and an authtoken.

---

# PART C — Hugging Face Spaces (alternative host)

1. Create a free account at https://huggingface.co/join
2. Click **New → Space**
3. Fill in:

| Field | Value |
|---|---|
| Space name | `sos-emergency-response-enugu` |
| License | `mit` |
| SDK | **Docker** → then switch to **Streamlit** |
| Hardware | CPU basic (free) |

4. Upload the project files (`app.py`, `auth.py`, `db.py`, `haversine.py`, `reports.py`,
   `setup_db.py`, `requirements.txt` and the `README.md`).
5. Hugging Face detects Streamlit and builds automatically.

> Hugging Face Spaces also has an ephemeral filesystem, so the same note as **A6** applies.
> It also **sleeps** after a period of inactivity; the first visit afterwards takes ~30 seconds
> to wake up.

---

# PART D — Deployment Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Build fails: `No module named streamlit` | `requirements.txt` missing or not committed | `git add requirements.txt && git commit -m "add requirements" && git push` |
| Build fails on `pyarrow` / `numpy` | Python version too new | Set Python **3.11** in Advanced settings, or add `runtime.txt` with `python-3.11` |
| App opens but shows "database could not be initialised" | The `data/` folder could not be created | Confirm the app has write access; the app creates `data/` automatically, so a reboot usually fixes it |
| Map is grey / blank | Outbound tile requests blocked | Markers and all calculations still work; try another network |
| `Error: Your app is having trouble` | An unhandled exception | Open **Manage app → Logs** on Streamlit Cloud and read the traceback |
| Login fails with the demo password | Database re-seeded with a different password | Clear the app (Manage app → Reboot) and use `commander` / `npf123` |
| Changes to GitHub do not appear | Streamlit caches the app | Manage app → **Reboot**, or push a trivial commit to trigger a rebuild |
| Port 8501 in use locally | Another Streamlit instance is running | Close the green "SOS COMMAND SERVER" window, or use port 8502 |

---

# PART E — Pre-Submission Checklist

| ✔ | Item |
|---|---|
| ☐ | GitHub repository is **public** and contains no `venv/` or `.db` files |
| ☐ | `requirements.txt` is committed and installs cleanly from scratch |
| ☐ | The live Streamlit Cloud URL opens in an **incognito** window (proves it is public) |
| ☐ | `commander` / `npf123` signs in successfully on the live link |
| ☐ | `dispatcher` / `npf123` signs in and shows **no** admin buttons |
| ☐ | The Live SOS Map shows markers and refreshes every 5 seconds |
| ☐ | The Nearest Unit Calculator returns three ranked units with distances and ETAs |
| ☐ | An incident report downloads as a PDF and opens correctly |
| ☐ | The live link and the login credentials have been **emailed to your supervisor** |
| ☐ | `tests/functional_test.py` and `tests/smoke_test_ui.py` both report **0 failures** |
| ☐ | The demo script (`DEMO_DAY_SCRIPT.md`) has been rehearsed at least twice |

---

# PART F — Useful Commands Reference

```bat
REM ---- run locally -----------------------------------------------------------
setup_and_start.bat                 normal start
setup_and_start.bat reset           wipe and re-seed the demo database
setup_and_start.bat fresh           ignore myenv and build a clean local venv

REM ---- manual control -------------------------------------------------------
myenv\Scripts\activate              activate your virtual environment
python setup_db.py --reset          rebuild the database
python -m streamlit run app.py      start the dashboard manually
python tests\functional_test.py     run the logic test suite
python tests\smoke_test_ui.py       run the UI smoke test

REM ---- git ------------------------------------------------------------------
git status                          what has changed
git add .                           stage everything
git commit -m "message"             commit
git push                            push to GitHub
git log --oneline -10               recent commits

REM ---- public tunnel for a live demo ----------------------------------------
cloudflared.exe tunnel --url http://localhost:8501
ngrok http 8501
```

---

*Emergency Response and SOS Location Tracking System · Nigeria Police Force,
Enugu State Command · Deployed entirely on free and open-source tooling.*
