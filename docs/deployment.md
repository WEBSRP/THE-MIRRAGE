# MIRRAGE Deployment and Operations Guide

This guide details setup procedures for local development workstations and production deployment on AWS EC2 and Vercel.

---

## 1. Local Development Setup

Follow these steps to run the complete MIRRAGE stack locally on a developer machine.

### Prerequisites

- Python 3.13 or higher
- Node.js 20 or higher, with `npm`
- Git

### Step 1: Clone the Repository

```bash
git clone https://github.com/the-mirrage/THE-MIRRAGE.git
cd THE-MIRRAGE
```

### Step 2: Configure and Run Backend

1. Navigate to the backend directory and create a virtual environment:
   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install Python dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. Prepare the environment configuration:
   ```bash
   cp .env.example .env
   ```
   Ensure `.env` contains:
   ```dotenv
   ENVIRONMENT=development
   DATABASE_URL=sqlite+aiosqlite:///./mirrage.db
   SECRET_KEY=dev-secret-key-do-not-use-in-production-min-32-chars
   K8S_MODE=mock
   VPN_MODE=mock
   ```

4. Initialize the local database:
   ```bash
   python scripts/init_db.py
   ```

5. Start the FastAPI development server from the repository root:
   ```bash
   cd /home/admin/THE-MIRRAGE
   PYTHONPATH=. backend/.venv/bin/uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   Alternatively, if `.venv` is activated:
   ```bash
   PYTHONPATH=. uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   The interactive API documentation is accessible at `http://127.0.0.1:8000/docs`.

### Step 3: Configure and Run Frontend

1. Navigate to the frontend directory:
   ```bash
   cd /home/admin/THE-MIRRAGE/frontend
   ```

2. Install JavaScript packages:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   Vite runs at `http://localhost:5173`. The configured dev proxy automatically routes all `/api` requests to `http://127.0.0.1:8000` without requiring Cross-Origin Resource Sharing (CORS) adjustments.

---

## 2. EC2 Production Deployment

In production, the backend, reverse proxy, ingress tunnel, and game sandboxes operate on an AWS EC2 instance (Ubuntu 24.04 LTS), while the frontend is hosted on Vercel.

### Step 1: Backend Systemd Service

The backend runs as an unprivileged systemd service managed by systemd.

1. Copy the systemd service template to the system directory:
   ```bash
   sudo cp infrastructure/systemd/mirrage-backend.service.example /etc/systemd/system/mirrage-backend.service
   ```

2. The service file configuration (`/etc/systemd/system/mirrage-backend.service`):
   ```ini
   [Unit]
   Description=MIRRAGE FastAPI Backend
   After=network.target

   [Service]
   Type=simple
   User=admin
   Group=admin
   WorkingDirectory=/home/admin/THE-MIRRAGE
   Environment="PYTHONPATH=/home/admin/THE-MIRRAGE"
   Environment="PATH=/home/admin/THE-MIRRAGE/backend/.venv/bin:/usr/local/bin:/usr/bin:/bin"
   ExecStart=/home/admin/THE-MIRRAGE/backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the backend service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now mirrage-backend
   ```

### Step 2: Nginx Reverse Proxy Configuration

Nginx accepts local connections on port 80 and proxies them to the FastAPI application on port 8000.

1. Install Nginx:
   ```bash
   sudo apt update
   sudo apt install -y nginx
   ```

2. Install the configuration from `infrastructure/nginx/mirrage.conf.example`:
   ```bash
   sudo cp infrastructure/nginx/mirrage.conf.example /etc/nginx/sites-available/mirrage.conf
   sudo ln -sf /etc/nginx/sites-available/mirrage.conf /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   ```

3. Verify and reload Nginx:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Step 3: Cloudflare Tunnel Configuration (`cloudflared`)

Cloudflare Tunnel securely publishes `api.themirrage.me` directly to `127.0.0.1:80` without exposing any public inbound ports on the EC2 security group.

1. Install `cloudflared`:
   ```bash
   sudo apt install -y cloudflared
   ```

