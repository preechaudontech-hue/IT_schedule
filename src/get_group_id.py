"""Tiny helper to discover a LINE group id.

Run this locally, expose it with a tunnel (e.g. `cloudflared tunnel --url http://localhost:8000`),
set the tunnel URL as the channel Webhook URL in the LINE console, then send any
message in the group. The group id is printed here.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            data = json.loads(body)
            for ev in data.get("events", []):
                src = ev.get("source", {})
                print("source:", json.dumps(src, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print("parse error:", e, body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):  # silence default logging
        pass


if __name__ == "__main__":
    print("Listening on http://0.0.0.0:8000  (POST /)")
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
