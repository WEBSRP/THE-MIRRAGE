# MIRRAGE Backend Engine

Production-grade FastAPI backend for the **MIRRAGE** Cybersecurity CTF & Honeypot Deception Platform.

---

## 1. Architectural Overview

```
                          +-------------------------+
                          |   Vercel / React Web    |
                          +------------+------------+
                                       |
                           HTTPS REST  | JWT Auth
                                       v
                          +-------------------------+
                          |     FastAPI Backend     |
                          |      (Python 3.13)      |
                          +----+---------------+----+
                               |               |
              +----------------+               +----------------+
              v                                                 v
  +-----------------------+                         +-----------------------+
  | PostgreSQL / SQLite   |                         |  OpenVPN Server (EC2) |
  | (Async SQLAlchemy ORM)|                         |  (10.8.0.0/24 Subnet) |
  +-----------------------+                         +-----------+-----------+
                                                                |
                                                                v
                                                    +-----------------------+
                                                    |  k3s / Kubernetes     |
                                                    |  (10.42.0.0/16 Subnet)|
                                                    +-----------+-----------+
                                                                |
                                                     Dual-Container Sandbox
                                                    +-----------+-----------+
                                                    |  Mirage   |    CTF    |
                                                    |  Honeypot |   Core    |
                                                    |  Port: 22 | Port: 2222|
                                                    +-----------+-----------+
```

---

## 2. Core Capabilities & Workflows

1. **Player Authentication & Onboarding**:
   - Email OTP verification for sign-in and account creation, with JWT access tokens.
   - Automatic generation of unique OpenVPN client identity and `.ovpn` configuration profiles.
2. **Dynamic Machine Sandboxing ("Start Machine")**:
   - Slot limit enforcement (max 3 concurrent active sessions).
   - Dual-container Pod provisioning (`mirage-honeypot` on port 22, `ctf-core` on port 2222).
   - Isolation with Kubernetes `NetworkPolicy`.
   - Local development simulation fallback when running without Kubernetes.
3. **Deception Telemetry & Decoy Presentation**:
   - Only the Mirage honeypot endpoint (`10.42.0.x:22`) is presented to the player.
   - The underlying CTF challenge is hidden and discovered through investigation.
4. **OpenVPN Connectivity & Telemetry**:
   - Downloads `.ovpn` file directly.
   - Telemetry tracks VPN state (`connected`/`disconnected`), assigned IP (`10.8.0.x`), and data usage.
5. **Automated Lifecycle & Cleanup**:
   - Automatic expiration after 30 minutes of inactivity.
   - Background worker cleans up Kubernetes resources and reclaims slots.

---

## 3. Directory Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app factory, CORS, lifespan, exception handlers
│   ├── core/
│   │   ├── config.py            # Pydantic Settings & environment configuration
│   │   ├── database.py          # Async SQLAlchemy engine & session factory
│   │   ├── security.py          # Password hashing (bcrypt) & JWT issuance
│   │   └── exceptions.py        # Domain exceptions
│   ├── models/                  # SQLAlchemy ORM models
│   │   ├── user.py              # User account model
│   │   ├── session.py           # GameSession model (Pod metadata, Decoy IPs, status)
│   │   ├── vpn.py               # VpnProfile model (config data, connection stats)
│   │   ├── activity.py          # ActivityLog model (honeypot triggers, audit trail)
│   │   └── challenge.py         # Challenge & FlagSubmission models
│   ├── schemas/                 # Pydantic schemas (requests & responses)
│   ├── services/                # Business logic
│   │   ├── auth_service.py      # Registration & authentication
│   │   ├── session_service.py   # Machine slots, timeouts, and state machines
│   │   ├── k8s_service.py       # Kubernetes / k3s Pod provisioner (+ local mock)
│   │   ├── vpn_service.py       # OpenVPN profile generator & status log parser
│   │   ├── activity_service.py  # Honeypot interaction logging
│   │   └── challenge_service.py # CTF flag verification
│   ├── api/
│   │   ├── deps.py              # FastAPI auth & DB dependency injection
│   │   └── v1/
│   │       ├── api.py           # Router aggregator
│   │       └── endpoints/       # auth, session, vpn, challenge, activity, health
│   └── workers/
│       └── cleanup.py           # Background session expiry and cleanup worker
├── k8s/                         # Kubernetes manifests (Pod template & NetworkPolicy)
├── openvpn/                     # OpenVPN server configuration
├── tests/                       # 100% async pytest test suite
├── scripts/
│   ├── run_dev.sh               # Dev server launcher
│   └── init_db.py               # DB init & challenge seeder
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## 4. Quickstart & Local Development

### Prerequisites
- Python 3.10+ (tested on Python 3.13)

### Installation & Run

```bash
# 1. Navigate to project root
cd /home/websrp/project/Mirrage-EC2

# 2. Activate virtual environment
source backend/venv/bin/activate

# 3. Launch development server
./backend/scripts/run_dev.sh
```

The API will be live at `http://localhost:8000`.
Interactive Swagger API documentation: `http://localhost:8000/api/v1/docs`.

---

## 5. Running the Test Suite

```bash
source backend/venv/bin/activate
PYTHONPATH=. pytest backend/tests -v
```

All 16 unit and integration tests run against an in-memory async SQLite engine with zero external dependencies.

---

## 6. API Reference Summary

### Authentication (`/api/v1/auth`)
- `POST /request-otp`: Send an email verification code.
- `POST /verify-otp`: Verify the code and issue a JWT; create an account for a new email.
- `POST /resend-otp`: Resend with cooldown and rate limiting.
- `GET /me`: Get the authenticated player profile.

OTP is the only sign-in method. Password login, password registration, and development login routes are removed. Existing users can sign in using their email; existing database password columns are retained for compatibility.

### Machine & Session Management (`/api/v1/session`)
- `GET /slots`: Check available sandbox slots (max 3).
- `POST /start`: Start player machine (provisions Pod & assigns `10.42.0.x`).
- `GET /status`: Get session status, remaining countdown, and decoy IP.
- `POST /stop`: Stop machine and delete Pod.

### OpenVPN Connectivity (`/api/v1/vpn`)
- `GET /profile`: Get `.ovpn` configuration metadata.
- `GET /download`: Download `.ovpn` configuration file attachment.
- `GET /status`: Get VPN connection indicator (`connected`/`disconnected`) and assigned IP (`10.8.0.x`).

### CTF & Challenges (`/api/v1/challenges`)
- `GET /`: List challenges and solve status.
- `POST /submit`: Submit a flag for verification.

### Telemetry & Audit (`/api/v1/activity`)
- `GET /`: Get audit trail and honeypot interaction logs.

### Diagnostics (`/api/v1/health`)
- `GET /`: System health check (database, k8s engine, vpn engine).

---

## 7. EC2 Production Deployment

On the Linux EC2 instance:
1. **Install k3s**: `curl -sfL https://get.k3s.io | sh -`
2. **Install OpenVPN**: `apt-get install openvpn`
3. **Configure Environment**: Copy `.env.example` to `.env` and set:
   ```env
   ENVIRONMENT=production
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mirrage_db
   K8S_ENABLED=true
   K8S_KUBECONFIG_PATH=/etc/rancher/k3s/k3s.yaml
   OPENVPN_ENABLED=true
   ```
4. **Start Backend via systemd or Docker Compose**:
   ```bash
   docker-compose -f backend/docker-compose.yml up -d
   ```