2. Place the tunnel credential token obtained from the Cloudflare Zero Trust dashboard:
   ```bash
   sudo mkdir -p /etc/cloudflared
   echo "<TUNNEL_TOKEN>" | sudo tee /etc/cloudflared/token
   sudo chmod 600 /etc/cloudflared/token
   sudo chown root:root /etc/cloudflared/token
   ```

3. Install and activate the systemd service:
   ```bash
   sudo cp infrastructure/systemd/cloudflared.service.example /etc/systemd/system/cloudflared.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now cloudflared
   ```

### Step 4: Backend Production Environment Configuration

The production environment file is located at `backend/.env` (which is excluded from Git tracking via `.gitignore`).

Required production settings:
```dotenv
ENVIRONMENT=production
PROJECT_NAME="MIRRAGE API"
SECRET_KEY=<SECURE_RANDOM_KEY_AT_LEAST_32_CHARS>
ACCESS_TOKEN_EXPIRE_MINUTES=1440

DATABASE_URL=postgresql+asyncpg://<DB_USER>:<DB_PASSWORD>@<RDS_ENDPOINT>:5432/<DB_NAME>

BACKEND_CORS_ORIGINS=["https://themirrage.me","https://www.themirrage.me","https://mirrage.vercel.app"]

MAX_CONCURRENT_SESSIONS=3
SESSION_TIMEOUT_MINUTES=30
SESSION_CLEANUP_INTERVAL_SECONDS=60

# Sandbox Orchestration
K8S_MODE=mock
K8S_NAMESPACE=mirrage-sessions
K8S_IN_CLUSTER=false
K8S_KUBECONFIG_PATH=~/.kube/config
MIRAGE_CONTAINER_IMAGE=mirrage/mirage-honeypot:latest
CTF_CONTAINER_IMAGE=mirrage/ctf-core:latest

# VPN Gateway
VPN_MODE=production
OPENVPN_SERVER_HOST=ec2-18-205-71-26.compute-1.amazonaws.com
OPENVPN_SERVER_PORT=1194
OPENVPN_PROTO=udp
OPENVPN_STATUS_LOG_PATH=/var/log/openvpn/status.log

# Easy-RSA / Production VPN Provisioning
EASYRSA_DIR=/home/admin/openvpn-ca
EASYRSA_CA_CERT=/home/admin/openvpn-ca/pki/ca.crt
EASYRSA_TLS_KEY=/home/admin/openvpn-ca/ta.key
VPN_CA_PASSPHRASE_FILE=/etc/mirrage/vpn-ca-passphrase
VPN_CLIENT_NAME_PREFIX=mirrage

# Transitional Flag
# Set to true while Kubernetes live production drivers are finalized
ALLOW_MOCK_IN_PRODUCTION=true
```

> [!IMPORTANT]
> The backend validates configuration integrity on startup. If `ENVIRONMENT=production`, it requires either production-mode drivers or `ALLOW_MOCK_IN_PRODUCTION=true`. The `SECRET_KEY` must be at least 32 characters long and must not contain common identifiers.

### Step 5: Frontend Vercel Deployment

The frontend single-page application is hosted on Vercel:

1. Connect the GitHub repository to Vercel via the dashboard.
2. Select Vite as the framework preset with root directory set to `frontend`.
3. Set the build command to `npm run build` and output directory to `dist`.
4. Configure domain mappings for `themirrage.me` and `www.themirrage.me`.
5. Automatic deployments occur whenever commits are pushed to the main branch.

### Step 6: Frontend Production Environment (`.env.production`)

The frontend references `frontend/.env.production` during the build process:
```dotenv
VITE_API_BASE_URL=https://api.themirrage.me
```
When built for production, all API calls target the Cloudflare Tunnel hostname.

---

## 3. Environment Variables Reference

