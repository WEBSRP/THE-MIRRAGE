# MIRRAGE

**MIRRAGE** is an isolated, forensic cybersecurity training environment designed to simulate real-world infrastructure and network exploitation scenarios. 

*“What you see is not necessarily what is there.”*

---

## 🛠 Tech Stack

### Frontend
- **Framework:** React 19 + TypeScript + Vite
- **Styling:** Tailwind CSS v4
- **Routing:** React Router v7
- **Architecture:** Minimalist, dark cinematic editorial aesthetic without external icon libraries or excessive dependencies.

### Backend
- **Framework:** FastAPI (Python 3.13)
- **Database:** SQLite (via SQLAlchemy Asyncio)
- **Authentication:** JWT (JSON Web Tokens)
- **Networking:** OpenVPN profile generation and session tracking
- **Testing:** `pytest` + `pytest-asyncio`

---

## 🚀 Getting Started

### Prerequisites
- Node.js (v20+)
- Python (3.13+)
- OpenVPN (for connecting to challenge environments)

### Backend Setup

1. Navigate to the project root and create a virtual environment:
   ```bash
   cd Mirrage-EC2
   python3 -m venv backend/venv
   source backend/venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp backend/.env.example backend/.env
   # Update .env with your secrets. Make sure ENVIRONMENT is set to 'development' for local testing.
   ```

4. Run the backend development server:
   ```bash
   PYTHONPATH=. uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   The API will be accessible at `http://127.0.0.1:8000`. API Docs available at `http://127.0.0.1:8000/docs`.

### Frontend Setup

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd Mirrage-EC2/frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```
   The frontend will be accessible at `http://localhost:5173`. API requests are automatically proxied to the backend.

---

## 🧪 Testing

To run the backend test suite, ensuring your virtual environment is active:
```bash
PYTHONPATH=. pytest backend/tests -v
```

To lint and build the frontend:
```bash
cd frontend
npm run lint
npm run build
```

---

## 🔒 Security Notice

**Never commit the following files to version control:**
- `.env` or `.env.*` (except `.env.example`)
- `mirrage.db` or any other `.sqlite` files
- `.ovpn` configuration profiles downloaded from the dashboard
- Any private keys or TLS certificates

Development access (`dev_player`) is strictly restricted to the `development` environment and automatically fails closed in production.
