# Cloudflare Tunnel Configuration

MIRRAGE uses a Cloudflare Tunnel to expose the FastAPI backend API publicly
without opening inbound ports on the EC2 instance.

## Architecture

```
Browser
  |
  v
https://api.themirrage.me
  |
  v
Cloudflare Edge (TLS termination)
  |
  v
cloudflared (EC2, systemd service)
  |
  v
http://127.0.0.1:80 (Nginx)
  |
  v
http://127.0.0.1:8000 (FastAPI)
```

## Setup

1. Install cloudflared on EC2:
   ```
   sudo apt install cloudflared
   ```

2. Create a tunnel in the Cloudflare Zero Trust dashboard.

3. Save the tunnel token to `/etc/cloudflared/token` (root-owned, mode 600).

4. Configure the tunnel route in Cloudflare dashboard:
   - Public hostname: `api.themirrage.me`
   - Service: `http://127.0.0.1:80`

5. Install and enable the systemd service:
   ```
   sudo cp infrastructure/systemd/cloudflared.service.example /etc/systemd/system/cloudflared.service
   sudo systemctl daemon-reload
   sudo systemctl enable --now cloudflared
   ```

## Security Notes

- The tunnel token at `/etc/cloudflared/token` is a secret credential.
  It must NEVER be committed to Git.
- The token can be regenerated from the Cloudflare Zero Trust dashboard
  if compromised.
- cloudflared only connects outbound to Cloudflare — no inbound firewall
  rules are required for the API.
