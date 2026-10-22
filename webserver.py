import os
import sys
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 10000))


def run_bot():
    subprocess.run([sys.executable, "main.py"], check=False)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Web server running on port {PORT}")

    server.serve_forever()
