# AIPI Production Deployment & Infrastructure Guide

**Airfare Price Index for India (AIPI)**  
*Smart India Hackathon 2026 · Problem Statement 26056 · Ministry of Statistics and Programme Implementation (MoSPI)*

---

## 1. Deployment Architecture Overview

The AIPI decision support platform is designed for containerized cloud, on-premise government datacenter (NIC/MeitY), or edge deployments with zero mandatory external SaaS dependencies.

```mermaid
graph TD
    Client["Client Web Browser (HTTPS)"] --> CDN["Reverse Proxy / Nginx / TLS Termination"]
    CDN -->|/dashboard & static assets| StaticFiles["Static SPA Delivery (/dashboard)"]
    CDN -->|/api/* & /health| FastAPIServer["FastAPI Application Cluster (Gunicorn / Uvicorn)"]
    FastAPIServer -->|Snapshot Mode| MemoryStore["In-Memory SnapshotStore"]
    FastAPIServer -->|Enterprise Mode| PostgresDB[("PostgreSQL Database (Vintages)")]
```

---

## 2. Environment Configuration

Create a production `.env` file in the root directory:

```ini
# ==============================================================================
# AIPI Production Environment Configuration
# ==============================================================================

# Application Environment
AIPI_ENV=production
AIPI_APP_NAME="Airfare Price Index for India"
AIPI_VERSION=0.1.0

# Network Binding
AIPI_HOST=0.0.0.0
AIPI_PORT=8000
AIPI_WORKERS=4

# Database Connection (Optional: if omitted, SnapshotStore memory mode is used)
DATABASE_URL=postgresql://aipi_user:secure_password@postgres:5432/aipi_db

# Cross-Origin Resource Sharing (CORS)
FRONTEND_ORIGINS=https://aipi.mospi.gov.in,https://dashboard.aipi.internal

# Data Governance & Security
ALLOW_PLACEHOLDER_WEIGHTS=false
MAD_TRIM_K=3.5
GEKS_WINDOW_DAYS=25
```

---

## 3. Deployment Options

### Option 1: Docker Compose (Standard Production)

The repository includes a production-ready `Dockerfile` and `docker-compose.yml`.

1. **Build and start services**:
   ```bash
   docker compose up -d --build
   ```
2. **Verify container health**:
   ```bash
   docker compose ps
   curl -f http://127.0.0.1:8000/health
   ```
3. **Inspect container logs**:
   ```bash
   docker compose logs -f aipi-api
   ```

---

### Option 2: Linux / Systemd + Gunicorn (Bare Metal or VM)

For bare metal installations in government cloud environments:

1. **Install system dependencies & Python 3.12**:
   ```bash
   sudo apt update && sudo apt install -y python3.12 python3.12-venv nginx
   ```
2. **Setup virtual environment**:
   ```bash
   cd /opt/aipi
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e .
   pip install gunicorn uvicorn
   ```
3. **Create Systemd Service (`/etc/systemd/system/aipi.service`)**:
   ```ini
   [Unit]
   Description=AIPI Econometric API & Decision Support Service
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/opt/aipi
   Environment="PATH=/opt/aipi/.venv/bin"
   EnvironmentFile=/opt/aipi/.env
   ExecStart=/opt/aipi/.venv/bin/gunicorn aipi.api.main:app \
       --workers 4 \
       --worker-class uvicorn.workers.UvicornWorker \
       --bind 127.0.0.1:8000 \
       --access-logfile /var/log/aipi/access.log \
       --error-logfile /var/log/aipi/error.log

   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
4. **Enable and start service**:
   ```bash
   sudo mkdir -p /var/log/aipi && sudo chown -R www-data:www-data /var/log/aipi
   sudo systemctl daemon-reload
   sudo systemctl enable --now aipi
   ```

---

## 4. Reverse Proxy & TLS Configuration (Nginx)

Place the following configuration in `/etc/nginx/sites-available/aipi.conf`:

```nginx
# ==============================================================================
# AIPI Production Nginx Configuration
# ==============================================================================

server {
    listen 80;
    server_name aipi.mospi.gov.in;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name aipi.mospi.gov.in;

    # SSL Certificates
    ssl_certificate /etc/ssl/certs/aipi_mospi.crt;
    ssl_certificate_key /etc/ssl/private/aipi_mospi.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; font-src 'self' https://fonts.gstatic.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:; connect-src 'self';" always;

    # Gzip Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1024;

    # Root redirect to dashboard
    location = / {
        return 301 /dashboard/;
    }

    # Static Assets & API Proxying
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }

    # Static Caching for Dashboard Assets
    location /dashboard/src/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
    }
}
```

---

## 5. Production Readiness & Pre-Launch Checklist

- [x] **Automated Test Suite**: All 155 unit, econometric, and API contract tests pass (`python -m pytest`).
- [x] **Strict TypeScript Compilation**: 0 compilation errors across all `.ts` components (`tsc --noEmit -p dashboard`).
- [x] **JavaScript Syntax Validation**: 0 syntax errors across all ES module files (`node --check`).
- [x] **Data Integrity Verification**: 0 mock or hardcoded statistics in the frontend; all metrics sourced from `/api/v1/*`.
- [x] **Race Condition Guardrails**: Active `AbortController` cancellation integrated on all 8 views.
- [x] **WCAG 2.1 AA Compliance**: Keyboard navigation, ARIA attributes, semantic headings, and `.sr-only` fallback data tables verified.
- [x] **XSS & Injection Protection**: Deterministic HTML escaping (`escapeHtml()`) active on all dynamic data points.
- [x] **Lineage & Provenance**: Cryptographic `run_id`, git commit SHA, and configuration hashes exposed on all publication endpoints.
- [x] **Health Check Integration**: `/health` endpoint reporting live data age and data mode.

---

## 6. Maintenance & Operational Runbooks

### Triggering a Daily Calculation Pipeline Run
```bash
python -m aipi.pipeline run --source parquet --output-dir data/vintages
```

### Rotating In-Memory Snapshots Without Downtime
When updating market data vintages, send `SIGHUP` to the Gunicorn master process to gracefully reload workers:
```bash
sudo systemctl reload aipi
```
