# StartHere Patient Advocacy

A Python (Flask) website for StartHere Patient Advocacy with database-backed patient intake forms, a contacts page, and deployment support for Render.

## Setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # optional: set SECRET_KEY and contact info
```

## Run locally

```bash
python app.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) (About page: `/about`).

On macOS, `http://localhost:5000` is often **not** this app — AirPlay Receiver uses that port and returns a blank or 403 response. Use `127.0.0.1` and port **5001** (the local default), or set `PORT` in `.env` if you need another port.

Patient form submissions are saved to the relational database in `instance/starthere.db` (SQLite) by default.

## Data model

The database follows the StartHere ER diagram with these tables:

| Table | Purpose |
|-------|---------|
| `companies` | Top-level organization (StartHere Patient Advocacy) |
| `clients` | Primary contacts who request advocacy services |
| `patients` | Patients receiving advocacy |
| `patient_relationships` | Related contacts for a patient (family, caregivers) |
| `advocates` | StartHere patient advocates |
| `providers` | External medical providers involved in care |
| `hospitals` | Hospital facilities |
| `home_health_facilities` | Home health agencies |
| `encounters` | Service events (ER Visit, Inpatient Stay, discharge, follow-up) |
| `notes` | Documentation attached to encounters |
| `lookup_lists` | Reference lists (e.g. account types) |
| `accounts` | Client/patient financial accounts |
| `billings` | Billing records linked to notes and accounts |
| `invoices` | Invoices for an account |
| `invoice_items` | Line items on an invoice |

On startup, the app seeds **StartHere Patient Advocacy**, the three advocates, and default account-type lookup values.

The Patient Info form creates a **Client**, **Patient**, **Encounter**, optional **Hospital**, and optional **Note**.

## Site structure

- **Home** – Overview and service cards
- **Services** – ER Visit, Inpatient Stay, Discharge Support, After Encounter Followup
- **Client Information** – Patient Info form (saved to database), HIPAA Forms
- **About StartHere** – Advocate bios (Dawn Criswell, Georgette Darnell, Larry Horton) and team contacts

## Viewing data locally

```bash
sqlite3 instance/starthere.db "SELECT p.first_name, p.last_name, e.encounter_type, e.status, e.created_at FROM encounters e JOIN patients p ON p.id = e.patient_id ORDER BY e.created_at DESC;"
```

Other useful queries:

```bash
sqlite3 instance/starthere.db "SELECT name, title, email FROM advocates;"
sqlite3 instance/starthere.db "SELECT name FROM hospitals;"
```

## Environment variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Required in production for form security |
| `DATABASE_URL` | PostgreSQL connection string (SQLite used if unset) |
| `CONTACT_*_EMAIL` / `CONTACT_*_PHONE` | Optional contact details for the Contacts page |

See `.env.example` for all contact variable names.

## Deploy to Render (recommended)

[Render](https://render.com) offers a free tier suitable for this app.

1. Push this project to a GitHub repository.
2. In the Render dashboard, choose **New → Blueprint** and connect the repo.
3. Render reads `render.yaml` and creates:
   - A **Web Service** running gunicorn
   - A **PostgreSQL database** for form submissions
4. Set optional contact environment variables under the web service's **Environment** tab.
5. Deploy — your site will be live at a `*.onrender.com` URL.

### Manual Render setup (without Blueprint)

1. Create a **PostgreSQL** database on Render and copy its **Internal Database URL**.
2. Create a **Web Service**:
   - **Build command:** `pip install -r requirements.txt`
   - **Pre-Deploy command:** `python scripts/migrate_schema.py`
   - **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
3. Add environment variables:
   - `SECRET_KEY` — generate a random string
   - `DATABASE_URL` — paste the PostgreSQL URL from step 1
4. Deploy from your GitHub repo.

Schema updates run in the **Pre-Deploy command** (`python scripts/migrate_schema.py`), not during web server boot.

## Deploy elsewhere

The app works on any platform that runs Python and supports environment variables:

- **Railway** — connect repo, set `DATABASE_URL` and `SECRET_KEY`, use start command `gunicorn app:app --bind 0.0.0.0:$PORT`
- **Fly.io** — add a `Dockerfile` or use their Python buildpack with gunicorn
- **Heroku** — the included `Procfile` works with `heroku create` and a Postgres add-on

Always set a strong `SECRET_KEY` and a persistent `DATABASE_URL` in production. SQLite on ephemeral filesystems (some free tiers) will lose data on redeploy — use PostgreSQL for production.
