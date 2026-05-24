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

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

Patient form submissions are saved to `instance/starthere.db` (SQLite) by default.

## Site structure

- **Home** – Overview and service cards
- **Services** – ER Admittance, In-Hospital Visits, Discharge Support, After Encounter Followup
- **Client Information** – Patient Info form (saved to database), HIPAA Forms
- **Contacts** – Georgette Johnson, Dawn Criswell, Larry Horton

## Viewing submissions

Submissions are stored in the `patient_submissions` table. To inspect locally:

```bash
sqlite3 instance/starthere.db "SELECT id, patient_name, email, service, created_at FROM patient_submissions;"
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
   - **Start command:** `gunicorn app:app`
3. Add environment variables:
   - `SECRET_KEY` — generate a random string
   - `DATABASE_URL` — paste the PostgreSQL URL from step 1
4. Deploy from your GitHub repo.

Tables are created automatically on first startup.

## Deploy elsewhere

The app works on any platform that runs Python and supports environment variables:

- **Railway** — connect repo, set `DATABASE_URL` and `SECRET_KEY`, use start command `gunicorn app:app`
- **Fly.io** — add a `Dockerfile` or use their Python buildpack with gunicorn
- **Heroku** — the included `Procfile` works with `heroku create` and a Postgres add-on

Always set a strong `SECRET_KEY` and a persistent `DATABASE_URL` in production. SQLite on ephemeral filesystems (some free tiers) will lose data on redeploy — use PostgreSQL for production.
