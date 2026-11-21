"""Real Nginx header-contract test; disposable root container only."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    if not Path("/.dockerenv").exists():
        raise RuntimeError("Run only in the documented disposable container")
    class Backend(BaseHTTPRequestHandler):
        def do_GET(self):
            payload = json.dumps({"headers": dict(self.headers), "peer": self.client_address[0]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def log_message(self, *args):
            pass
    backend = HTTPServer(("127.0.0.1", 8000), Backend)
    threading.Thread(target=backend.serve_forever, daemon=True).start()
    root = Path(tempfile.mkdtemp(prefix="otp-proxy-check-"))
    source = Path(__file__).resolve().with_name("mirrage.conf.example").read_text()
    config = root / "nginx.conf"
    config.write_text(f"pid {root}/nginx.pid;\nerror_log {root}/error.log;\nevents {{}}\nhttp {{ access_log off;\n" + source + "\n}\n")
    subprocess.run(["/usr/sbin/nginx", "-t", "-p", str(root), "-c", str(config)], check=True,
                   capture_output=True, timeout=10)
    nginx = subprocess.Popen(["/usr/sbin/nginx", "-p", str(root), "-c", str(config), "-g", "daemon off;"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    def get(headers):
        with urlopen(Request("http://127.0.0.1/", headers=headers), timeout=2) as response:
            return json.load(response)
    try:
        for _ in range(40):
            try:
                get({"CF-Connecting-IP": "198.51.100.20"})
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("Disposable proxy did not become ready")
        for visitor in ("198.51.100.20", "2001:db8::20"):
            result = get({"CF-Connecting-IP": visitor, "X-Mirrage-Client-IP": "203.0.113.99",
                          "X-Forwarded-For": "203.0.113.98", "X-Real-IP": "203.0.113.97"})
            headers = {key.lower(): value for key, value in result["headers"].items()}
            assert result["peer"] == "127.0.0.1"
            assert headers["x-mirrage-client-ip"] == headers["x-forwarded-for"] == headers["x-real-ip"] == visitor
            assert "cf-connecting-ip" not in headers
        for headers in ({}, {"CF-Connecting-IP": "invalid"}, {"CF-Connecting-IP": "198.51.100.1, 203.0.113.1"}):
            try:
                get(headers)
            except HTTPError as error:
                assert error.code == 400
            else:
                raise AssertionError("Missing/malformed tunnel identity was accepted")
        assert "listen 127.0.0.1:80" in source and "listen [::1]:80" in source
        print("PASS: real Nginx visitor normalization, overwritten spoofed headers, IPv4/IPv6, rejected missing/malformed identities")
    finally:
        nginx.terminate()
        nginx.wait(timeout=10)
        backend.shutdown()


if __name__ == "__main__":
    main()
