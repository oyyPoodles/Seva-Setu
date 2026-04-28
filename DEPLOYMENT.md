# SevaSetu Google Cloud Production Deployment

This project is configured for:

- Frontend: Firebase Hosting, using Firebase framework-aware Hosting for the Next.js app.
- Backend: Cloud Run, built from `backend/Dockerfile`.
- Database: Cloud SQL for PostgreSQL 16 with the `vector` and `uuid-ossp` extensions.

Google references:

- Cloud SQL supports `pgvector` for PostgreSQL 13 and later: https://cloud.google.com/sql/docs/postgres/extensions
- Firebase Hosting can deploy Next.js apps with framework-aware Hosting: https://firebase.google.com/docs/hosting/frameworks/nextjs

## Prerequisites

Install and authenticate:

```powershell
gcloud auth login
gcloud auth application-default login
firebase login
```

You also need billing enabled on the Google Cloud project.

## One-Command Production Deploy

Run from the repository root:

```powershell
.\scripts\deploy-production.ps1 `
  -ProjectId "your-gcp-project-id" `
  -Region "asia-south1"
```

The script prompts for:

- Cloud SQL password
- Gemini API key
- Google Maps API key

It then:

1. Enables required Google/Firebase APIs.
2. Creates a Cloud SQL PostgreSQL 16 instance and database if they do not exist.
3. Stores the database URL and API keys in Secret Manager.
4. Grants the Cloud Run runtime service account Cloud SQL and Secret Manager access.
5. Deploys the FastAPI backend to Cloud Run with min instances set to 1.
6. Writes `frontend/.env.production` with the deployed Cloud Run URL.
7. Deploys the Next.js frontend through Firebase Hosting.

## Smoke Test

After deploy, run:

```powershell
.\scripts\smoke-test-production.ps1 `
  -BackendUrl "https://your-cloud-run-url" `
  -FrontendUrl "https://your-gcp-project-id.web.app"
```

The smoke test checks:

- `/health`
- `/api/dashboard/stats`
- `/api/needs`
- Firebase-hosted home, dashboard, and needs pages

## Production Notes

- Cloud Run is deployed with `--min-instances 1` to reduce cold-start fluctuations.
- The app creates `CREATE EXTENSION IF NOT EXISTS vector` and `uuid-ossp` on startup.
- Do not commit `.firebaserc`, `frontend/.env.production`, backend `.env` files, or service account JSON.
- `FIREBASE_CREDENTIALS_PATH` is intentionally unset by the deployment script. If you enable Firebase auth enforcement later, also update the frontend to send Firebase ID tokens in mutating API requests.
