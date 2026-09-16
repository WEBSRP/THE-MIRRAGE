# MIRRAGE

**MIRRAGE** is a cloud-first cybersecurity training platform combining CTF challenges with deception/honeypot environments. Players connect through VPN to isolated Kubernetes-orchestrated sessions where they must distinguish real infrastructure from decoys.

*"What you see is not what was built."*

---

## Architecture

### Public Web Application

```
Browser
  |
  v
https://www.themirrage.me  (Vercel)
  |
  | HTTPS API requests
  v
https://api.themirrage.me  (Cloudflare Tunnel)
  |
  v
cloudflared on EC2
  |
  v
Nginx :80
  |
  v
FastAPI :8000
  |
  v
Amazon RDS PostgreSQL
```

### Private Player Sessions

```
Player
  |
  v
OpenVPN (10.8.0.0/24)
  |
  v
EC2
  |
  v
k3s (mirrage-sessions namespace)
  |
  v
Per-player Pod
  |-- Mirage   (honeypot SSH, port 22)
  |-- CTF      (challenge SSH, port 2222)
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4 |
| Backend | FastAPI, Python 3.13, SQLAlchemy (async) |
| Database | Amazon RDS PostgreSQL |
| Auth | JWT (HS256), bcrypt |
| Frontend Hosting | Vercel |
| API Ingress | Cloudflare Tunnel |
| Reverse Proxy | Nginx |
| Infrastructure | AWS EC2 |
| Orchestration | k3s (Kubernetes) |
| VPN | OpenVPN + Easy-RSA |
| Containers | Mirage (honeypot) + CTF (challenge) per session |

---

## Repository Structure

```
THE-MIRRAGE/
├── frontend/               React/Vite frontend application
├── backend/                FastAPI backend application
│   ├── app/                Application source code
│   │   ├── api/            API routes (v1)
│   │   ├── core/           Config, database, security, exceptions
│   │   ├── models/         SQLAlchemy models
│   │   ├── schemas/        Pydantic schemas
│   │   ├── services/       Business logic services
│   │   └── workers/        Background workers
│   ├── scripts/            Development/admin scripts
│   ├── tests/              Backend test suite
│   ├── Dockerfile          Backend container image
│   └── .env.example        Environment variable template
├── containers/             Session container images
│   ├── mirage/             Mirage honeypot Dockerfile
│   ├── ctf/                CTF challenge Dockerfile
│   └── docker-compose.yaml Session containers compose
├── infrastructure/         Infrastructure configuration templates
│   ├── kubernetes/         k8s manifests and pod templates
│   ├── openvpn/            OpenVPN config template and provisioner
│   ├── nginx/              Nginx reverse proxy template
│   ├── systemd/            systemd unit file templates
│   └── cloudflare/         Cloudflare tunnel documentation
└── docs/                   Project documentation
    ├── architecture.md     System architecture overview
    ├── deployment.md       Deployment and operations guide
    └── security.md         Security model and secret management
```

---

## Getting Started

### Prerequisites

- Node.js (v20+)
- Python (3.13+)
- OpenVPN (for connecting to challenge environments)

### Backend Setup

1. Create and activate a virtual environment:
   ```bash
   cd THE-MIRRAGE
   python3 -m venv backend/.venv
   source backend/.venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Configure environment:
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env — set ENVIRONMENT=development
   ```

4. Start the backend:
   ```bash
   PYTHONPATH=. uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```

   API docs: http://127.0.0.1:8000/api/v1/docs

### Frontend Setup

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

   Frontend: http://localhost:5173 (API requests proxied to backend via Vite)

---

## Testing

```bash
# Backend tests
PYTHONPATH=. pytest backend/tests -v

# Frontend lint and build
cd frontend
npm run lint
npm run build
```

---

## Deployment

See [docs/deployment.md](docs/deployment.md) for full production deployment instructions.

### Key Production Services (EC2)

| Service | Command |
|---------|---------|
| Backend | `sudo systemctl status mirrage-backend` |
| Nginx | `sudo systemctl status nginx` |
| Cloudflare Tunnel | `sudo systemctl status cloudflared` |
| OpenVPN | `sudo systemctl status openvpn-server@server` |
| k3s | `kubectl get pods -A` |

---

## Security

See [docs/security.md](docs/security.md) for the full security model.

**Never commit to Git:**
- `.env` files (except `.env.example`)
- Private keys, certificates, or CA material
- `.ovpn` client profiles
- Cloudflare tunnel tokens
- Database credentials

Development-only endpoints (`/dev-login`) are disabled in production and fail closed with 403.

---

## License

See [LICENSE](LICENSE).
