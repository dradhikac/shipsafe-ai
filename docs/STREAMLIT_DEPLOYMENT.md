# Streamlit Console Deployment Guide — ShipSafe AI V2

## Overview
ShipSafe AI V2 replaces the legacy static Flask dashboard with a real-time, interactive **Streamlit DevSecOps Console** (`streamlit_app.py`).

The UI follows clean enterprise design principles:
- Light / graphite theme with crisp typography
- High information density (tables, status badges, timelines)
- Live database queries directly pulling from persisted SQLite/PostgreSQL
- Interactive tabs for deep inspection of findings, evidence snippets, impact graph, requirements, and remediation patches.

---

## Architecture

```
+--------------------+           Direct ORM Query           +--------------------+
|   Streamlit App    |  --------------------------------->  | SQLite / PostgreSQL|
| (streamlit_app.py) |                                      |  (Analysis Runs,   |
+---------+----------+                                      |   Findings, etc.)  |
          |                                                 +--------------------+
          | Trigger Remediation / Manual Recheck
          v
+--------------------+
|  FastAPI Backend   |
|   (api/app.py)     |
+--------------------+
```

---

## Local Run

```bash
# In virtualenv
streamlit run streamlit_app.py --server.port 8501
```

---

## Production Deployment

### Docker Deployment
A typical container deployment runs Streamlit alongside the FastAPI webhook service:
```dockerfile
# Dockerfile.streamlit
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Environment Configuration
The Streamlit app respects the following environment variables:
- `DATABASE_URL`: SQLAlchemy connection string (`sqlite:///shipsafe.db` or `postgresql://user:pass@host:5432/shipsafe`).
- `API_BASE_URL`: URL of the FastAPI backend (e.g. `http://localhost:8000` or `https://api.shipsafe.internal`).
- `APP_ENV`: `development` or `production`.
