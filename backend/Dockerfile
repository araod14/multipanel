# Control Plane image. Build context is the REPO ROOT (see docker-compose.yml)
# so the frontend can be built and baked in alongside the backend.

# --- Stage 1: build the React SPA -----------------------------------------
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Python API + baked SPA --------------------------------------
FROM python:3.12-slim
WORKDIR /app

# System deps kept minimal; wheels cover cryptography/bcrypt on slim.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# Built SPA served by FastAPI at the site root (single origin behind nginx).
COPY --from=frontend /fe/dist ./frontend_dist

EXPOSE 9000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