Below is the complete reference for backend configuration variables defined in `backend/app/core/config.py` and `backend/.env.example`.

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | string | `development` | Operating mode: `development`, `production`, or `testing`. Controls endpoint security rules. |
| `PROJECT_NAME` | string | `MIRRAGE API` | Human-readable service label used in OpenAPI metadata. |
| `SECRET_KEY` | string | None | Cryptographic secret for signing JWT tokens. Must exceed 31 characters in production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | `1440` | Lifetime in minutes of issued bearer tokens (default: 24 hours). |
| `DATABASE_URL` | string | `sqlite+aiosqlite:///./mirrage.db` | SQLAlchemy async connection string (e.g. SQLite locally or asyncpg PostgreSQL on RDS). |
| `BACKEND_CORS_ORIGINS` | list / string | `["http://localhost:5173", ...]` | Allowed HTTP origins for CORS cross-origin requests. Can be specified as JSON array or comma-separated list. |
| `MAX_CONCURRENT_SESSIONS` | integer | `3` | Maximum active sandbox sessions allowed globally across the platform. |
| `SESSION_TIMEOUT_MINUTES` | integer | `30` | Inactivity expiration duration for active player pods. |
| `SESSION_CLEANUP_INTERVAL_SECONDS` | integer | `60` | Background cleanup loop frequency for reaping expired sessions. |
| `K8S_MODE` | string | `mock` | Kubernetes provider: `mock` (simulated pods) or `production` (live k3s cluster). |
| `K8S_NAMESPACE` | string | `mirrage-sessions` | Target Kubernetes namespace where sandbox pods are scheduled. |
| `K8S_IN_CLUSTER` | boolean | `false` | Specifies whether to load in-cluster Kubernetes configuration or local kubeconfig. |
| `K8S_KUBECONFIG_PATH` | string | `~/.kube/config` | Absolute or user path to cluster admin configuration file. |
| `MIRAGE_CONTAINER_IMAGE` | string | `mirrage/mirage-honeypot:latest` | Container image repository and tag for the decoy SSH honeypot. |
| `CTF_CONTAINER_IMAGE` | string | `mirrage/ctf-core:latest` | Container image repository and tag for the challenge target system. |
| `VPN_MODE` | string | `mock` | VPN engine mode: `mock` (emulated client profiles) or `production` (live Easy-RSA/OpenVPN). |
| `OPENVPN_SERVER_HOST` | string | `vpn.mirrage.internal` | Publicly reachable IP address or hostname of the OpenVPN gateway. |
| `OPENVPN_SERVER_PORT` | integer | `1194` | UDP port for OpenVPN client connections. |
| `OPENVPN_STATUS_LOG_PATH` | string | `/var/log/openvpn/openvpn-status.log` | Path to live OpenVPN status log parsed for telemetry. |
| `ALLOW_MOCK_IN_PRODUCTION` | boolean | `false` | Operational override enabling mock k8s or VPN services when `ENVIRONMENT=production`. |

---

## 4. Service Management & Operations

Common operational commands for managing services on the EC2 host:

### Backend Service Management

Restart the FastAPI backend service:
```bash
sudo systemctl restart mirrage-backend
```

Check service status:
```bash
sudo systemctl status mirrage-backend
```

Inspect live backend logs:
```bash
journalctl -u mirrage-backend -f -n 100
```

### Nginx Reverse Proxy Management

Inspect Nginx service status:
```bash
sudo systemctl status nginx
```

Test configuration syntax:
```bash
sudo nginx -t
```

Reload Nginx without downtime:
```bash
sudo systemctl reload nginx
```

### Cloudflare Tunnel Management

Inspect tunnel status and connectivity:
```bash
sudo systemctl status cloudflared
```

Inspect cloudflared connection logs:
```bash
journalctl -u cloudflared -f -n 50
```

Restart the tunnel service:
```bash
sudo systemctl restart cloudflared
```

### Kubernetes (k3s) Inspection

List all pods across all namespaces:
```bash
kubectl get pods -A
```

Inspect active player session pods:
```bash
kubectl get pods -n mirrage-sessions -o wide
```

View detailed status of a specific pod:
```bash
kubectl describe pod <POD_NAME> -n mirrage-sessions
```

Inspect network policies in the session namespace:
```bash
kubectl get networkpolicy -n mirrage-sessions
```
