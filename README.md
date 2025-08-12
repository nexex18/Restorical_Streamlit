Eco Site Analytics — Isolated Visualization App

Overview
- A self-contained Streamlit application to explore the Ecology Sites SQLite database copied into this folder (`data/ecology_sites.db`).
- No system-wide changes: everything runs inside this project folder using a local virtual environment. Optionally, use the provided Dockerfile for full OS-level isolation.

What’s Included
- Streamlit multi-page app covering:
  - Overview dashboard (key metrics, quick charts)
  - Sites Explorer (filters, search, CSV export)
  - Narratives viewer (by site, section ordering)
  - Documents browser (category/date/status filters)
  - Qualifications explorer (tiers, scores, decisions)
  - Contaminants summary (top contaminants, statuses)
  - Contacts summary (prioritized prospects)
- Reusable DB helpers with cached queries to keep things snappy.

Project Layout
- `data/ecology_sites.db` — local copy of your database
- `streamlit_app.py` — app entrypoint
- `pages/` — individual pages for each data area
- `app_lib/db.py` — SQLite helpers and caching
- `requirements.txt` — Python deps for the local venv
- `Dockerfile` — optional containerized runtime (no host impact)

Run Locally (isolated venv)
1) Create a local virtual environment inside this folder:
   - macOS/Linux: `python3 -m venv .venv`
   - Windows (PowerShell): `py -m venv .venv`
2) Activate it:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows (PowerShell): `.venv\\Scripts\\Activate.ps1`
3) Install deps (within the venv only):
   - `pip install -r requirements.txt`
4) Run the app (still within the venv):
   - `streamlit run streamlit_app.py`

Optional: Full Isolation with Docker
1) Build: `docker build -t eco-site-analytics .`
2) Run: `docker run --rm -p 8501:8501 -v $(pwd)/data:/app/data eco-site-analytics`
   - The DB is read from `/app/data/ecology_sites.db` inside the container.

Notes
- The app only reads from the SQLite DB; it does not mutate data.
- If your source DB changes, recopy it into `data/` or mount it into the container at runtime.

