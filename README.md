# MERZ Fensterimport · Render-ready Web App

React frontend + FastAPI backend in one Docker deployment.

## Features
- Upload architect PDF
- Upload Excel template
- Preview before import
- Haus A / Haus B / Beide
- Aggregation mode
- Warning list
- Import report sheet in output XLSX
- MERZ-inspired UI with local logo asset

## Local development

### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and proxies `/api` to `http://localhost:8000`.

## Docker
```bash
docker build -t merz-fensterimport .
docker run -p 10000:10000 merz-fensterimport
```

## Render deployment
1. Create a new GitHub repo and upload this project.
2. In Render, choose **New Web Service**.
3. Connect the GitHub repo.
4. Render should detect the `Dockerfile` automatically.
5. Deploy.
6. Open the provided URL.

## Important note
This is a cloud-hosted app. Uploaded PDFs and Excel templates are processed on the host where you deploy it. Confirm that this is allowed for company data before using it in production.

## Styling basis
Visual direction based on the Schreinerei Merz website structure and branding emphasis around Schreinerei MERZ / Fenster / Türen, together with the provided MERZ logo asset. citeturn884915view0
